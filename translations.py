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
    "fuse_overcurrent_header": {
        "sv": "⚡ Säkringsmarginal (IEC 60269, DIAZED trög)",
        "en": "⚡ Fuse overcurrent margin (IEC 60269, DIAZED slow-blow)",
    },
    "fuse_overcurrent_caption": {
        "sv": "**Expertinställning.** DIAZED trög-säkringar (gG/gL) smälter inte omedelbart vid nominell ström. "
              "IEC 60269 specificerar två strömnivåer: Inf (1.25× In) där säkringen garanterat INTE "
              "smälter inom 1 timme, och If (1.6× In) där den MÅSTE smälta inom 1 timme. "
              "Detta påverkar hur mycket laddeffekt som är tillgänglig utöver hushållets last.",
        "en": "**Expert setting.** DIAZED slow-blow fuses (gG/gL) don't melt instantly at rated current. "
              "IEC 60269 specifies two current levels: Inf (1.25× In) where the fuse is guaranteed NOT "
              "to blow within 1 hour, and If (1.6× In) where it MUST blow within 1 hour. "
              "This affects how much charging power is available beyond household load.",
    },
    "fuse_overcurrent_label": {
        "sv": "Överströmsmarginal",
        "en": "Overcurrent margin",
    },
    "fuse_oc_nominal": {
        "sv": "Nominell — exakt säkringsvärde (konservativ)",
        "en": "Nominal — exact fuse rating (conservative)",
    },
    "fuse_oc_safe": {
        "sv": "1.25× In — garanterat ingen smältning (Inf, 1h)",
        "en": "1.25× In — guaranteed no blow (Inf, 1h)",
    },
    "fuse_oc_aggressive": {
        "sv": "1.6× In — kan smälta inom 1h (If, riskabelt)",
        "en": "1.6× In — may blow within 1h (If, risky)",
    },
    "fuse_overcurrent_help": {
        "sv": "IEC 60269 definierar två trösklar för DIAZED trög-säkringar (gG/gL):\n"
              "• 1.25× In (Inf): konventionell icke-smältström — smälter INTE inom 1 timme\n"
              "• 1.6× In (If): konventionell smältström — MÅSTE smälta inom 1 timme\n\n"
              "Batteriladdning sker i block om 1-3 timmar, så 1.25× är säker i praktiken. "
              "1.6× riskerar att säkringen går vid långa laddpass.",
        "en": "IEC 60269 defines two thresholds for DIAZED slow-blow fuses (gG/gL):\n"
              "• 1.25× In (Inf): conventional non-fusing current — will NOT blow within 1 hour\n"
              "• 1.6× In (If): conventional fusing current — MUST blow within 1 hour\n\n"
              "Battery charging happens in 1-3 hour blocks, so 1.25× is safe in practice. "
              "1.6× risks blowing the fuse during long charge sessions.",
    },
    "fuse_overcurrent_warning": {
        "sv": "⚠️ Säkring {fuse:.0f}A × {factor:.2f} = **{effective:.1f}A effektiv**. "
              "Detta är inte ett standardvärde — var medveten om att säkringen kan smälta vid hög last.",
        "en": "⚠️ Fuse {fuse:.0f}A × {factor:.2f} = **{effective:.1f}A effective**. "
              "This is not a default setting — be aware the fuse may blow under high load.",
    },
    "fuse_overcurrent_sim_note": {
        "sv": "Simuleringen använder DIAZED-marginal {factor:.2f}× på din {fuse:.0f}A säkring → "
              "**{effective:.1f}A effektiv** ({eff_kw:.1f} kW istället för {nom_kw:.1f} kW). "
              "Det ger **+{extra_kw:.1f} kW** extra laddkapacitet utan säkringsbyte.",
        "en": "Simulation uses DIAZED margin {factor:.2f}× on your {fuse:.0f}A fuse → "
              "**{effective:.1f}A effective** ({eff_kw:.1f} kW instead of {nom_kw:.1f} kW). "
              "That gives **+{extra_kw:.1f} kW** extra charging capacity without upgrading the fuse.",
    },
    "fuse_overcurrent_no_upgrade": {
        "sv": "Din {fuse:.0f}A DIAZED-säkring räcker med {factor:.2f}× marginal "
              "({effective:.1f}A effektiv, +{extra_kw:.1f} kW). Inget säkringsbyte behövs — "
              "du sparar den extra årsavgiften för en större säkring.",
        "en": "Your {fuse:.0f}A DIAZED fuse is sufficient with {factor:.2f}× margin "
              "({effective:.1f}A effective, +{extra_kw:.1f} kW). No fuse upgrade needed — "
              "you save the extra yearly fee for a larger fuse.",
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
              "OBS: Kalibrerad elbilsdata (Tibber Insights) används i simuleringen oavsett vad som anges i kWh/dag här.",
        "en": "Set a wide time window and enable Smart to pick the cheapest hours "
              "(spot prices known day-ahead). kWh/day controls how many hours are needed. "
              "Without Smart, the load runs every hour in the window. "
              "Note: Calibrated EV data (Tibber Insights) is used in the simulation regardless of the kWh/day value set here.",
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
    "heating_header": {
        "sv": "Uppvärmning",
        "en": "Heating",
    },
    "heating_checkbox": {
        "sv": "Temperaturanpassad lastmodell",
        "en": "Temperature-dependent load model",
    },
    "heating_checkbox_help": {
        "sv": "Modellerar värmepumpens elförbrukning baserat på väderdata och husets egenskaper",
        "en": "Models heat pump electricity consumption based on weather data and house properties",
    },
    "heating_caption": {
        "sv": "Modellen beräknar husets elförbrukning för uppvärmning timme för timme, "
              "baserat på **verklig temperatur** från SMHI och **husets egenskaper** (energiklass, yta, värmepumptyp). "
              "Kall timme = hög förbrukning = mer egenanvändning av sol/batteri. "
              "Varm timme = låg förbrukning = mer överskott. "
              "Har du laddat förbrukningsdata (Tibber/Vattenfall) kalibreras modellen automatiskt mot din verkliga förbrukning.",
        "en": "The model calculates hourly heating electricity consumption based on "
              "**real temperature** from SMHI and **house properties** (energy class, area, heat pump type). "
              "Cold hour = high consumption = more self-use of solar/battery. "
              "Warm hour = low consumption = more surplus. "
              "If consumption data is loaded (Tibber/Vattenfall), the model auto-calibrates to your actual usage.",
    },
    "heating_location": {
        "sv": "**Plats (för väderdata)**",
        "en": "**Location (for weather data)**",
    },
    "city_label": {
        "sv": "Stad / ort",
        "en": "City / town",
    },
    "city_help": {
        "sv": "Välj den ort som är närmast dig. Hämtas automatiskt från Tibber om tillgänglig.",
        "en": "Choose the town closest to you. Auto-filled from Tibber if available.",
    },
    "loc_source_tibber": {
        "sv": "exakta koordinater från Tibber",
        "en": "exact coordinates from Tibber",
    },
    "loc_source_city": {
        "sv": "stadscentrum",
        "en": "city center",
    },
    "nearest_station": {
        "sv": "Närmaste SMHI-station: **{name}** ({dist:.0f} km, baserat på {source})",
        "en": "Nearest SMHI station: **{name}** ({dist:.0f} km, based on {source})",
    },
    "choose_other_station": {
        "sv": "Välj annan station",
        "en": "Choose another station",
    },
    "station_label": {
        "sv": "Station",
        "en": "Station",
    },
    "fetching_weather": {
        "sv": "Hämtar väderdata från {name}...",
        "en": "Fetching weather data from {name}...",
    },
    "weather_fetch_error": {
        "sv": "Kunde inte hämta väderdata: {error}",
        "en": "Could not fetch weather data: {error}",
    },
    "your_house": {
        "sv": "**Ditt hus**",
        "en": "**Your house**",
    },
    "house_calibration_help": {
        "sv": "Välj energiklass och yta för att uppskatta värmeförlust. Har du förbrukningsdata (Tibber/Vattenfall) kalibreras modellen automatiskt.",
        "en": "Choose energy class and area to estimate heat loss. If consumption data is loaded (Tibber/Vattenfall), the model auto-calibrates.",
    },
    "energy_class_label": {
        "sv": "Energiklass (energideklaration)",
        "en": "Energy class (energy declaration)",
    },
    "energy_class_help": {
        "sv": "Finns i husets energideklaration. Vet du inte? Klass C-D är vanligast för hus byggda 1990-2020.",
        "en": "Found in your home's energy declaration. Not sure? Class C-D is most common for homes built 1990-2020.",
    },
    "house_area_label": {
        "sv": "Boyta (m²)",
        "en": "Living area (m²)",
    },
    "house_area_help": {
        "sv": "Hämtas från Tibber om tillgänglig.",
        "en": "Auto-filled from Tibber if available.",
    },
    "heating_ground": {
        "sv": "Bergvärme (mark/sjö)",
        "en": "Ground source (borehole/lake)",
    },
    "heating_airsource": {
        "sv": "Luftvärmepump",
        "en": "Air source heat pump",
    },
    "heating_district": {
        "sv": "Fjärrvärme",
        "en": "District heating",
    },
    "heating_electric": {
        "sv": "Direktel (element)",
        "en": "Direct electric (radiators)",
    },
    "heating_label": {
        "sv": "Uppvärmning",
        "en": "Heating",
    },
    "heating_type_help": {
        "sv": "Hämtas från Tibber om tillgänglig. Påverkar COP-beräkningen.",
        "en": "Auto-filled from Tibber if available. Affects COP calculation.",
    },
    "cop_ground": {
        "sv": "COP ~3.2–3.5 (nära konstant, brintemp varierar inte med utetemperatur)",
        "en": "COP ~3.2–3.5 (nearly constant, brine temp unaffected by outdoor temperature)",
    },
    "cop_airsource": {
        "sv": "COP 1.5–4.5, sämre vid kyla",
        "en": "COP 1.5–4.5, worse in cold weather",
    },
    "cop_district": {
        "sv": "Ingen VP — elkostnad för cirkulationspump",
        "en": "No heat pump — electricity cost for circulation pump only",
    },
    "cop_electric": {
        "sv": "COP = 1.0 (ren eluppvärmning)",
        "en": "COP = 1.0 (pure electric heating)",
    },
    "aa_checkbox": {
        "sv": "Luft-luft komplement (AC + uppvärmning)",
        "en": "Air-to-air supplement (AC + heating)",
    },
    "aa_help": {
        "sv": "Luft-luft VP som komplement: AC på sommaren, uppvärmning när utetemperaturen är tillräckligt hög.",
        "en": "Air-to-air heat pump as supplement: AC in summer, heating when outdoor temperature is high enough.",
    },
    "detailed_hp_settings": {
        "sv": "Detaljerade VP-inställningar",
        "en": "Detailed heat pump settings",
    },
    "hloss_calibrated": {
        "sv": "Kalibrerat {value:.3f} kW/°C från din förbrukningsdata.",
        "en": "Calibrated {value:.3f} kW/°C from your consumption data.",
    },
    "hloss_estimated": {
        "sv": "Uppskattat {value:.3f} kW/°C från energiklass + yta. Ladda förbrukningsdata eller fyll i Tibber Insikter för exakt kalibrering.",
        "en": "Estimated {value:.3f} kW/°C from energy class + area. Load consumption data or enter Tibber Insights for exact calibration.",
    },
    "hloss_label": {
        "sv": "Värmeförlust (kW/°C)",
        "en": "Heat loss (kW/°C)",
    },
    "calibration_note": {
        "sv": "Kalibrerat mot verklig förbrukning. Energiklass, yta och VP-inställningar nedan påverkar inte simuleringen.",
        "en": "Calibrated against actual consumption. Energy class, area, and heat pump settings below do not affect the simulation.",
    },
    "hp_max_label": {
        "sv": "VP max värmeeffekt (kW)",
        "en": "Heat pump max heating power (kW)",
    },
    "hp_max_help": {
        "sv": "Uppskattat {hp_max} kW för {area} m². Typiskt 4-8 kW för villa, 8-12 kW för större hus.",
        "en": "Estimated {hp_max} kW for {area} m². Typically 4-8 kW for houses, 8-12 kW for larger homes.",
    },
    "elpatron_label": {
        "sv": "Elpatron (kW)",
        "en": "Backup heater (kW)",
    },
    "elpatron_help": {
        "sv": "Tillsatsvärme vid extremkyla. 0 om ingen.",
        "en": "Supplemental heating in extreme cold. 0 if none.",
    },
    "dhw_label": {
        "sv": "Varmvatten (kWh el/dag)",
        "en": "Hot water (kWh elec/day)",
    },
    "dhw_help": {
        "sv": "Uppskattat {dhw} kWh/dag för {area} m². Beror på antal personer (~2 kWh/person/dag via VP).",
        "en": "Estimated {dhw} kWh/day for {area} m². Depends on number of residents (~2 kWh/person/day via heat pump).",
    },
    # ---- Data loading status messages ----
    "tibber_grid": {
        "sv": "Nät: {grid}",
        "en": "Grid: {grid}",
    },
    "tibber_fuse": {
        "sv": "Säkring: {fuse}A",
        "en": "Fuse: {fuse}A",
    },
    "tibber_area": {
        "sv": "Yta: {area} m²",
        "en": "Area: {area} m²",
    },
    "tibber_solar_yearly": {
        "sv": "Sol: {kwh} kWh/år",
        "en": "Solar: {kwh} kWh/yr",
    },
    "heating_ground": {
        "sv": "Bergvärme",
        "en": "Ground-source HP",
    },
    "heating_air2air": {
        "sv": "Luft-luft",
        "en": "Air-to-air HP",
    },
    "heating_air2water": {
        "sv": "Luft-vatten",
        "en": "Air-to-water HP",
    },
    "heating_district": {
        "sv": "Fjärrvärme",
        "en": "District heating",
    },
    "heating_electric": {
        "sv": "Direktel",
        "en": "Direct electric",
    },
    "heating_other": {
        "sv": "Övrigt",
        "en": "Other",
    },
    "eon_install_help": {
        "sv": "Ditt E.ON installations-ID (finns på fakturan)",
        "en": "Your E.ON installation ID (found on the invoice)",
    },
    "eon_missing_id": {
        "sv": "Ange installations-ID",
        "en": "Enter installation ID",
    },
    "eon_fetching": {
        "sv": "Hämtar förbrukningsdata från E.ON...",
        "en": "Fetching consumption data from E.ON...",
    },
    "eon_loaded": {
        "sv": "E.ON data laddad: {count} timvärden ({days} dagar), {kwh} kWh",
        "en": "E.ON data loaded: {count} hourly values ({days} days), {kwh} kWh",
    },
    "eon_no_data": {
        "sv": "Inga data returnerades. Kontrollera installations-ID.",
        "en": "No data returned. Check installation ID.",
    },
    "eon_error": {
        "sv": "E.ON-fel: {error}",
        "en": "E.ON error: {error}",
    },
    "hourly_data_loaded": {
        "sv": "Timdata laddad: **{count} timvärden** ({days} dagar) | Snitt: {avg_day:.0f} kWh/dag | ~{avg_year} kWh/år",
        "en": "Hourly data loaded: **{count} values** ({days} days) | Avg: {avg_day:.0f} kWh/day | ~{avg_year} kWh/yr",
    },
    "daily_data_loaded": {
        "sv": "Daglig data laddad: **{days} dagar** | Snitt: {avg_day:.0f} kWh/dag | ~{avg_year} kWh/år",
        "en": "Daily data loaded: **{days} days** | Avg: {avg_day:.0f} kWh/day | ~{avg_year} kWh/yr",
    },
    "csv_data_loaded": {
        "sv": "Förbrukning laddad: **{count} datapunkter**",
        "en": "Consumption loaded: **{count} data points**",
    },
    "import_error": {
        "sv": "Importfel: {error}",
        "en": "Import error: {error}",
    },
    "consumption_hourly_info": {
        "sv": "Förbrukningsdata: **{count} timvärden** ({days} dagar) | Snitt: {avg_day:.0f} kWh/dag | ~{avg_year} kWh/år",
        "en": "Consumption data: **{count} values** ({days} days) | Avg: {avg_day:.0f} kWh/day | ~{avg_year} kWh/yr",
    },
    "consumption_profile_range": {
        "sv": "Förbrukningsprofil laddad: {min_kw}–{max_kw} kW",
        "en": "Consumption profile loaded: {min_kw}–{max_kw} kW",
    },
    "consumption_profile_avg": {
        "sv": "Förbrukningsprofil laddad: medel {avg:.1f} kW",
        "en": "Consumption profile loaded: avg {avg:.1f} kW",
    },
    "price_source_help": {
        "sv": "API hämtar från elprisetjustnu.se. CSV om du har en egen fil.",
        "en": "API fetches from elprisetjustnu.se. CSV if you have your own file.",
    },
    "price_csv_label": {
        "sv": "Pris-CSV",
        "en": "Price CSV",
    },
    "price_csv_help": {
        "sv": "CSV med kolumner: date, hour, sek_per_kwh",
        "en": "CSV with columns: date, hour, sek_per_kwh",
    },
    "date_range_synced": {
        "sv": "Datumintervall anpassat till Vattenfall-data ({start} — {end})",
        "en": "Date range synced with Vattenfall data ({start} — {end})",
    },
    "no_prices_found": {
        "sv": "Inga priser hittades. Kontrollera datum och elområde.",
        "en": "No prices found. Check dates and price zone.",
    },
    "price_data_loaded": {
        "sv": "Prisdata laddad: **{days} dagar** ({start} → {end})",
        "en": "Price data loaded: **{days} days** ({start} → {end})",
    },
    "price_date_mismatch": {
        "sv": "Prisdata ({p_start} — {p_end}) täcker inte hela förbrukningsperioden ({c_start} — {c_end}). Hämta priser för samma period för bästa resultat.",
        "en": "Price data ({p_start} — {p_end}) does not cover the full consumption period ({c_start} — {c_end}). Fetch prices for the same period for best results.",
    },
    "prices_loaded_no_consumption": {
        "sv": "**Prisdata laddad.** Förbrukningsprofil saknas — standardvärden används. Konfigurera din anläggning nedan.",
        "en": "**Price data loaded.** No consumption profile — default values used. Configure your system below.",
    },

    # ---- Units ----
    "kwh_yr": {
        "sv": "kWh/år",
        "en": "kWh/yr",
    },
    "kr_yr": {
        "sv": "kr/år",
        "en": "SEK/yr",
    },
    "yr_unit": {
        "sv": "år",
        "en": "yr",
    },

    # ---- Energy class labels ----
    "eclass_a": {
        "sv": "A (≤50 kWh/m²) — Passivhus",
        "en": "A (≤50 kWh/m²) — Passive house",
    },
    "eclass_b": {
        "sv": "B (51-75 kWh/m²) — Nybyggt",
        "en": "B (51-75 kWh/m²) — New build",
    },
    "eclass_c": {
        "sv": "C (76-100 kWh/m²) — Bra renoverat",
        "en": "C (76-100 kWh/m²) — Well renovated",
    },
    "eclass_d": {
        "sv": "D (101-130 kWh/m²) — Standard 1990-2010",
        "en": "D (101-130 kWh/m²) — Standard 1990-2010",
    },
    "eclass_e": {
        "sv": "E (131-160 kWh/m²) — Äldre hus",
        "en": "E (131-160 kWh/m²) — Older house",
    },
    "eclass_f": {
        "sv": "F (161-190 kWh/m²) — Dåligt isolerat",
        "en": "F (161-190 kWh/m²) — Poorly insulated",
    },
    "eclass_g": {
        "sv": "G (>190 kWh/m²) — Mycket dåligt isolerat",
        "en": "G (>190 kWh/m²) — Very poorly insulated",
    },

    # ---- Air-to-air presets & labels ----
    "aa_model_label": {
        "sv": "Modell",
        "en": "Model",
    },
    "aa_preset_custom": {
        "sv": "Anpassad",
        "en": "Custom",
    },
    "aa_preset_hero_info": {
        "sv": "23,990 kr + ~6,000 installation. 6.3 kW max värme, -35°C till +31°C.",
        "en": "23,990 SEK + ~6,000 installation. 6.3 kW max heating, -35°C to +31°C.",
    },
    "aa_preset_custom_info": {
        "sv": "Fyll i egna värden.",
        "en": "Enter your own values.",
    },
    "aa_heat_kw_label": {
        "sv": "Luft-luft värmeeffekt (kW)",
        "en": "Air-to-air heating capacity (kW)",
    },
    "aa_heat_kw_help": {
        "sv": "Nominell värmeeffekt.",
        "en": "Nominal heating capacity.",
    },
    "aa_min_temp_label": {
        "sv": "Min utetemperatur för drift (°C)",
        "en": "Min outdoor temp for operation (°C)",
    },
    "aa_min_temp_help": {
        "sv": "Under denna temperatur stängs luft-luft av.",
        "en": "Below this temperature the air-to-air HP is turned off.",
    },
    "aa_cool_kw_label": {
        "sv": "Luft-luft kyleffekt (kW)",
        "en": "Air-to-air cooling capacity (kW)",
    },
    "aa_cool_kw_help": {
        "sv": "Nominell kyleffekt.",
        "en": "Nominal cooling capacity.",
    },
    "aa_cool_threshold_label": {
        "sv": "Kylning startar vid (°C ute)",
        "en": "Cooling starts at (°C outdoor)",
    },
    "aa_cool_threshold_help": {
        "sv": "Utetemperatur då AC startar.",
        "en": "Outdoor temperature when AC starts.",
    },
    "aa_price_label": {
        "sv": "Pris inkl installation (SEK)",
        "en": "Price incl. installation (SEK)",
    },
    "aa_lifetime_label": {
        "sv": "Livslängd (år)",
        "en": "Lifetime (years)",
    },

    # ---- Base load (non-heat) ----
    "base_no_heat_label": {
        "sv": "Bas utan värme/EV (kW)",
        "en": "Base excl. heating/EV (kW)",
    },
    "base_no_heat_help": {
        "sv": "Uppskattat {base} kW för {area} m². Belysning, kyl/frys, ventilation, etc.",
        "en": "Estimated {base} kW for {area} m². Lighting, fridge/freezer, ventilation, etc.",
    },

    # ---- Heating summary caption ----
    "heating_summary_caption": {
        "sv": "Uppskattat: energiklass {eclass}, {area} m², h_loss = {hloss} kW/°C | Väderdata: {days} dagar ({start} — {end})",
        "en": "Estimated: energy class {eclass}, {area} m², h_loss = {hloss} kW/°C | Weather data: {days} days ({start} — {end})",
    },

    # ---- Air-to-air investment expander ----
    "aa_investment_header": {
        "sv": "Luft-luft investering",
        "en": "Air-to-air HP investment",
    },
    "aa_heat_saving": {
        "sv": "Värmebesparing",
        "en": "Heating savings",
    },
    "aa_heat_saving_help": {
        "sv": "Minskad elförbrukning för uppvärmning tack vare luft-luft",
        "en": "Reduced electricity use for heating thanks to air-to-air HP",
    },
    "aa_ac_consumption": {
        "sv": "AC-förbrukning",
        "en": "AC consumption",
    },
    "aa_ac_consumption_help": {
        "sv": "Tillkommande elförbrukning för kylning",
        "en": "Additional electricity use for cooling",
    },
    "aa_net_saving": {
        "sv": "Nettobesparing",
        "en": "Net savings",
    },
    "aa_net_saving_help": {
        "sv": "Värmebesparing minus AC-kostnad (vid ~60 öre/kWh snitt)",
        "en": "Heating savings minus AC cost (at ~60 öre/kWh average)",
    },
    "aa_payback": {
        "sv": "Återbetalningstid",
        "en": "Payback period",
    },
    "aa_payback_na_help": {
        "sv": "AC-kostnaden överstiger värmebesparingen. Investeringen motiveras av komfort, inte besparing.",
        "en": "AC cost exceeds heating savings. The investment is justified by comfort, not savings.",
    },
    "aa_invest_positive": {
        "sv": "Investering {price} kr → netto **{profit} kr** under {years} år ({monthly} kr/mån)",
        "en": "Investment {price} SEK → net **{profit} SEK** over {years} years ({monthly} SEK/month)",
    },
    "aa_invest_comfort": {
        "sv": "Luft-luft sparar {saving_kwh} kWh/år på uppvärmning men AC-driften kostar {cooling_kwh} kWh/år. Investeringen motiveras av komfort (AC), inte elbesparing.",
        "en": "Air-to-air HP saves {saving_kwh} kWh/yr on heating but AC operation costs {cooling_kwh} kWh/yr. The investment is justified by comfort (AC), not electricity savings.",
    },

    # ---- Calibration expander ----
    "cal_expander": {
        "sv": "Kalibrera mot din förbrukning",
        "en": "Calibrate against your consumption",
    },
    "cal_caption": {
        "sv": "Fyll i din årsförbrukning uppdelad per kategori för exakt kalibrering. Hittas i din elapp: Tibber (Insikter), Greenely (Förbrukningsanalys), eller på din elnätsägares Mina sidor.",
        "en": "Enter your annual consumption by category for exact calibration. Found in your electricity app: Tibber (Insights), Greenely (Consumption Analysis), or on your grid operator's portal.",
    },
    "cal_year_label": {
        "sv": "År att kalibrera mot",
        "en": "Year to calibrate against",
    },
    "cal_total_label": {
        "sv": "Total förbrukning (kWh/år)",
        "en": "Total consumption (kWh/yr)",
    },
    "cal_total_help": {
        "sv": "Hela årets elförbrukning. Finns på elräkningen eller i din elapp.",
        "en": "Full year electricity consumption. Found on your bill or in your electricity app.",
    },
    "cal_heating_label": {
        "sv": "Uppvärmning + varmvatten (kWh/år)",
        "en": "Heating + hot water (kWh/yr)",
    },
    "cal_heating_help": {
        "sv": "Värmepump + varmvatten. Kallas 'Uppvärmning' i Tibber/Greenely.",
        "en": "Heat pump + hot water. Called 'Heating' in Tibber/Greenely.",
    },
    "cal_ev_label": {
        "sv": "Elbil (kWh/år)",
        "en": "EV charging (kWh/yr)",
    },
    "cal_ev_help": {
        "sv": "Laddning av elbil. 0 om ingen elbil.",
        "en": "EV charging. 0 if no EV.",
    },
    "cal_active_label": {
        "sv": "Matlagning, belysning etc (kWh/år)",
        "en": "Cooking, lighting, etc. (kWh/yr)",
    },
    "cal_active_help": {
        "sv": "Spis, ugn, belysning, tvätt, disk — det du aktivt använder.",
        "en": "Stove, oven, lighting, laundry, dishwasher — things you actively use.",
    },
    "cal_always_label": {
        "sv": "Alltid på (kWh/år)",
        "en": "Always on (kWh/yr)",
    },
    "cal_always_help": {
        "sv": "Kyl, frys, ventilation, standby — det som alltid drar.",
        "en": "Fridge, freezer, ventilation, standby — always-on loads.",
    },
    "cal_success": {
        "sv": "Kalibrerat mot {year}: **h_loss = {hloss} kW/°C**, bas = {base} kW (uppvärmning {heating} kWh, EV {ev} kWh, övrigt {other} kWh)",
        "en": "Calibrated against {year}: **h_loss = {hloss} kW/°C**, base = {base} kW (heating {heating} kWh, EV {ev} kWh, other {other} kWh)",
    },
    "cal_ev_updated": {
        "sv": "Elbilsladdning uppdaterad: {daily} kWh/dag (baserat på {annual} kWh/år från Tibber)",
        "en": "EV charging updated: {daily} kWh/day (based on {annual} kWh/yr from Tibber)",
    },
    "cal_insufficient_weather": {
        "sv": "Inte tillräckligt med väderdata för {year} ({days} dagar). Behöver minst 300.",
        "en": "Insufficient weather data for {year} ({days} days). Need at least 300.",
    },

    # ---- House consumption summary ----
    "house_consumption_summary": {
        "sv": "Husförbrukning (exkl. EV/pool): ~{annual} kWh/år | vinter ~{winter} kWh/dag, sommar ~{summer} kWh/dag",
        "en": "House consumption (excl. EV/pool): ~{annual} kWh/yr | winter ~{winter} kWh/day, summer ~{summer} kWh/day",
    },

    # ---- Spread analysis details ----
    "cheapest_hour_help": {
        "sv": "Genomsnittlig lägsta timpris per dag",
        "en": "Average lowest hourly price per day",
    },
    "most_expensive_hour_help": {
        "sv": "Genomsnittlig högsta timpris per dag",
        "en": "Average highest hourly price per day",
    },
    "typical_spread_help": {
        "sv": "Median skillnad mellan billigaste och dyraste timmen",
        "en": "Median difference between cheapest and most expensive hour",
    },
    "good_days_help": {
        "sv": "Skillnad på de 20% mest lönsamma dagarna",
        "en": "Spread on the 20% most profitable days",
    },
    "daily_spread_trace": {
        "sv": "Daglig skillnad (max-min)",
        "en": "Daily spread (max-min)",
    },
    "min_spread_annotation": {
        "sv": "Min spread för lönsamhet (~20 öre)",
        "en": "Min spread for profitability (~20 öre)",
    },
    "spread_yaxis": {
        "sv": "Prisskillnad (öre/kWh)",
        "en": "Price spread (öre/kWh)",
    },

    # ---- Solar config ----
    "zero_export_label": {
        "sv": "Nollexport (ingen försäljning till nät)",
        "en": "Zero export (no grid sales)",
    },
    "zero_export_help": {
        "sv": "Batteriet laddar ur bara för eget bruk. Kräver ingen mikroproducentregistrering. Avmarkera för att simulera med nätexport.",
        "en": "Battery discharges only for own use. No microproducer registration needed. Uncheck to simulate with grid export.",
    },
    "export_arb_label": {
        "sv": "Exportarbitrage-kapacitet (kWh)",
        "en": "Export arbitrage capacity (kWh)",
    },
    "export_arb_help": {
        "sv": "Extra batterikapacitet utöver egenförbrukning som används för ren prisarbitrage (köp billigt, sälj dyrt). 0 = ingen extra arbitrage. Sätts automatiskt om batteriet är större än vad huset behöver.",
        "en": "Extra battery capacity beyond self-consumption used for pure price arbitrage (buy low, sell high). 0 = no extra arbitrage. Set automatically if battery exceeds house needs.",
    },
    "pvgis_success": {
        "sv": "PVGIS: {count} timvärden ({years} år), ~{yearly} kWh/år",
        "en": "PVGIS: {count} hourly values ({years} years), ~{yearly} kWh/yr",
    },
    "pvgis_no_data": {
        "sv": "Inga data från PVGIS. Kontrollera koordinater.",
        "en": "No data from PVGIS. Check coordinates.",
    },
    "pvgis_error": {
        "sv": "PVGIS-fel: {error}",
        "en": "PVGIS error: {error}",
    },
    "solar_csv_loaded": {
        "sv": "Soldata laddad: {count} timvärden ({days} dagar), {total} kWh totalt",
        "en": "Solar data loaded: {count} hourly values ({days} days), {total} kWh total",
    },
    "solar_csv_parse_error": {
        "sv": "Kunde inte tolka soldata-CSV. Kontrollera format.",
        "en": "Could not parse solar CSV. Check the format.",
    },
    "solar_import_error": {
        "sv": "Importfel soldata: {error}",
        "en": "Solar import error: {error}",
    },
    "solar_source_comparison": {
        "sv": "{src}: {yearly} kWh/år (cos³-modell: {model} kWh/år)",
        "en": "{src}: {yearly} kWh/yr (cos³ model: {model} kWh/yr)",
    },

    # ---- Grid / tariff details ----
    "operator_info_effekt": {
        "sv": "**{operator}** — simulerar: {tariffs} ({rate} kr/kW/mån) och säkring {fuses}",
        "en": "**{operator}** — simulates: {tariffs} ({rate} kr/kW/month) and fuse {fuses}",
    },
    "operator_info_basic": {
        "sv": "**{operator}** — simulerar: {tariffs} och säkring {fuses}",
        "en": "**{operator}** — simulates: {tariffs} and fuse {fuses}",
    },
    "tariff_details": {
        "sv": "Tariffdetaljer",
        "en": "Tariff details",
    },
    "tidstariff_label": {
        "sv": "**Tidstariff**",
        "en": "**Time-of-use tariff**",
    },
    "tidstariff_caption": {
        "sv": "Höglast: jan-mar + nov-dec, vardagar 06-22 (ej helgdagar). Övrig tid: alla andra timmar.",
        "en": "Peak: Jan-Mar + Nov-Dec, weekdays 06-22 (excl. holidays). Off-peak: all other hours.",
    },
    "peak_rate_label": {
        "sv": "Höglast (öre/kWh)",
        "en": "Peak rate (öre/kWh)",
    },
    "offpeak_rate_label": {
        "sv": "Övrig tid (öre/kWh)",
        "en": "Off-peak (öre/kWh)",
    },
    "enkeltariff_label": {
        "sv": "**Enkeltariff**",
        "en": "**Flat tariff**",
    },
    "enkeltariff_caption": {
        "sv": "Samma avgift alla timmar, alla dagar.",
        "en": "Same rate all hours, all days.",
    },
    "flat_rate_label": {
        "sv": "Överföring (öre/kWh)",
        "en": "Transfer fee (öre/kWh)",
    },
    "effekttariff_label": {
        "sv": "**Effekttariff**",
        "en": "**Power demand tariff**",
    },
    "effekt_caption": {
        "sv": "Effektmätning: medel av {top_n} högsta toppar från olika dagar. Mätperiod: {peak_desc}{night_desc}.",
        "en": "Power measurement: average of {top_n} highest peaks from different days. Measurement period: {peak_desc}{night_desc}.",
    },
    "effekt_peak_all_hours": {
        "sv": "alla timmar",
        "en": "all hours",
    },
    "effekt_peak_weekday": {
        "sv": "vardagar {start}-{end}, nov-mar",
        "en": "weekdays {start}-{end}, Nov-Mar",
    },
    "effekt_peak_alldays": {
        "sv": "alla dagar",
        "en": "all days",
    },
    "effekt_night_discount": {
        "sv": ", natt (22-06) räknas till {pct:.0f}%",
        "en": ", night (22-06) counted at {pct:.0f}%",
    },
    "effekt_rate_label": {
        "sv": "Effektavgift (kr/kW/mån)",
        "en": "Power demand fee (kr/kW/month)",
    },
    "effekt_energy_label": {
        "sv": "Energiavgift (öre/kWh)",
        "en": "Energy rate (öre/kWh)",
    },
    "effekt_top_n_label": {
        "sv": "Antal toppar",
        "en": "Number of peaks",
    },
    "tariff_summary": {
        "sv": "Energiskatt: {tax} öre/kWh | Abonnemang {fuse}A: {monthly} kr/mån ({yearly} kr/år)",
        "en": "Energy tax: {tax} öre/kWh | Subscription {fuse}A: {monthly} kr/month ({yearly} kr/yr)",
    },

    # ---- Load input labels ----
    "load_from_hour": {
        "sv": "Från",
        "en": "From",
    },
    "load_to_hour": {
        "sv": "Till",
        "en": "To",
    },
    "load_kwh_day": {
        "sv": "kWh/dag",
        "en": "kWh/day",
    },
    "load_kwh_day_help": {
        "sv": "Energibehov per dag. 0 = kör alla timmar i fönstret.",
        "en": "Energy needed per day. 0 = run all hours in the window.",
    },
    "load_smart": {
        "sv": "Smart",
        "en": "Smart",
    },
    "load_smart_help": {
        "sv": "Välj billigaste timmarna inom fönstret (prisoptimerat)",
        "en": "Pick cheapest hours within the window (price-optimized)",
    },
    "load_remove": {
        "sv": "Ta bort",
        "en": "Remove",
    },
    "flex_max_kwh_day": {
        "sv": "Max kWh per dag",
        "en": "Max kWh per day",
    },
    "flex_active_from": {
        "sv": "Aktiv från",
        "en": "Active from",
    },
    "flex_active_to": {
        "sv": "Aktiv till",
        "en": "Active to",
    },
    "flex_max_kwh_help": {
        "sv": "Max energi per dag. {power} kW \u00d7 {hours}h = {total} kWh",
        "en": "Max energy per day. {power} kW \u00d7 {hours}h = {total} kWh",
    },
    "month_names": {
        "sv": ["Jan", "Feb", "Mar", "Apr", "Maj", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"],
        "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    },

    # ---- Scenario comparison (step 4 cont.) ----
    "scenario_battery": {
        "sv": "Batteri",
        "en": "Battery",
    },
    "scenario_normal": {
        "sv": "Normal ({years})",
        "en": "Normal ({years})",
    },
    "scenario_normal_monthly": {
        "sv": "Normal kr/mån",
        "en": "Normal SEK/mo",
    },
    "scenario_high": {
        "sv": "Höga priser ({years})",
        "en": "High prices ({years})",
    },
    "scenario_high_monthly": {
        "sv": "Höga kr/mån",
        "en": "High SEK/mo",
    },
    "scenario_avg_all": {
        "sv": "Snitt alla år",
        "en": "Average all years",
    },
    "scenario_partial": {
        "sv": "(del)",
        "en": "(partial)",
    },
    "scenario_yaxis": {
        "sv": "Lägre elkostnad (kr/år)",
        "en": "Lower electricity cost (SEK/yr)",
    },
    "scenario_info": {
        "sv": "**{label}**: Vid normala priser ({normal_years}) sparar du **{avg_n} kr/år** ({avg_n_mo} kr/mån). Vid höga priser ({high_years}) sparar du **{avg_h} kr/år** ({avg_h_mo} kr/mån).",
        "en": "**{label}**: At normal prices ({normal_years}) you save **{avg_n} SEK/yr** ({avg_n_mo} SEK/mo). At high prices ({high_years}) you save **{avg_h} SEK/yr** ({avg_h_mo} SEK/mo).",
    },
    "invest_cost_trace": {
        "sv": "Investeringskostnad per år",
        "en": "Investment cost per year",
    },
    "savings_trace": {
        "sv": "Lägre elkostnad per år",
        "en": "Lower electricity cost per year",
    },
    "cost_hover": {
        "sv": "Kostnad",
        "en": "Cost",
    },
    "saving_hover": {
        "sv": "Besparing",
        "en": "Savings",
    },
    "col_battery": {
        "sv": "Batteri",
        "en": "Battery",
    },
    "col_savings_yr": {
        "sv": "Besparing/år",
        "en": "Savings/yr",
    },
    "col_cost_yr": {
        "sv": "Kostnad/år",
        "en": "Cost/yr",
    },
    "col_net_yr": {
        "sv": "Netto/år",
        "en": "Net/yr",
    },
    "col_net_mo": {
        "sv": "Netto/mån",
        "en": "Net/mo",
    },
    "col_investment": {
        "sv": "Investering",
        "en": "Investment",
    },
    "col_lifetime": {
        "sv": "Livslängd",
        "en": "Lifetime",
    },
    "col_tariff": {
        "sv": "Tariff",
        "en": "Tariff",
    },
    "repaid_annotation": {
        "sv": "Återbetald",
        "en": "Repaid",
    },
    "xaxis_year": {
        "sv": "År",
        "en": "Year",
    },
    "yaxis_cum_cashflow": {
        "sv": "Ackumulerat kassaflöde (SEK)",
        "en": "Cumulative cash flow (SEK)",
    },
    "fin_loan_label": {
        "sv": "Lån",
        "en": "Loan",
    },
    "fin_caption": {
        "sv": "Investeringen finansieras via {loan} ({rate}%, {years} år). Besparing minus lånekostnad = pengar kvar i fickan varje månad.",
        "en": "Investment financed via {loan} ({rate}%, {years} years). Savings minus loan cost = money in your pocket each month.",
    },
    "fin_lower_cost_trace": {
        "sv": "Lägre elkostnad",
        "en": "Lower electricity cost",
    },
    "fin_loan_cost_trace": {
        "sv": "{loan}kostnad",
        "en": "{loan} cost",
    },
    "fin_net_trace": {
        "sv": "Netto",
        "en": "Net",
    },
    "fin_saving_hover": {
        "sv": "Besparing",
        "en": "Savings",
    },
    "fin_net_hover": {
        "sv": "Netto",
        "en": "Net",
    },
    "yaxis_kr_month": {
        "sv": "kr/månad",
        "en": "SEK/month",
    },
    "col_loan_per_mo": {
        "sv": "{loan}/mån",
        "en": "{loan}/mo",
    },
    "col_savings_mo": {
        "sv": "Besparing/mån",
        "en": "Savings/mo",
    },
    "col_cashflow_mo": {
        "sv": "Kassaflöde/mån",
        "en": "Cash flow/mo",
    },
    "col_net_lifetime": {
        "sv": "Netto livslängd",
        "en": "Net lifetime",
    },
    "fin_all_profitable": {
        "sv": "**Alla storlekar lönsamma under batteriets livslängd.** Bäst: **{label}** — +{net_mo} kr/mån kassaflöde, +{net_life} kr netto under {lifetime} år.",
        "en": "**All sizes profitable over battery lifetime.** Best: **{label}** — +{net_mo} SEK/mo cash flow, +{net_life} SEK net over {lifetime} years.",
    },
    "fin_best_result": {
        "sv": "**{label}** ger bäst resultat: +{net_mo} kr/mån kassaflöde, +{net_life} kr netto under {lifetime} år.",
        "en": "**{label}** gives best result: +{net_mo} SEK/mo cash flow, +{net_life} SEK net over {lifetime} years.",
    },
    "fin_none_profitable": {
        "sv": "Ingen storlek ger positivt netto under batteriets livslängd med dessa lånvillkor.",
        "en": "No size gives positive net over battery lifetime with these loan terms.",
    },
    "fin_cash_caption": {
        "sv": "Kontant betalning — ackumulerat kassaflöde per batteristorlek",
        "en": "Cash payment — cumulative cash flow per battery size",
    },
    "yaxis_cum_sek": {
        "sv": "Ackumulerat (SEK)",
        "en": "Cumulative (SEK)",
    },
    "fuse_caption": {
        "sv": "Säkringsstorleken påverkar laddkapacitet och abonnemangskostnad. Din nuvarande: {fuse}A ({fee} kr/år). Resultat för rekommenderat batteri ({label}). OBS: kapaciteten är nedjusterad 30% för fasobalans — laster fördelar sig sällan jämnt över alla tre faser. 3\u00d7 Victron MultiPlus-II (en per fas, ESS \"Total of all phases\") kan kompensera detta med aktiv fasbalansering. Enda 48V-alternativet — alla andra 3-fas v\u00e4xelriktare kr\u00e4ver HV-batteri.",
        "en": "Fuse size affects charging capacity and subscription cost. Your current: {fuse}A ({fee} SEK/yr). Results for recommended battery ({label}). NOTE: capacity reduced 30% for phase imbalance \u2014 loads rarely distribute evenly across all three phases. 3\u00d7 Victron MultiPlus-II (one per phase, ESS \"Total of all phases\") can compensate with active phase balancing. Only 48V option \u2014 all other 3-phase inverters require HV battery.",
    },
    "fuse_current": {
        "sv": "(nu)",
        "en": "(now)",
    },
    "fuse_net_savings": {
        "sv": "Netto besparing (kr/år)",
        "en": "Net savings (SEK/yr)",
    },
    "fuse_extra_cost": {
        "sv": "Extra abonnemangskostnad (kr/år)",
        "en": "Extra subscription cost (SEK/yr)",
    },
    "fuse_col_fuse": {
        "sv": "Säkring",
        "en": "Fuse",
    },
    "fuse_col_current": {
        "sv": "(nuvarande)",
        "en": "(current)",
    },
    "fuse_col_optimal": {
        "sv": "\u2605 optimal",
        "en": "\u2605 optimal",
    },
    "fuse_col_subscription": {
        "sv": "Abonnemang",
        "en": "Subscription",
    },
    "fuse_col_gross_savings": {
        "sv": "Brutto besparing",
        "en": "Gross savings",
    },
    "fuse_col_extra_sub": {
        "sv": "Extra abonnemang",
        "en": "Extra subscription",
    },
    "fuse_col_net": {
        "sv": "Netto",
        "en": "Net",
    },
    "fuse_col_vs_current": {
        "sv": "vs nuvarande",
        "en": "vs current",
    },
    "fuse_best_net": {
        "sv": "**{fuse}A ger b\u00e4st netto** \u2014 {extra} kr/\u00e5r mer \u00e4n {current}A (extra avgift {fee} kr/\u00e5r)",
        "en": "**{fuse}A gives best net** \u2014 {extra} SEK/yr more than {current}A (extra fee {fee} SEK/yr)",
    },
    "fuse_current_best": {
        "sv": "**{fuse}A ger b\u00e4st netto f\u00f6r batteriet.** Uppgradering till {next_fuse}A kostar {fee} kr/\u00e5r mer.",
        "en": "**{fuse}A gives best net for the battery.** Upgrading to {next_fuse}A costs {fee} SEK/yr more.",
    },
    "detail_expander": {
        "sv": "Detaljer",
        "en": "Details",
    },
    "detail_battery": {
        "sv": "Batteri",
        "en": "Battery",
    },
    "detail_battery_price": {
        "sv": "Batteripris",
        "en": "Battery price",
    },
    "detail_total_invest": {
        "sv": "Total investering",
        "en": "Total investment",
    },
    "detail_lower_cost": {
        "sv": "L\u00e4gre elkostnad",
        "en": "Lower electricity cost",
    },
    "detail_of_which_battery": {
        "sv": "  varav batteri",
        "en": "  of which battery",
    },
    "detail_of_which_solar": {
        "sv": "  varav sol egenanv\u00e4nd",
        "en": "  of which solar self-use",
    },
    "detail_payback": {
        "sv": "\u00c5terbetalningstid",
        "en": "Payback period",
    },
    "detail_net_over": {
        "sv": "Netto under {lifetime} \u00e5r",
        "en": "Net over {lifetime} years",
    },
    "detail_battery_life": {
        "sv": "Batterilivsl\u00e4ngd",
        "en": "Battery lifetime",
    },
    "detail_tariff": {
        "sv": "Tariff",
        "en": "Tariff",
    },
    "detail_lower_cost_metric": {
        "sv": "L\u00e4gre elkostnad",
        "en": "Lower electricity cost",
    },
    "detail_fixed_costs": {
        "sv": "Fasta kostnader (samma med/utan)",
        "en": "Fixed costs (same with/without)",
    },
    "monthly_discharge": {
        "sv": "Urladdat (undviken elkostnad)",
        "en": "Discharged (avoided grid cost)",
    },
    "monthly_discharge_extra": {
        "sv": "Batteri ers\u00e4tter n\u00e4tk\u00f6p",
        "en": "Battery replaces grid purchase",
    },
    "monthly_sold_grid": {
        "sv": "S\u00e5lt till n\u00e4t",
        "en": "Sold to grid",
    },
    "monthly_sold_extra": {
        "sv": "\u00d6verskott s\u00e5lt",
        "en": "Surplus sold",
    },
    "monthly_charge_cost": {
        "sv": "Laddkostnad (fr\u00e5n n\u00e4t)",
        "en": "Charge cost (from grid)",
    },
    "monthly_charge_extra": {
        "sv": "Kostnad att ladda",
        "en": "Cost to charge",
    },
    "monthly_net_savings": {
        "sv": "Netto besparing",
        "en": "Net savings",
    },
    "monthly_avg_annotation": {
        "sv": "Snitt {value} kr/m\u00e5n",
        "en": "Avg {value} SEK/mo",
    },
    "yaxis_kr_month_typical": {
        "sv": "kr/m\u00e5nad (typiskt \u00e5r)",
        "en": "SEK/month (typical year)",
    },
    "monthly_details_expander": {
        "sv": "Detaljer per m\u00e5nad",
        "en": "Details per month",
    },
    "monthly_col_month": {
        "sv": "M\u00e5nad",
        "en": "Month",
    },
    "monthly_col_discharged": {
        "sv": "Urladdat (kr)",
        "en": "Discharged (SEK)",
    },
    "monthly_col_charge_cost": {
        "sv": "Laddkostnad (kr)",
        "en": "Charge cost (SEK)",
    },
    "monthly_col_sold": {
        "sv": "S\u00e5lt till n\u00e4t (kr)",
        "en": "Sold to grid (SEK)",
    },
    "monthly_col_solar_bat": {
        "sv": "Sol\u2192batteri (kWh)",
        "en": "Solar\u2192battery (kWh)",
    },
    "monthly_col_net": {
        "sv": "Netto besparing (kr)",
        "en": "Net savings (SEK)",
    },
    "computing_scenarios": {
        "sv": "Ber\u00e4knar framtidsscenarier...",
        "en": "Computing future scenarios...",
    },
    "net_lifetime_delta": {
        "sv": "Netto {value} kr under {lifetime} \u00e5r",
        "en": "Net {value} SEK over {lifetime} years",
    },
    "forecast_15yr_header": {
        "sv": "15-\u00e5rsprognos \u2014 {label}",
        "en": "15-year forecast \u2014 {label}",
    },
    "forecast_15yr_caption": {
        "sv": "Ackumulerat kassafl\u00f6de under batteriets livsl\u00e4ngd i tre scenarier. Volatiliteten \u00f6kar linj\u00e4rt till m\u00e5lniv\u00e5 under de f\u00f6rsta 10 \u00e5ren.",
        "en": "Cumulative cash flow over battery lifetime in three scenarios. Volatility increases linearly to target level over the first 10 years.",
    },
    "computing_15yr": {
        "sv": "Ber\u00e4knar 15-\u00e5rskurvor...",
        "en": "Computing 15-year curves...",
    },
    "scenario_col_scenario": {
        "sv": "Scenario",
        "en": "Scenario",
    },
    "scenario_col_volatility": {
        "sv": "Volatilitet",
        "en": "Volatility",
    },
    "scenario_col_savings_yr": {
        "sv": "Besparing/\u00e5r",
        "en": "Savings/yr",
    },
    "scenario_col_savings_mo": {
        "sv": "Besparing/m\u00e5n",
        "en": "Savings/mo",
    },
    "scenario_col_net_15yr": {
        "sv": "Netto 15 \u00e5r",
        "en": "Net 15 years",
    },
    "scenario_vol_desc": {
        "sv": "{vf:.0%}x om 10 \u00e5r",
        "en": "{vf:.0%}x in 10 years",
    },

    # ---- Results: recommendation, export comparison, self-consumption, luft-luft, PDF ----
    "rec_upgrade_fuse": {
        "sv": " + uppgradera till {fuse:.0f}A",
        "en": " + upgrade to {fuse:.0f}A",
    },
    "rec_downgrade_fuse": {
        "sv": " + nedgradera till {fuse:.0f}A",
        "en": " + downgrade to {fuse:.0f}A",
    },
    "rec_success": {
        "sv": "**Rekommendation: {label}{fuse_label}** — "
              "lägre elkostnad {benefit:,.0f} kr/år ({benefit_mo:,.0f} kr/mån), "
              "investering {invest:,.0f} kr, "
              "återbetald på {payback:.1f} år, "
              "netto {profit:,.0f} kr under {lifetime:.0f} år",
        "en": "**Recommendation: {label}{fuse_label}** — "
              "lower electricity cost {benefit:,.0f} SEK/yr ({benefit_mo:,.0f} SEK/mo), "
              "investment {invest:,.0f} SEK, "
              "payback in {payback:.1f} years, "
              "net {profit:,.0f} SEK over {lifetime:.0f} years",
    },
    "fuse_change_info": {
        "sv": "Säkring: {change_word} {from_fuse:.0f}A → {to_fuse:.0f}A: "
              "abonnemang {fee_delta:+,.0f} kr/år, "
              "netto {extra:+,.0f} kr/år bättre än nuvarande säkring",
        "en": "Fuse: {change_word} {from_fuse:.0f}A → {to_fuse:.0f}A: "
              "subscription {fee_delta:+,.0f} SEK/yr, "
              "net {extra:+,.0f} SEK/yr better than current fuse",
    },
    "fuse_upgrade_word": {
        "sv": "Uppgradering",
        "en": "Upgrade",
    },
    "fuse_downgrade_word": {
        "sv": "Nedgradering",
        "en": "Downgrade",
    },
    "best_tariff_info": {
        "sv": "Bästa tariff: **{tariff}**",
        "en": "Best tariff: **{tariff}**",
    },
    "export_compare_with": {
        "sv": "med nätexport",
        "en": "with grid export",
    },
    "export_compare_without": {
        "sv": "utan nätexport (nollexport)",
        "en": "without grid export (zero export)",
    },
    "export_compare_expander": {
        "sv": "Jämför: {label}",
        "en": "Compare: {label}",
    },
    "export_simulating": {
        "sv": "Simulerar alternativ...",
        "en": "Simulating alternative...",
    },
    "export_mode_zero": {
        "sv": "Nollexport",
        "en": "Zero export",
    },
    "export_mode_with": {
        "sv": "Med export",
        "en": "With export",
    },
    "export_col_mode": {
        "sv": "Läge",
        "en": "Mode",
    },
    "export_col_selected": {
        "sv": " (valt)",
        "en": " (selected)",
    },
    "export_col_savings_yr": {
        "sv": "Besparing/år",
        "en": "Savings/yr",
    },
    "export_col_cycles_yr": {
        "sv": "Cykler/år",
        "en": "Cycles/yr",
    },
    "export_col_lifetime": {
        "sv": "Livslängd",
        "en": "Lifetime",
    },
    "export_col_net": {
        "sv": "Netto",
        "en": "Net",
    },
    "export_revenue_caption": {
        "sv": "Export: {kwh:,.0f} kWh/år → {rev:,.0f} kr/år intäkt. "
              "Kräver mikroproducentregistrering och exportavtal.",
        "en": "Export: {kwh:,.0f} kWh/yr → {rev:,.0f} SEK/yr revenue. "
              "Requires microproducer registration and export agreement.",
    },
    "export_better": {
        "sv": "**{label} ger {diff:+,.0f} kr mer** över livslängden.",
        "en": "**{label} gives {diff:+,.0f} SEK more** over lifetime.",
    },
    "export_worse": {
        "sv": "**{label} är bättre** — {diff:,.0f} kr mer över livslängden.",
        "en": "**{label} is better** — {diff:,.0f} SEK more over lifetime.",
    },
    "tipping_point_caption": {
        "sv": "**Tipping point för exportarbitrage:** "
              "Vid typiskt nattelpris (~{low_kr:.0f} kr/kWh) behövs ett spotpris på minst "
              "~{min_high_kr:.1f} kr/kWh vid försäljning för att täcka "
              "energiskatt, nätavgift, verkningsgrad ({eff:.0%}) och exportavgift. "
              "Det kräver en daglig prisspridning på ~{spread_kr:.1f} kr/kWh — "
              "ovanligt med dagens svenska spotpriser, men kan bli vanligare "
              "med ökad andel vind/sol och minskad kärnkraft. "
              "**OBS:** Exportarbitrage kräver nätägare med låga fasta avgifter och låg energiavgift "
              "(t.ex. SEOM effekttariff: 5 öre/kWh). Med tidstariff (t.ex. Vattenfall: 76,5 öre höglast) "
              "äter överföringsavgiften upp vinsten — varje laddad kWh kostar fullt, "
              "men exporterad kWh ger bara spotpris tillbaka.",
        "en": "**Tipping point for export arbitrage:** "
              "At typical night price (~{low_kr:.0f} SEK/kWh), a spot price of at least "
              "~{min_high_kr:.1f} SEK/kWh is needed when selling to cover "
              "energy tax, grid fee, efficiency ({eff:.0%}), and export fee. "
              "This requires a daily price spread of ~{spread_kr:.1f} SEK/kWh — "
              "uncommon with current Swedish spot prices, but may become more frequent "
              "with increasing wind/solar and declining nuclear. "
              "**Note:** Export arbitrage requires a grid operator with low fixed fees and low energy fee "
              "(e.g., SEOM power tariff: 5 öre/kWh). With time-of-use tariff (e.g., Vattenfall: 76.5 öre peak) "
              "the transfer fee eats the profit — each charged kWh costs full price, "
              "but exported kWh only gets spot price back.",
    },
    "self_consumption_zero": {
        "sv": "**Maximal egenförbrukning: {label}** — "
              "nära noll export ({export:.0f} kWh/år till nät), "
              "investering {invest:,.0f} kr, "
              "lägre elkostnad {benefit:,.0f} kr/år",
        "en": "**Maximum self-consumption: {label}** — "
              "near zero export ({export:.0f} kWh/yr to grid), "
              "investment {invest:,.0f} SEK, "
              "lower electricity cost {benefit:,.0f} SEK/yr",
    },
    "self_consumption_lowest": {
        "sv": "**Lägst export: {label}** — "
              "{export:.0f} kWh/år exporteras fortfarande till nät. "
              "Investering {invest:,.0f} kr. "
              "Överväg större batteri eller fler flexibla laster för att nå noll export.",
        "en": "**Lowest export: {label}** — "
              "{export:.0f} kWh/yr still exported to grid. "
              "Investment {invest:,.0f} SEK. "
              "Consider larger battery or more flexible loads to reach zero export.",
    },
    "self_consumption_export_bar": {
        "sv": "Export till nät (kWh/år)",
        "en": "Export to grid (kWh/yr)",
    },
    "self_consumption_savings_line": {
        "sv": "Lägre elkostnad (kr/år)",
        "en": "Lower electricity cost (SEK/yr)",
    },
    "self_consumption_title": {
        "sv": "Egenförbrukning vs batteristorlek",
        "en": "Self-consumption vs battery size",
    },
    "self_consumption_xaxis": {
        "sv": "Batterikapacitet (kWh)",
        "en": "Battery capacity (kWh)",
    },
    "self_consumption_yaxis": {
        "sv": "Export till nät (kWh/år)",
        "en": "Export to grid (kWh/yr)",
    },
    "self_consumption_yaxis2": {
        "sv": "Lägre elkostnad (kr/år)",
        "en": "Lower electricity cost (SEK/yr)",
    },
    "aa_expander": {
        "sv": "Luft-luft bidrag (utanför huvudinvesteringen)",
        "en": "Air-to-air contribution (outside main investment)",
    },
    "aa_solar_surplus": {
        "sv": "Luft-luft solöverskott",
        "en": "Air-to-air solar surplus",
    },
    "aa_solar_surplus_help": {
        "sv": "Solöverskott som luft-luft absorberar genom "
              "förvärme/förkylning av huset (termisk lagring)",
        "en": "Solar surplus absorbed by air-to-air via "
              "pre-heating/pre-cooling the house (thermal storage)",
    },
    "aa_avoided_export": {
        "sv": "Undviken export",
        "en": "Avoided export",
    },
    "aa_avoided_export_help": {
        "sv": "Värdet av att använda solöverskottet i huset "
              "istället för att exportera till nät (~60 öre/kWh)",
        "en": "Value of using solar surplus in the house "
              "instead of exporting to grid (~60 öre/kWh)",
    },
    "aa_other_flex": {
        "sv": "Övriga flex-laster",
        "en": "Other flex loads",
    },
    "aa_other_flex_help": {
        "sv": "Poolpump, varmvatten etc. — separat från luft-luft",
        "en": "Pool pump, hot water, etc. — separate from air-to-air",
    },
    "aa_caption": {
        "sv": "Luft-luft absorberar {aa_flex:,.0f} kWh/år solöverskott "
              "av totalt {total_flex:,.0f} kWh/år flex-förbrukning. "
              "Detta är inte inräknat i huvudinvesteringens lönsamhet ovan — "
              "det är en bonus som minskar exportförluster.",
        "en": "Air-to-air absorbs {aa_flex:,.0f} kWh/yr solar surplus "
              "out of {total_flex:,.0f} kWh/yr total flex consumption. "
              "This is not included in the main investment profitability above — "
              "it is a bonus that reduces export losses.",
    },
    "pdf_error": {
        "sv": "Kunde inte generera PDF: {error}",
        "en": "Could not generate PDF: {error}",
    },
    "no_weather_data": {
        "sv": "Ingen väderdata från {station}. Klicka 'KÖR SIMULERING' för att hämta automatiskt.",
        "en": "No weather data from {station}. Click 'RUN SIMULATION' to fetch automatically.",
    },
    "sek_kwh_caption": {
        "sv": "Ange pris per kWh och max laddeffekt. Simuleringen testar storlekar från 5 till 100 kWh och hittar den storlek som maximerar egenförbrukning.",
        "en": "Enter price per kWh and max charge rate. The simulation tests sizes from 5 to 100 kWh and finds the size that maximizes self-consumption.",
    },
    "sek_kwh_typical_help": {
        "sv": "Typiskt 800-1500 SEK/kWh för LiFePO4.",
        "en": "Typically 800-1500 SEK/kWh for LiFePO4.",
    },
    "max_kw_help": {
        "sv": "Begränsas av inverter. NKON: 11 kW (16 kWh), 15 kW (32 kWh).",
        "en": "Limited by inverter. NKON: 11 kW (16 kWh), 15 kW (32 kWh).",
    },
    "step_kwh_help": {
        "sv": "Storlekar testas i detta steg: 5, 10, 15, ... kWh",
        "en": "Sizes tested in this step: 5, 10, 15, ... kWh",
    },
    "testing_sizes": {
        "sv": "Testar {count} storlekar: {first}–{last} kWh à {price} kr/kWh",
        "en": "Testing {count} sizes: {first}–{last} kWh at {price} kr/kWh",
    },
    "edit_table_caption": {
        "sv": "Redigera tabellen nedan — lägg till/ta bort rader, ändra priser. NKON ESS Pro (LiFePO4) som standard.",
        "en": "Edit the table below — add/remove rows, change prices. NKON ESS Pro (LiFePO4) as default.",
    },
    "install_same_cost_help": {
        "sv": "Samma kostnad oavsett batteristorlek",
        "en": "Same cost regardless of battery size",
    },
    "solar_material_help": {
        "sv": "Paneler + inverter + montage/kabel. Sätt 0 om redan installerat.",
        "en": "Panels + inverter + mounting/cables. Set 0 if already installed.",
    },
    "solar_install_help": {
        "sv": "0 om du installerar själv",
        "en": "0 if you install yourself",
    },
    "mortgage_caption": {
        "sv": "Investeringen läggs på bolånet",
        "en": "Investment added to mortgage",
    },
    "loan_caption": {
        "sv": "Lånekostnaden visas i kassaflödesdiagrammet",
        "en": "Loan cost shown in cashflow chart",
    },
    "simulation_spinner": {
        "sv": "Simulerar {batteries} batteristorlekar × {tariffs} tariffer × {fuses} säkringar...",
        "en": "Simulating {batteries} battery sizes × {tariffs} tariffs × {fuses} fuse sizes...",
    },
    "aa_flex_cool": {
        "sv": "Luft-luft AC (solöverskott)",
        "en": "Air-to-air AC (solar surplus)",
    },
    "aa_flex_heat": {
        "sv": "Luft-luft värme (solöverskott)",
        "en": "Air-to-air heating (solar surplus)",
    },
    "diy_header": {
        "sv": "Systemdesign — DIY utan export",
        "en": "System Design — DIY Zero Export",
    },
    "diy_intro": {
        "sv": "En kostnadseffektiv design som separerar laddning (billig, hög effekt) från urladdning (smart, nollexport). Kräver ingen mikroproducentregistrering.",
        "en": "A cost-effective design that separates charging (cheap, high power) from discharging (smart, zero export). No microproducer registration needed.",
    },

    # ---- Degradation ----
    "degradation_caption": {
        "sv": "Inkluderar batteriåldring: LiFePO4 tappar ~1% kapacitet per år (85% SoH efter 15 år).",
        "en": "Includes battery aging: LiFePO4 loses ~1% capacity per year (85% SoH after 15 years).",
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
