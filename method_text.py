"""Method description for the app's "Om kalkylen" section (Swedish, for an economist).

Keep it in step with the code: every number and rule here is what app.py,
batteri.py and economics.py actually do (see CLAUDE.md).
"""

METHOD_SV = r"""
### Vad kalkylen svarar på

Lönar det sig för ett hushåll att investera i ett hembatteri (och eventuellt solceller), och i så fall vilken storlek?
Kalkylen är en **partiell analys på hushållsnivå**: den jämför hushållets elkostnad **med** investeringen mot
**utan** den (kontrafaktiskt), timme för timme, på verkliga historiska priser. Det är ingen samhällsekonomisk
kalkyl — effekter på elsystemet, utsläpp eller andra aktörer ingår inte.

### Indata

| | Källa |
|---|---|
| Elpriser | Spotpriser per timme för valt elområde (Nord Pool day-ahead via elprisetjustnu.se), normalt de senaste ~3 åren. Kvartspriser (sedan 1 okt 2025) räknas om till timmedel. |
| Förbrukning | Hushållets egna timvärden (fil från nätbolaget eller Tibber), annars en temperaturstyrd värmemodell (SMHI:s timtemperaturer) plus grundlast. Utan egna uppgifter används ett exempelhus och resultatet märks **Exempelkalkyl**. |
| Solproduktion | PVGIS (EU:s satellitdata för platsen), egen fil från växelriktaren, eller en förenklad modell. |
| Nättariff | Nätbolagets prislista: överföringsavgift, energiskatt (45 öre/kWh inkl. moms 2026), ev. effektavgift och säkringsabonnemang. |
| Investering | Batteripris, installation, solcellspris, finansiering — anges av användaren (exempelvärden är märkta). |

### Vad en kWh är värd

- **Köpt el** kostar *spotpris × 1,25 (moms) + överföringsavgift + energiskatt* för just den timmen. Det är
  hushållets **marginalkostnad**, och den används för att värdera allt batteriet gör: en kWh som batteriet levererar
  en dyr timme är en kWh hushållet slipper köpa då.
- **Fasta avgifter** (abonnemang) påverkas inte — utom om en större säkring krävs, då räknas den högre avgiften som kostnad.
- **Effektavgift** (hos nätbolag som har den): förändringen av månadens uppmätta toppeffekt med investeringen jämfört
  med utan. En högre topp räknas som kostnad.
- **Ingen nettodebitering.** Standardläget är *nollexport*: batteriet laddar bara ur mot husets egen förbrukning och
  solöverskott som inte får plats kapas. Export kan väljas; då ersätts såld el med *spotpris × faktor − avgift*, utan moms.

### Hur batteriet körs

Varje dygn planeras när dygnets priser är kända (de publiceras dagen före). Batteriet laddar billiga timmar och laddar
ur dyra, där varje laddning kopplas till en senare urladdning och de lönsammaste paren väljs först. Ett par genomförs
bara om prisskillnaden täcker förlusten i batteriet (verkningsgraden) **plus 20 öre/kWh**. Hänsyn tas till batteriets
kapacitet och effekt, laddnivågränser och säkringens utrymme (husets last den timmen, med 30 % avdrag för ojämn
fasbelastning). Gratis solöverskott laddar batteriet först, därefter flexibla laster som varmvatten.

Planeringen förutsätter att dygnets priser och förbrukning är kända — en **övre gräns** för vad ett styrsystem klarar.
Kontrollen *”Klarar ett riktigt styrsystem det här?”* kör därför samma period genom ett verkligt styrsystems kod, som
själv måste gissa förbrukning och sol; den brukar landa några procent lägre, och då bör den lägre siffran användas.

### Från simulering till årsbelopp

Hela perioden simuleras timme för timme. Summorna delas med antalet dagar och multipliceras med 365,25 — ett
**genomsnittsår** för perioden. Nyttan delas i tre delar:

1. **Batteriet**: värdet av urladdad el (undviket inköp) − kostnaden för el som laddats från nätet, ± ändrad effektavgift.
2. **Solcellerna** (bara om de ingår i investeringen): den el som används direkt i huset, *min(sol, förbrukning)* per
   timme, värderad till den timmens pris. Kapad sol räknas inte.
3. **Fasta poster**: batteriets tomgångsförbrukning (W × 8 760 h × genomsnittspris), ev. dyrare säkring och ev.
   kostnad för tariffbyte.

**Tariffval:** alla nätbolagets tariffer prövas. Referensen är den **billigaste tariffen utan investering**, så att en
besparing som går att få bara genom att byta tariff inte räknas som batteriets förtjänst (den visas separat). Väljs en
tariff som ger högre räkning för hushållets övriga förbrukning dras mellanskillnaden av varje år.

### Livslängd, slitage och lönsamhetsmått

- **Livslängd** = antal laddcykler batteriet klarar ÷ cykler per år, högst 15 år.
- **Slitage**: batteriets nytta minskar linjärt med kapacitetsförlusten (standard 1 %/år), solcellernas med 0,5 %/år;
  slitaget räknas mitt i varje år.
- **”Lägre elkostnad per år”** i rekommendationen är **år 1**.
- **Netto under livslängden** = summan av årens nytta − batteriinvesteringen − den del av solinvesteringen som hör till
  perioden (livslängd ÷ 25 år, solcellernas livslängd).
- **Återbetalningstid** = år tills den ackumulerade nyttan når investeringen (inom 25 år).
- **Viktigt för en ekonom:** alla belopp är **nominella och odiskonterade** — ingen kalkylränta, ingen inflation och
  inga prisförändringar utöver framtidsscenarierna. Nettot är alltså en enkel summa; med en positiv kalkylränta blir
  nuvärdet lägre, och en lång återbetalningstid väger tyngre än den ser ut.

### Finansiering

Lån räknas som **annuitetslån**. Jämförelsen görs över **batteriets livslängd**, inte lånets löptid: netto under
livslängden − räntan som betalats under samma period, och den skuld som återstår när batteriet är förbrukat visas.
(Ett 50-årigt bolån för ett batteri som håller 15 år ser annars bättre ut än det är.) **Grönt avdrag** är valfritt och
avstängt som standard: 50 % av batteriet (bara tillsammans med solceller), 15 % av solcellerna, högst 50 000 kr per person.

### Framtidsscenarier

Batteriet tjänar på **prisskillnader inom dygnet**, inte på prisnivån. Scenarierna skalar avvikelsen från dygnets
medelpris (0,7×, 1,0×, 1,5×, 2,5×, 4×) med oförändrat dygnsmedel och låter förändringen ske gradvis över 10 år.
De är **antaganden, inte prognoser**; ingen bedöms som mer sannolik än någon annan. 1,0× är huvudresultatet.

### Förenklingar och vad som inte ingår

- Odiskonterade, nominella belopp (se ovan).
- Historiska priser antas representativa för framtiden (utom i scenarierna).
- Dygnets priser och förbrukning antas kända vid planeringen — styrsystemskontrollen visar vad det kostar i verkligheten.
- Timmedelvärden: korta effekttoppar inom timmen (spis, bastu) syns inte.
- Batteriet simuleras som nytt varje år; slitaget läggs på värdet i efterhand.
- Ingen ersättning för stödtjänster (frekvensreglering, flexibilitet), inga skatteeffekter utöver moms, energiskatt och
  grönt avdrag, inga underhållskostnader utöver det användaren anger.
- Kalkylen lägger inte in någon inbyggd optimism: alla antaganden är neutrala och visas under rekommendationen
  (*Antaganden bakom resultatet*) och i PDF-rapporten.
"""
