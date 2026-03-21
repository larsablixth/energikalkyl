# Energikalkyl - El, Sol & Batteri

Ska du investera i hembatteri och solceller? Den har appen simulerar lonsamheten baserat pa verkliga elpriser, din forbrukning, natavgifter och finansiering.

**Appen rekommenderar optimal batteristorlek och visar exakt hur mycket du sparar per manad.**

## Kom igang

### Alternativ 1: Kör lokalt
```bash
pip install -r requirements.txt
streamlit run app.py
```
Oppna http://localhost:8501

### Alternativ 2: Docker
```bash
docker compose up
```
Oppna http://localhost:8501

## Vad behovs?

### Prisdata (obligatoriskt)
Spotpriser hamtas automatiskt fran elprisetjustnu.se. Valj elomrade och period, klicka "Hamta priser".

Alternativt: ladda en CSV-fil med historiska priser.

### Forbrukningsdata (valfritt men rekommenderat)
Ju mer data, desto battre simulering:

| Kalla | Vad du far | Hur |
|-------|-----------|-----|
| **Tibber** | Adress, sakring, natägare, husdata + 30 dagars profil | Klicka "Hamta data" (kraver .tibber_token) |
| **E.ON** | Timforbrukning for E.ON-kunder | Ange installations-ID (kraver .eon_credentials) |
| **Vattenfall Excel** | 3+ ars timdata | Ladda upp filer fran Mina sidor |
| **Annan CSV** | Timforbrukning | Ladda upp |
| **Manuellt** | Grundlast + laster | Ange i steg 2 |

**Tips:** Anvand Tibber (for husdata) OCH Vattenfall Excel (for lang historik) samtidigt.

### Kalibrering
For bast resultat, fyll i din arsforbrukning uppdelad per kategori (uppvarmning, elbil, etc.). Hittas i din elapp (Tibber Insikter, Greenely, eller pa elrakningen).

## Vad simuleras?

- **Alla batteristorlekar** i pristabellen (redigerbar, NKON ESS Pro som standard)
- **Alla tariffer** for din nätägare (Tidstariff, Enkeltariff, Effekttariff)
- **Sakringsuppgradering** — behover du storre sakring?
- **Uppvarmningsmodell** — temperaturanpassad fran SMHI väderdata (230 stationer)
- **Tre framtidsscenarier** — konservativt, sannolikt, hog volatilitet
- **PDF-rapport** for banken med metodik och kassaflodesanalys

## Natägare som stods

| Natägare | Tariffer | Effekttariff |
|----------|---------|-------------|
| Vattenfall Eldistribution | Tid + Enkel | Nej (annu) |
| Ellevio | Effekt | 81.25 kr/kW/man |
| E.ON Energidistribution | Tid + Enkel | Nej |
| Goteborg Energi | Effekt + Enkel | 135 kr/kW/man (vinter) |
| Malarenergi | Effekt | 59.25 kr/kW/man |
| Jamtkraft | Enkel | Nej |
| SEOM (Sollentuna) | Effekt | 145 kr/kW/man (vinter) |
| Anpassad | Alla | Redigerbar |

## API-nycklar (valfritt)

```bash
# Tibber (developer.tibber.com)
echo "din-token" > .tibber_token

# E.ON (kontakta E.ON for API-konto)
echo "client_id:client_secret" > .eon_credentials

# ENTSO-E (transparency.entsoe.eu, valfritt alternativ for spotpriser)
echo "din-nyckel" > .entsoe_key
```

## Teknisk oversikt

| Fil | Funktion |
|-----|---------|
| app.py | Streamlit web GUI |
| batteri.py | Batterisimulering (multi-cykel, solmedveten, sakringsbegransad) |
| solar.py | Solproduktionsmodell (cos3, konfigurerbara kWp) |
| tariff.py | Nattariffer + 8 natägare med effekttariff |
| heating.py | Uppvarmningsmodell (bergvarme, luftvarmepump, fjarrvarme, direktel) |
| weather.py | SMHI väderdata (230 stationer, auto-hamtning) |
| report.py | PDF-rapport for bankunderlag |
| tibber_source.py | Tibber GraphQL API |
| eon_source.py | E.ON Navigator API |
| import_vattenfall.py | Vattenfall Excel (daglig + timdata) |

## Licens

Privat projekt. Dela med vanners tillstand.
