"""
Translation strings for Energikalkyl.

Usage:
    from translations import t, set_language
    set_language("en")
    print(t("app_title"))  # "Energy Calculator — Electricity, Solar & Battery"
"""

_lang = "sv"

STRINGS = {
    # ---- App title & global ----
    "app_title": {
        "sv": "Energikalkyl — El, Sol & Batteri",
        "en": "Energy Calculator — Electricity, Solar & Battery",
    },
    "app_subtitle": {
        "sv": "Simulera lönsamheten i hembatteri och solceller baserat på verkliga elpriser och din förbrukning.",
        "en": "Simulate the profitability of a home battery and solar panels based on real electricity prices and your consumption.",
    },
    "language": {
        "sv": "Språk",
        "en": "Language",
    },

    # ---- Step 1: Load data ----
    "step1_header": {
        "sv": "1. Ladda data",
        "en": "1. Load data",
    },
    "step1_caption": {
        "sv": "Börja med Tibber om du har det — då fylls förbrukning, plats och nätägare i automatiskt.",
        "en": "Start with Tibber if you have it — it auto-fills consumption, location, and grid operator.",
    },
    "consumption_header": {
        "sv": "Förbrukningsprofil",
        "en": "Consumption profile",
    },
    "consumption_best": {
        "sv": "**Bäst resultat:** Hämta från Tibber (ger adress, nätägare, säkring) "
              "**och** ladda upp timdata från din nätägare (Vattenfall, E.ON eller CSV). Båda kan användas simultant.",
        "en": "**Best results:** Fetch from Tibber (gives address, grid operator, fuse) "
              "**and** upload hourly data from your grid operator (Vattenfall, E.ON, or CSV). Both can be used simultaneously.",
    },
    "tibber_expander": {
        "sv": "Hämta från elapp (Tibber)",
        "en": "Fetch from electricity app (Tibber)",
    },
    "tibber_caption": {
        "sv": "Hämtar förbrukningsprofil, adress, nätägare, säkring och husdata. "
              "Hämta din token på [developer.tibber.com](https://developer.tibber.com/).",
        "en": "Fetches consumption profile, address, grid operator, fuse size, and house data. "
              "Get your token at [developer.tibber.com](https://developer.tibber.com/).",
    },
    "tibber_token_label": {
        "sv": "Tibber API-token",
        "en": "Tibber API token",
    },
    "tibber_token_placeholder": {
        "sv": "Klistra in din token här",
        "en": "Paste your token here",
    },
    "tibber_token_help": {
        "sv": "Klistra in din personliga Tibber-token. Hittas på developer.tibber.com → ditt konto.",
        "en": "Paste your personal Tibber token. Found at developer.tibber.com → your account.",
    },
    "fetch_data": {
        "sv": "Hämta data",
        "en": "Fetch data",
    },
    "tibber_token_security": {
        "sv": "🔒 Din token skickas krypterat (HTTPS) och sparas bara i minnet under din session — "
              "den lagras aldrig på disk. Token ger enbart läsåtkomst till förbrukningsdata, "
              "inte kontroll över enheter eller betalningar.",
        "en": "🔒 Your token is sent encrypted (HTTPS) and only kept in memory during your session — "
              "it is never saved to disk. The token only grants read access to consumption data, "
              "not control over devices or payments.",
    },
    "fetching_tibber": {
        "sv": "Hämtar förbrukningsprofil och heminfo från Tibber...",
        "en": "Fetching consumption profile and home info from Tibber...",
    },
    "tibber_loaded": {
        "sv": "Tibber-data laddad",
        "en": "Tibber data loaded",
    },
    "tibber_error": {
        "sv": "Tibber-fel",
        "en": "Tibber error",
    },
    "eon_expander": {
        "sv": "Hämta från E.ON Energidata",
        "en": "Fetch from E.ON Energy Data",
    },
    "eon_caption": {
        "sv": "För E.ON-kunder. Kräver API-nyckel (.eon_credentials). "
              "Kontakta E.ON för att skapa API-konto.",
        "en": "For E.ON customers. Requires API key (.eon_credentials). "
              "Contact E.ON to create an API account.",
    },
    "installation_id": {
        "sv": "Installations-ID",
        "en": "Installation ID",
    },
    "years_count": {
        "sv": "Antal år",
        "en": "Number of years",
    },
    "fetch_eon": {
        "sv": "Hämta från E.ON",
        "en": "Fetch from E.ON",
    },
    "upload_expander": {
        "sv": "Ladda upp förbrukningsdata (Excel/CSV)",
        "en": "Upload consumption data (Excel/CSV)",
    },
    "upload_caption": {
        "sv": "**Vattenfall:** Logga in på [mina.vattenfall.se](https://mina.vattenfall.se) → "
              "Elavtal → Elförbrukning → Exportera till Excel. Ladda upp Excel-filen direkt — "
              "det komplicerade formatet hanteras automatiskt.  \n"
              "**Övriga nätägare:** CSV med kolumner för datum, tid och förbrukning (kWh). "
              "Formatet detekteras automatiskt (semikolon/komma, svensk/engelsk header).",
        "en": "**Vattenfall:** Log in at [mina.vattenfall.se](https://mina.vattenfall.se) → "
              "Electricity contract → Consumption → Export to Excel. Upload the Excel file directly — "
              "the complex format is handled automatically.  \n"
              "**Other grid operators:** CSV with columns for date, time, and consumption (kWh). "
              "Format is auto-detected (semicolon/comma, Swedish/English headers).",
    },
    "consumption_data": {
        "sv": "Förbrukningsdata",
        "en": "Consumption data",
    },
    "no_consumption": {
        "sv": "Ingen förbrukningsdata laddad — standardvärden används i steg 2.",
        "en": "No consumption data loaded — default values used in step 2.",
    },

    # ---- Prices ----
    "prices_header": {
        "sv": "Elpriser (spotpris)",
        "en": "Electricity prices (spot)",
    },
    "prices_caption": {
        "sv": "Historiska spotpriser behövs för simuleringen. Ju mer data, desto bättre resultat.",
        "en": "Historical spot prices are needed for the simulation. More data = better results.",
    },
    "source": {
        "sv": "Källa",
        "en": "Source",
    },
    "fetch_api": {
        "sv": "Hämta från API",
        "en": "Fetch from API",
    },
    "load_csv": {
        "sv": "Ladda CSV",
        "en": "Load CSV",
    },
    "price_zone": {
        "sv": "Elområde",
        "en": "Price zone",
    },
    "from_date": {
        "sv": "Från",
        "en": "From",
    },
    "to_date": {
        "sv": "Till",
        "en": "To",
    },
    "fetch_prices": {
        "sv": "Hämta priser",
        "en": "Fetch prices",
    },
    "fetching_prices": {
        "sv": "Hämtar spotpriser...",
        "en": "Fetching spot prices...",
    },
    "load_prices_warning": {
        "sv": "Ladda spotpriser för att köra simuleringen.",
        "en": "Load spot prices to run the simulation.",
    },
    "step1_incomplete": {
        "sv": "**Steg 1 ej klart** — ladda spotpriser ovan för att fortsätta.",
        "en": "**Step 1 incomplete** — load spot prices above to continue.",
    },
    "data_synced": {
        "sv": "**Data laddad och synkroniserad.** Konfigurera din anläggning nedan.",
        "en": "**Data loaded and synchronized.** Configure your system below.",
    },
    "data_loaded": {
        "sv": "**Data laddad.** Konfigurera din anläggning nedan och kör simuleringen.",
        "en": "**Data loaded.** Configure your system below and run the simulation.",
    },

    # ---- Spread analysis ----
    "cheapest_hour": {
        "sv": "Billigaste timmen",
        "en": "Cheapest hour",
    },
    "most_expensive_hour": {
        "sv": "Dyraste timmen",
        "en": "Most expensive hour",
    },
    "typical_spread": {
        "sv": "Typisk dagsskillnad",
        "en": "Typical daily spread",
    },
    "good_days": {
        "sv": "Bra dagar (topp 20%)",
        "en": "Good days (top 20%)",
    },
    "spread_explanation": {
        "sv": "Batteriet laddar under de billigaste 4 timmarna och laddar ur under de dyraste. "
              "Ju större skillnad, desto mer tjänar batteriet.",
        "en": "The battery charges during the 4 cheapest hours and discharges during the most expensive. "
              "The bigger the spread, the more the battery earns.",
    },

    # ---- Step 2: System ----
    "step2_header": {
        "sv": "2. Din anläggning",
        "en": "2. Your system",
    },
    "step2_caption": {
        "sv": "Beskriv ditt hus, elnät och elanvändare. Uppvärmningsmodellen anpassas automatiskt efter din plats och hustyp.",
        "en": "Describe your house, grid connection, and electricity usage. The heating model adapts automatically to your location and house type.",
    },
    "battery": {
        "sv": "Batteri",
        "en": "Battery",
    },
    "efficiency": {
        "sv": "Verkningsgrad (%)",
        "en": "Round-trip efficiency (%)",
    },
    "efficiency_help": {
        "sv": "Tur-retur-verkningsgrad. Gäller alla batteristorlekar.",
        "en": "Round-trip efficiency. Applies to all battery sizes.",
    },
    "cycle_life": {
        "sv": "Cykellivslängd",
        "en": "Cycle life",
    },
    "cycle_life_help": {
        "sv": "Antal cykler innan batteriet tappar kapacitet. LiFePO4: typiskt 6000-8000.",
        "en": "Number of cycles before battery degrades. LiFePO4: typically 6000-8000.",
    },
    "solar_panels": {
        "sv": "Solceller",
        "en": "Solar panels",
    },
    "system_kwp": {
        "sv": "System (kWp)",
        "en": "System (kWp)",
    },
    "export_price": {
        "sv": "Försäljningspris (andel av spot)",
        "en": "Export price (share of spot)",
    },
    "export_price_help": {
        "sv": "1.0 = du får hela spotpriset. 0 = ingen försäljning till nät.",
        "en": "1.0 = you get full spot price. 0 = no export to grid.",
    },
    "export_fee": {
        "sv": "Försäljningsavgift (öre/kWh)",
        "en": "Export fee (öre/kWh)",
    },
    "export_fee_help": {
        "sv": "Tibber tar ~5 öre/kWh vid försäljning till nät.",
        "en": "Tibber charges ~5 öre/kWh for grid export.",
    },
    "solar_data": {
        "sv": "Soldata",
        "en": "Solar data",
    },
    "solar_model": {
        "sv": "Modell (cos³)",
        "en": "Model (cos³)",
    },
    "solar_pvgis": {
        "sv": "PVGIS (satellit)",
        "en": "PVGIS (satellite)",
    },
    "solar_csv": {
        "sv": "CSV (växelriktare)",
        "en": "CSV (inverter)",
    },
    "solar_data_help": {
        "sv": "PVGIS ger platsspecifik produktion baserad på satellitdata (2005-2023). "
              "CSV för egen data från växelriktare.",
        "en": "PVGIS provides location-specific production based on satellite data (2005-2023). "
              "CSV for your own inverter data.",
    },
    "solar_location": {
        "sv": "Plats för soldata",
        "en": "Location for solar data",
    },
    "tilt": {
        "sv": "Lutning (°)",
        "en": "Tilt (°)",
    },
    "tilt_help": {
        "sv": "0=horisontellt, 35=typiskt tak, 90=fasad",
        "en": "0=horizontal, 35=typical roof, 90=facade",
    },
    "direction": {
        "sv": "Riktning (°)",
        "en": "Direction (°)",
    },
    "direction_help": {
        "sv": "0=söder, -90=öster, 90=väster",
        "en": "0=south, -90=east, 90=west",
    },
    "fetch_pvgis": {
        "sv": "Hämta PVGIS-data",
        "en": "Fetch PVGIS data",
    },
    "fetching_pvgis": {
        "sv": "Hämtar satellitbaserad soldata från PVGIS...",
        "en": "Fetching satellite-based solar data from PVGIS...",
    },
    "solar_production_csv": {
        "sv": "Solproduktion (CSV)",
        "en": "Solar production (CSV)",
    },
    "solar_csv_help": {
        "sv": "Timvis produktion från växelriktare (Huawei, SMA, Fronius, Enphase m.fl.)",
        "en": "Hourly production from inverter (Huawei, SMA, Fronius, Enphase, etc.)",
    },
    "use_real_solar": {
        "sv": "Använd verklig soldata",
        "en": "Use real solar data",
    },
    "use_real_solar_help": {
        "sv": "Använder uppmätt produktion istället för modell.",
        "en": "Uses measured production instead of model.",
    },

    # ---- Grid ----
    "grid": {
        "sv": "Elnät",
        "en": "Grid",
    },
    "grid_operator": {
        "sv": "Nätägare",
        "en": "Grid operator",
    },
    "grid_operator_help": {
        "sv": "Din elnätsägare (står på elnätsfakturan). Hämtas automatiskt från Tibber om tillgänglig.",
        "en": "Your grid operator (on your grid invoice). Auto-detected from Tibber if available.",
    },
    "fuse_size": {
        "sv": "Nuvarande säkring (A)",
        "en": "Current fuse (A)",
    },
    "fuse_help": {
        "sv": "Din nuvarande säkring. Simuleringen utvärderar om du bör uppgradera.",
        "en": "Your current fuse. The simulation evaluates if you should upgrade.",
    },
    "phases": {
        "sv": "Faser",
        "en": "Phases",
    },
    "energy_tax": {
        "sv": "Energiskatt (öre/kWh)",
        "en": "Energy tax (öre/kWh)",
    },
    "energy_tax_help": {
        "sv": "43.90 öre + 25% moms = 54.88 (2026)",
        "en": "43.90 öre + 25% VAT = 54.88 (2026)",
    },

    # ---- Loads ----
    "loads_header": {
        "sv": "Elanvändare",
        "en": "Electricity loads",
    },
    "loads_caption": {
        "sv": "Laster utöver uppvärmning. EV och pool hanteras separat från hushållets grundlast.",
        "en": "Loads beyond heating. EV and pool are handled separately from base household load.",
    },
    "base_load": {
        "sv": "Grundlast (kW)",
        "en": "Base load (kW)",
    },
    "base_load_help": {
        "sv": "Hushållets ständiga förbrukning. Ignoreras om uppvärmningsmodellen är aktiv.",
        "en": "Household always-on consumption. Ignored when heating model is active.",
    },
    "scheduled_loads": {
        "sv": "**Tidsstyrda laster**",
        "en": "**Scheduled loads**",
    },
    "scheduled_caption": {
        "sv": "Ange ett brett tidsfönster och aktivera Smart för att välja billigaste timmarna "
              "(spotpriser kända dygnet före). kWh/dag styr hur många timmar som behövs. "
              "Utan Smart körs lasten alla timmar i fönstret. "
              "OBS: Om du fyller i kalibrering (Tibber Insights) uppdateras elbilens kWh/dag automatiskt från verklig data.",
        "en": "Set a wide time window and enable Smart to pick the cheapest hours "
              "(spot prices known day-ahead). kWh/day controls how many hours are needed. "
              "Without Smart, the load runs every hour in the window. "
              "Note: If you enter calibration data (Tibber Insights), the EV's kWh/day is automatically updated from real data.",
    },
    "add_load": {
        "sv": "+ Last",
        "en": "+ Load",
    },
    "flexible_loads": {
        "sv": "**Flexibla laster** (solöverskott)",
        "en": "**Flexible loads** (solar surplus)",
    },
    "flexible_caption": {
        "sv": "Körs på solöverskott istället för att exportera till nät. "
              "Varmvatten-element tar upp överskott när batteriet är fullt.",
        "en": "Runs on solar surplus instead of exporting to grid. "
              "Hot water tank absorbs surplus when the battery is full.",
    },
    "add_flex_load": {
        "sv": "+ Flexibel last",
        "en": "+ Flexible load",
    },

    # ---- Heating ----
    "heating_header": {
        "sv": "Uppvärmning",
        "en": "Heating",
    },
    "heating_model_label": {
        "sv": "Temperaturanpassad lastmodell",
        "en": "Temperature-dependent load model",
    },
    "heating_model_help": {
        "sv": "Modellerar värmepumpens elförbrukning baserat på väderdata och husets egenskaper",
        "en": "Models heat pump electricity use based on weather data and house properties",
    },
    "location_header": {
        "sv": "**Plats (för väderdata)**",
        "en": "**Location (for weather data)**",
    },
    "city_label": {
        "sv": "Stad / ort",
        "en": "City / town",
    },
    "city_help": {
        "sv": "Välj den ort som är närmast dig. Hämtas automatiskt från Tibber om tillgänglig.",
        "en": "Choose the city closest to you. Auto-detected from Tibber if available.",
    },
    "your_house": {
        "sv": "**Ditt hus**",
        "en": "**Your house**",
    },
    "energy_class": {
        "sv": "Energiklass (energideklaration)",
        "en": "Energy class (energy certificate)",
    },
    "energy_class_help": {
        "sv": "Finns i husets energideklaration. Vet du inte? Klass C-D är vanligast för hus byggda 1990-2020.",
        "en": "Found in your house energy certificate. Don't know? Class C-D is most common for houses built 1990-2020.",
    },
    "house_area": {
        "sv": "Boyta (m²)",
        "en": "Living area (m²)",
    },
    "heating_type": {
        "sv": "Uppvärmning",
        "en": "Heating type",
    },
    "heating_type_help": {
        "sv": "Hämtas från Tibber om tillgänglig. Påverkar COP-beräkningen.",
        "en": "Auto-detected from Tibber if available. Affects COP calculation.",
    },
    "heating_options": {
        "sv": ["Bergvärme (mark/sjö)", "Luftvärmepump", "Fjärrvärme", "Direktel (element)"],
        "en": ["Ground source HP", "Air source HP", "District heating", "Direct electric"],
    },
    "aa_label": {
        "sv": "Luft-luft komplement (AC + uppvärmning)",
        "en": "Air-to-air HP supplement (AC + heating)",
    },

    # ---- Step 3: Investment ----
    "step3_header": {
        "sv": "3. Investering",
        "en": "3. Investment",
    },
    "battery_prices": {
        "sv": "Batteripriser",
        "en": "Battery prices",
    },
    "pricing_mode": {
        "sv": "Prismodell",
        "en": "Pricing mode",
    },
    "specific_batteries": {
        "sv": "Specificerade batterier (NKON)",
        "en": "Specific batteries (NKON)",
    },
    "sek_per_kwh_mode": {
        "sv": "SEK per kWh — hitta optimal storlek",
        "en": "SEK per kWh — find optimal size",
    },
    "battery_price_kwh": {
        "sv": "Batteripris (SEK/kWh)",
        "en": "Battery price (SEK/kWh)",
    },
    "max_charge_kw": {
        "sv": "Max ladd/urladdning (kW)",
        "en": "Max charge/discharge (kW)",
    },
    "step_kwh": {
        "sv": "Steg (kWh)",
        "en": "Step (kWh)",
    },
    "eur_sek_rate": {
        "sv": "EUR/SEK växelkurs",
        "en": "EUR/SEK exchange rate",
    },
    "battery_install": {
        "sv": "Installation batteri (SEK)",
        "en": "Battery installation (SEK)",
    },
    "solar_material": {
        "sv": "Solceller material (SEK)",
        "en": "Solar panels material (SEK)",
    },
    "solar_install": {
        "sv": "Sol-installation arbete (SEK)",
        "en": "Solar installation labor (SEK)",
    },
    "financing": {
        "sv": "Finansiering",
        "en": "Financing",
    },
    "own_capital": {
        "sv": "Eget kapital",
        "en": "Own capital",
    },
    "mortgage": {
        "sv": "Bolån",
        "en": "Mortgage",
    },
    "other_loan": {
        "sv": "Annat lån",
        "en": "Other loan",
    },
    "mortgage_rate": {
        "sv": "Bolåneränta (%)",
        "en": "Mortgage rate (%)",
    },
    "loan_term": {
        "sv": "Löptid (år)",
        "en": "Loan term (years)",
    },
    "interest_rate": {
        "sv": "Ränta (%)",
        "en": "Interest rate (%)",
    },
    "loan_years": {
        "sv": "Lånetid (år)",
        "en": "Loan period (years)",
    },

    # ---- Step 4: Results ----
    "step4_header": {
        "sv": "4. Resultat",
        "en": "4. Results",
    },
    "step4_caption": {
        "sv": "Tryck på knappen nedan för att simulera alla batteristorlekar. "
              "Simuleringen testar alla tariffer och väljer den bästa för varje storlek.",
        "en": "Press the button below to simulate all battery sizes. "
              "The simulation tests all tariffs and picks the best for each size.",
    },
    "run_simulation": {
        "sv": "KÖR SIMULERING",
        "en": "RUN SIMULATION",
    },
    "simulating": {
        "sv": "Simulerar",
        "en": "Simulating",
    },
    "recommendation": {
        "sv": "Rekommendation",
        "en": "Recommendation",
    },
    "best_tariff": {
        "sv": "Bästa tariff",
        "en": "Best tariff",
    },
    "lower_cost_yr": {
        "sv": "lägre elkostnad",
        "en": "lower electricity cost",
    },
    "investment": {
        "sv": "investering",
        "en": "investment",
    },
    "payback_in": {
        "sv": "återbetald på",
        "en": "payback in",
    },
    "net_over": {
        "sv": "netto",
        "en": "net",
    },
    "years": {
        "sv": "år",
        "en": "years",
    },
    "yr": {
        "sv": "år",
        "en": "yr",
    },
    "month_short": {
        "sv": "mån",
        "en": "mo",
    },
    "scenario_header": {
        "sv": "Scenariojämförelse",
        "en": "Scenario comparison",
    },
    "scenario_caption": {
        "sv": "Samma simulering — uppdelad per år. Elpriser varierar kraftigt mellan år.",
        "en": "Same simulation — split by year. Electricity prices vary significantly between years.",
    },
    "compare_all_header": {
        "sv": "Jämförelse alla batteristorlekar",
        "en": "Comparison of all battery sizes",
    },
    "compare_all_caption": {
        "sv": "Investeringen fördelad över batteriets livslängd jämförd med årlig besparing. Samma tidsskala.",
        "en": "Investment spread over battery lifetime compared with annual savings. Same timescale.",
    },
    "investment_cost_yr": {
        "sv": "Investeringskostnad per år",
        "en": "Investment cost per year",
    },
    "savings_yr": {
        "sv": "Lägre elkostnad per år",
        "en": "Lower electricity cost per year",
    },
    "financing_header": {
        "sv": "Finansiering — netto per månad",
        "en": "Financing — net per month",
    },
    "no_results": {
        "sv": "Inga resultat att visa.",
        "en": "No results to display.",
    },

    # ---- Spread expander ----
    "spread_expander": {
        "sv": "Prisspridning — lägsta till högsta: typiskt {median} öre, bra dagar {p80} öre",
        "en": "Price spread — lowest to highest: typically {median} öre, good days {p80} öre",
    },

    # ---- Fuse comparison ----
    "fuse_header": {
        "sv": "Lönar sig en större säkring?",
        "en": "Is a larger fuse worth it?",
    },

    # ---- Step 5: Detail ----
    "step5_header": {
        "sv": "5. Detaljvy",
        "en": "5. Detail view",
    },
    "show_details_for": {
        "sv": "Visa detaljer för:",
        "en": "Show details for:",
    },
    "lower_cost": {
        "sv": "Lägre elkostnad",
        "en": "Lower electricity cost",
    },
    "per_year": {
        "sv": "Per år",
        "en": "Per year",
    },
    "payback": {
        "sv": "Payback",
        "en": "Payback",
    },
    "cycles_yr": {
        "sv": "Cykler/år",
        "en": "Cycles/yr",
    },
    "typical_year": {
        "sv": "Typiskt år — skillnad i elkostnad per månad",
        "en": "Typical year — electricity cost difference per month",
    },

    # ---- Step 6: Future scenarios ----
    "step6_header": {
        "sv": "6. Framtidsprognos",
        "en": "6. Future outlook",
    },
    "step6_caption": {
        "sv": "Tre scenarier baserat på hur elprisernas volatilitet utvecklas. "
              "Mer förnybart i elnätet ger större prisskillnader mellan timmar — "
              "det är vad batteriet tjänar på.",
        "en": "Three scenarios based on how electricity price volatility develops. "
              "More renewables in the grid creates larger price swings between hours — "
              "this is what the battery profits from.",
    },
    "conservative": {
        "sv": "Konservativt",
        "en": "Conservative",
    },
    "likely": {
        "sv": "Sannolikt",
        "en": "Likely",
    },
    "high_volatility": {
        "sv": "Hög volatilitet",
        "en": "High volatility",
    },
    "conservative_desc": {
        "sv": "Prissvängningarna ökar 50% på 10 år. Måttlig utbyggnad av förnybart.",
        "en": "Price swings increase 50% over 10 years. Moderate renewable expansion.",
    },
    "likely_desc": {
        "sv": "Prissvängningarna 2-3x på 10 år. Fortsatt utbyggnad av vind/sol, fler elbilar, elektrifiering av industri. De flesta energianalytiker förväntar sig detta.",
        "en": "Price swings 2-3x over 10 years. Continued wind/solar expansion, more EVs, industry electrification. Most energy analysts expect this.",
    },
    "high_volatility_desc": {
        "sv": "Prissvängningarna 4x. Massiv utbyggnad av förnybart, kärnkraft fasas ut, ökad europeisk sammankoppling.",
        "en": "Price swings 4x. Massive renewable buildout, nuclear phase-out, increased European interconnection.",
    },
    "year_forecast": {
        "sv": "15-årsprognos",
        "en": "15-year forecast",
    },

    # ---- Months ----
    "months": {
        "sv": ["", "Jan", "Feb", "Mar", "Apr", "Maj", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"],
        "en": ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    },

    # ---- Common labels ----
    "kr_yr": {
        "sv": "kr/år",
        "en": "SEK/yr",
    },
    "kr_month": {
        "sv": "kr/mån",
        "en": "SEK/mo",
    },
    "kwh_yr": {
        "sv": "kWh/år",
        "en": "kWh/yr",
    },
    "details": {
        "sv": "Detaljer",
        "en": "Details",
    },
    "download_pdf": {
        "sv": "Ladda ner PDF-rapport (bankunderlag)",
        "en": "Download PDF report (bank documentation)",
    },
    "diy_header": {
        "sv": "Systemdesign — DIY utan export",
        "en": "System Design — DIY Zero Export",
    },
    "diy_intro": {
        "sv": "En kostnadseffektiv design som separerar laddning (billig, hög effekt) från urladdning (smart, nollexport). Kräver ingen mikroproducentregistrering.",
        "en": "A cost-effective design that separates charging (cheap, high power) from discharging (smart, zero export). No microproducer registration needed.",
    },
}


def set_language(lang: str):
    """Set the current language ('sv' or 'en')."""
    global _lang
    _lang = lang


def get_language() -> str:
    """Get the current language."""
    return _lang


def t(key: str) -> str:
    """Get translated string for the current language."""
    entry = STRINGS.get(key)
    if entry is None:
        return f"[{key}]"
    return entry.get(_lang, entry.get("sv", f"[{key}]"))
