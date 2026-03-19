# Energikalkyl — El, Sol & Batteri

Analysverktyg for svenska elpriser, solceller och hembatteri. Simulerar lonsamhet baserat pa historiska spotpriser, verklig forbrukning, solproduktion, natavgifter och investeringskostnader.

## Arkitektur

```
elpriser.py          CLI huvudprogram, datahämtning, alla kommandon
app.py               Streamlit web GUI
batteri.py           Batterisimulering (BatteryConfig, LoadSchedule, FlexibleLoad, simulate)
solar.py             Solproduktionsmodell (Stockholm, konfigurerbara kWp)
tariff.py            Vattenfall Tidstariff/Enkeltariff 2026, säkringsavgifter
entsoe_source.py     ENTSO-E API datakälla + EUR/SEK via ECB
tibber_source.py     Tibber GraphQL API (priser, förbrukning, profiler)
import_consumption.py  CSV-import av förbrukningsdata (generisk)
import_vattenfall.py   Vattenfall Eldistribution Excel-import
```

## Datakällor

| Källa | Typ | API-nyckel | Beskrivning |
|-------|-----|-----------|-------------|
| elprisetjustnu.se | Spotpriser | Nej | Gratis, 15-min upplösning, cachas lokalt i `.price_cache/` |
| ENTSO-E | Spotpriser (grossist) | Ja (`.entsoe_key`) | Bulk-hämtning, EUR/MWh, konverteras med daglig ECB-kurs |
| Tibber | Priser + förbrukning | Ja (`.tibber_token`) | GraphQL API, timdata ~30 dagar, månadsdata ~12 mån |
| Vattenfall Eldistribution | Förbrukning | Manuell CSV/Excel | Ladda ner från Mina sidor (BankID), daglig data i Excel |
| ECB (frankfurter.app) | EUR/SEK-kurs | Nej | Dagliga kurser, cachas i `.fx_cache.json` |

## Installation

```bash
cd ~/projects/elpriser
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Beroenden: `requests`, `entsoe-py`, `pandas`, `streamlit`, `plotly`, `openpyxl`

## API-nycklar

```bash
# ENTSO-E (transparency.entsoe.eu → My Account → Web API Security Token)
echo "din-nyckel" > .entsoe_key

# Tibber (developer.tibber.com → Load personal token)
echo "din-token" > .tibber_token
```

## Användning — CLI

### Hämta priser
```bash
# Dagens priser
python elpriser.py idag --zon SE3

# Hämta 3 år historik (cachas lokalt)
python elpriser.py hämta --zon SE3 --datum 2023-03-19 --till 2026-03-18 --csv historik.csv

# Från ENTSO-E
python elpriser.py hämta --källa entsoe --zon SE3 --datum 2023-01-01 --till 2026-03-18 --csv historik_entsoe.csv
```

### Tibber
```bash
python elpriser.py tibber --priser                    # Dagens priser
python elpriser.py tibber --timmar 720 --profil       # 30 dagars förbrukning + profil
python elpriser.py tibber --månader 36                # Månadsförbrukning
python elpriser.py tibber --dagar 1095 --csv daglig.csv  # Daglig data
```

### Batterisimulering
```bash
# Grundläggande
python elpriser.py batteri --csv historik.csv --kapacitet 13.5 --säkring 25

# Fullständig simulering med alla parametrar
python elpriser.py batteri --csv historik.csv \
  --kapacitet 32.15 --laddeffekt 15 --urladdeffekt 15 --verkningsgrad 0.93 \
  --säkring 25 --tariff tid \
  --last elbil:11:23-06 \
  --flex poolpump:3:20:5-9 \
  --sol 15 \
  --pris 25000 --installation 10000 --cykler 8000 --livslängd 15 \
  --sol-pris 150000 --sol-installation 50000 --sol-livslängd 25 \
  --tibber-profil

# Med Vattenfall Excel-förbrukning
python elpriser.py batteri --csv historik.csv \
  --förbruknings-csv /mnt/c/Users/user/Downloads/vattenfall_2025.xlsx \
  --kapacitet 32.15 --laddeffekt 15 --urladdeffekt 15 --sol 15
```

## Användning — Web GUI

```bash
streamlit run app.py
# Öppna http://localhost:8501
```

GUI-struktur:
1. **Sidopanel**: Förbrukningsdata (Tibber/CSV/Excel) + Prisdata (API/CSV/Tibber)
2. **Prisöversikt**: Diagram, prisspridning, tabell, statistik
3. **Anläggning & Parametrar**: Batteri, Solceller, Elnät & Nätavgift, Förbrukning & Laster, Investering
4. **Simulering & Resultat**: Arbitragevinst, ROI, säkringsvarningar, daglig vinst, SOC-diagram, säkringsjämförelse

## Simuleringsmodell

### Batterioptimering (per dag)
1. Solöverskott laddar batteriet gratis (efter hushåll och flexibla laster)
2. Billigaste 25% av timmarna → ladda från nät (om under dagssnittet)
3. Dyraste 25% av timmarna → urladda (om över dagssnittet)
4. Övriga timmar → idle

### Begränsningar som modelleras
- **Säkringsgräns**: Max effekt från nät (A × V × faser)
- **Tidsvarierande last**: Grundlast + schemalagda laster (EV nattetid) + Tibber/Vattenfall-profil
- **Säsongsanpassning**: Månadsdata skalas på timmeprofil (vinter ~2× sommar)
- **Flexibla laster**: Pool-värmepump etc. absorberar solöverskott före batteriet
- **Verkningsgrad**: Tur-retur-förluster vid laddning/urladdning
- **Nätavgift**: Tidstariff (höglast vinter vardag 06-22) eller Enkeltariff + energiskatt

### Investeringskalkyl
- Separata kostnader för batteri och solceller
- Cykellivslängd vs kalenderlivslängd
- Degradering av solpaneler (0.5%/år)
- Återbetalningstid, ROI, total vinst under livslängd

## Vattenfall Eldistribution 2026

### Tidstariff
- Höglasttid (vinter vardag 06-22): 76,50 öre/kWh
- Övrig tid: 30,50 öre/kWh
- Höglasttid = jan, feb, mar, nov, dec, vardagar 06-22 (ej helgdagar)

### Enkeltariff
- Alla timmar: 44,50 öre/kWh

### Abonnemangsavgifter (kr/år)
| 16A | 20A | 25A | 35A | 50A | 63A |
|-----|-----|-----|-----|-----|-----|
| 5 775 | 8 085 | 10 125 | 13 890 | 19 945 | 26 875 |

## Referens-setup (projektägare)

- **Plats**: Sigtuna (SE3)
- **Elnätsägare**: Vattenfall Eldistribution
- **Elhandlare**: Tibber
- **Solceller**: 15 kWp, södervänd
- **Elbil**: 11 kW laddning, nattetid (23-06)
- **Pool**: Värmepump 3 kW, maj-sep
- **Överväger batteri**: NKON ESS Pro 32.15 kWh, 15 kW ladd/urladd, LiFePO4, 8000 cykler
- **Säkring**: 25A 3-fas (max tillgänglig: 35A)
- **Vattenfall-data**: 4 Excel-filer (2023-2026) på `/mnt/c/Users/user/Downloads/`

## Filstruktur — data (ej i git)

```
.entsoe_key          ENTSO-E API-nyckel
.tibber_token        Tibber API-token
.price_cache/        Cachade dagspriser (JSON per dag)
.fx_cache.json       Cachade EUR/SEK-kurser
historik_SE3_3ar.csv 3 år spotpriser SE3 (38 475 rader, 15-min)
```
