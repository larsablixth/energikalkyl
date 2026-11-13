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
        "sv": "Ladda upp förbrukningsdata (Excel/CSV/JSON)",
        "en": "Upload consumption data (Excel/CSV/JSON)",
    },
    "upload_caption": {
        "sv": "Ladda upp filen precis som du fick den — formatet känns igen automatiskt.  \n"
              "**Vattenfall:** [mina.vattenfall.se](https://mina.vattenfall.se) → Elavtal → "
              "Elförbrukning → Exportera till Excel.  \n"
              "**Ellevio, E.ON, Göteborg Energi, Mälarenergi m.fl.:** Mina sidor → förbrukning → "
              "välj ett helt år och upplösning *timme* (eller kvart) → exportera/ladda ner (CSV eller Excel).  \n"
              "**Home Assistant:** Historik → välj din energisensor (kWh, mätarställning) → "
              "*Ladda ner data*.  \n"
              "Klarar tim- och kvartsvärden, en rad per dag med 24 kolumner, mätarställningar, "
              "Wh/kWh, UTC-tider och sommar-/vintertid.",
        "en": "Upload the file exactly as you got it — the format is detected automatically.  \n"
              "**Vattenfall:** [mina.vattenfall.se](https://mina.vattenfall.se) → Electricity contract → "
              "Consumption → Export to Excel.  \n"
              "**Ellevio, E.ON, Göteborg Energi, Mälarenergi etc.:** My pages → consumption → "
              "pick a full year and *hourly* (or 15-min) resolution → export/download (CSV or Excel).  \n"
              "**Home Assistant:** History → pick your energy sensor (kWh, meter total) → "
              "*Download data*.  \n"
              "Handles hourly and 15-min values, one row per day with 24 columns, meter readings, "
              "Wh/kWh, UTC timestamps and daylight saving time.",
    },
    "cons_file_loaded": {
        "sv": "**{name}**: {fmt} — {start} → {end}, {days} dagar ({count} värden)",
        "en": "**{name}**: {fmt} — {start} → {end}, {days} days ({count} values)",
    },
    "cons_parse_failed": {
        "sv": "**{name}** kunde inte läsas: {reason}  \nKolumner som hittades: {columns}",
        "en": "**{name}** could not be read: {reason}  \nColumns found: {columns}",
    },
    "cons_fmt_vattenfall_excel": {"sv": "Vattenfall Eldistribution, timvärden", "en": "Vattenfall Eldistribution, hourly values"},
    "cons_fmt_long": {"sv": "Tidsserie (en rad per intervall)", "en": "Time series (one row per interval)"},
    "cons_fmt_wide": {"sv": "En rad per dag med timkolumner", "en": "One row per day with hour columns"},
    "cons_fmt_meter": {"sv": "Mätarställningar (omräknade till förbrukning)", "en": "Meter readings (converted to consumption)"},
    "cons_fmt_ha_history": {"sv": "Home Assistant-historik, energisensor", "en": "Home Assistant history, energy sensor"},
    "cons_fmt_ha_history_power": {"sv": "Home Assistant-historik, effektsensor (integrerad)", "en": "Home Assistant history, power sensor (integrated)"},
    "cons_fmt_ha_statistics": {"sv": "Home Assistant långtidsstatistik", "en": "Home Assistant long-term statistics"},
    "cons_err_empty": {"sv": "filen är tom.", "en": "the file is empty."},
    "cons_err_no_table": {"sv": "hittade ingen tabell med förbrukning i filen.", "en": "no consumption table found in the file."},
    "cons_err_no_time": {
        "sv": "hittade ingen kolumn med datum/tid.",
        "en": "no date/time column found.",
    },
    "cons_err_no_value": {
        "sv": "hittade ingen kolumn med förbrukning (kWh). Kostnads- och produktionskolumner ignoreras.",
        "en": "no consumption (kWh) column found. Cost and production columns are ignored.",
    },
    "cons_err_no_values": {"sv": "inga rader med både tid och värde.", "en": "no rows with both a time and a value."},
    "cons_err_daily_only": {
        "sv": "filen innehåller bara dygnsvärden. Exportera igen med upplösning *timme* eller *kvart*.",
        "en": "the file only has daily totals. Export again with *hourly* or *15-minute* resolution.",
    },
    "cons_err_irregular": {
        "sv": "tidsstegen är oregelbundna och värdena ser inte ut som mätarställningar.",
        "en": "the time steps are irregular and the values don't look like meter readings.",
    },
    "cons_err_all_zero": {"sv": "alla förbrukningsvärden är 0.", "en": "all consumption values are 0."},
    "cons_err_xls_old": {
        "sv": "gammalt Excel-format (.xls). Öppna filen och spara som .xlsx eller CSV.",
        "en": "old Excel format (.xls). Open the file and save it as .xlsx or CSV.",
    },
    "cons_err_power_unknown": {
        "sv": "statistiken är medelvärden men enheten (W/kW) saknas.",
        "en": "the statistics are averages but the unit (W/kW) is missing.",
    },
    "cons_err_vattenfall_no_hourly": {
        "sv": "Vattenfall-filen saknar timvärden.",
        "en": "the Vattenfall file has no hourly values.",
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
    "bat_fade": {
        "sv": 'Kapacitetsförlust (%/år)',
        "en": 'Capacity fade (%/yr)',
    },
    "bat_fade_help": {
        "sv": 'Hur mycket batteriets kapacitet, och därmed dess värde, minskar per år. LiFePO4: ofta omkring 1 %/år. Används i alla resultat.',
        "en": "How much the battery's capacity, and with it its value, drops per year. LiFePO4: often around 1%/yr. Used in all results.",
    },
    "standby_w": {
        "sv": 'Standbyeffekt växelriktare + BMS (W)',
        "en": 'Standby power inverter + BMS (W)',
    },
    "standby_w_help": {
        "sv": 'Effekt som batterisystemet drar dygnet runt (t.ex. Deye 12K ~30 W + Seplos BMS ~15 W). Kostnaden dras från besparingen varje år.',
        "en": 'Power the battery system draws around the clock (e.g. Deye 12K ~30 W + Seplos BMS ~15 W). The cost is subtracted from the savings every year.',
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
        "sv": "Laster utöver uppvärmning. Elbil och poolvärmepump hanteras separat från hushållets grundlast. "
              "Inga är förvalda: lägg till de du har.",
        "en": "Loads beyond heating. EV and pool heat pump are handled separately from base household load. "
              "None are preselected: add the ones you have.",
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
              "Varmvatten-element tar upp överskott när batteriet är fullt. "
              "En poolvärmepump (värmer vattnet) kan vänta på överskott; en cirkulationspump för poolen "
              "går varje dag oavsett sol och hör hemma under tidsstyrda laster (eller i grundlasten), inte här.",
        "en": "Runs on solar surplus instead of exporting to grid. "
              "Hot water tank absorbs surplus when the battery is full. "
              "A pool heat pump (heats the water) can wait for surplus; a pool circulation pump "
              "runs every day whether the sun shines or not and belongs under scheduled loads (or in the base load), not here.",
    },
    "add_flex_load": {
        "sv": "+ Flexibel last",
        "en": "+ Flexible load",
    },
    "add_ev_load": {
        "sv": "+ Elbil",
        "en": "+ EV",
    },
    "ev_load_name": {
        "sv": "Elbil",
        "en": "EV",
    },
    "add_pool_heat_pump": {
        "sv": "+ Poolvärmepump",
        "en": "+ Pool heat pump",
    },
    "pool_heat_pump_name": {
        "sv": "Poolvärmepump",
        "en": "Pool heat pump",
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
    "tibber_token_required": {
        "sv": "Klistra in din Tibber-token först (hämtas på developer.tibber.com).",
        "en": "Paste your Tibber token first (get it at developer.tibber.com).",
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
        "sv": 'Samma simulering — uppdelad per år. Alla kolumner visar batteriets handelsresultat per år (urladdningsvärde − laddkostnad + exportintäkt), utan solcellernas egenanvändning, effektavgift, säkringsavgift, standby och slitage. Elpriser varierar kraftigt mellan år.',
        "en": "Same simulation — split by year. All columns show the battery's trading result per year (discharge value − charging cost + export revenue), without solar self-use, demand charge, fuse fee, standby and wear. Electricity prices vary significantly between years.",
    },
    "compare_all_header": {
        "sv": "Jämförelse alla batteristorlekar",
        "en": "Comparison of all battery sizes",
    },
    "compare_all_caption": {
        "sv": 'Investeringen fördelad över batteriets livslängd jämförd med genomsnittlig besparing per år under samma period (inkl. slitage och standby). Samma tidsskala: (besparing − kostnad) × livslängd = netto.',
        "en": 'Investment spread over the battery lifetime compared with the average savings per year over the same period (incl. wear and standby). Same timescale: (savings − cost) × lifetime = net.',
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
        "sv": 'Fem antaganden om hur prisskillnaderna mellan timmar utvecklas — det är dem batteriet tjänar på. Dygnets medelpris är oförändrat. Det här är antaganden, inte prognoser: kalkylen anger inte vilket som är mest troligt. Besparing/år = första årets värde om scenariots nivå gällde redan nu.',
        "en": "Five assumptions about how the price differences between hours develop — that is what the battery earns from. The daily average price is unchanged. These are assumptions, not forecasts: the tool does not say which is most likely. Savings/yr = the first year's value if the scenario's level already applied.",
    },
    "scen_smaller": {
        "sv": 'Mindre prissvängningar (0,7×)',
        "en": 'Smaller price swings (0.7×)',
    },
    "scen_unchanged": {
        "sv": 'Oförändrat (1,0×)',
        "en": 'Unchanged (1.0×)',
    },
    "scen_somewhat_larger": {
        "sv": 'Något större (1,5×)',
        "en": 'Somewhat larger (1.5×)',
    },
    "scen_much_larger": {
        "sv": 'Mycket större (2,5×)',
        "en": 'Much larger (2.5×)',
    },
    "scen_extreme": {
        "sv": 'Extremt större (4×)',
        "en": 'Extremely larger (4×)',
    },
    "scen_smaller_desc": {
        "sv": 'Antar att prisskillnaderna mellan timmar minskar till 70 % på 10 år, t.ex. för att många batterier och flexibla laster jämnar ut priserna.',
        "en": 'Assumes the price differences between hours shrink to 70% over 10 years, e.g. because many batteries and flexible loads flatten prices.',
    },
    "scen_unchanged_desc": {
        "sv": 'Antar samma prisskillnader som i den historiska perioden. Samma som huvudresultatet.',
        "en": 'Assumes the same price differences as in the historical period. Equals the main result.',
    },
    "scen_somewhat_larger_desc": {
        "sv": 'Antar att prisskillnaderna mellan timmar ökar till 1,5 gånger dagens på 10 år.',
        "en": "Assumes the price differences between hours grow to 1.5 times today's over 10 years.",
    },
    "scen_much_larger_desc": {
        "sv": 'Antar att prisskillnaderna mellan timmar ökar till 2,5 gånger dagens på 10 år.',
        "en": "Assumes the price differences between hours grow to 2.5 times today's over 10 years.",
    },
    "scen_extreme_desc": {
        "sv": 'Antar att prisskillnaderna mellan timmar ökar till 4 gånger dagens på 10 år.',
        "en": "Assumes the price differences between hours grow to 4 times today's over 10 years.",
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
    "export_simulator_json": {
        "sv": "Exportera för Simulator (JSON)",
        "en": "Export for Simulator (JSON)",
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
        "sv": "Värmebesparing minus AC-kostnad (till aktuellt retail-elpris)",
        "en": "Heating savings minus AC cost (at current retail electricity price)",
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
        "sv": "Husförbrukning (exkl. elbil/poolvärmepump): ~{annual} kWh/år | vinter ~{winter} kWh/dag, sommar ~{summer} kWh/dag",
        "en": "House consumption (excl. EV/pool heat pump): ~{annual} kWh/yr | winter ~{winter} kWh/day, summer ~{summer} kWh/day",
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
        "sv": '**{label}**: batteriets handelsresultat vid normala priser ({normal_years}) är **{avg_n} kr/år** ({avg_n_mo} kr/mån). Vid höga priser ({high_years}) **{avg_h} kr/år** ({avg_h_mo} kr/mån).',
        "en": "**{label}**: the battery's trading result at normal prices ({normal_years}) is **{avg_n} SEK/yr** ({avg_n_mo} SEK/mo). At high prices ({high_years}) **{avg_h} SEK/yr** ({avg_h_mo} SEK/mo).",
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
    "col_debt_left": {
        "sv": "Kvar att betala när batteriet är slut",
        "en": "Debt left when battery is worn out",
    },
    "fin_debt_caption": {
        "sv": "Lånet löper i {years} år men batteriet håller kortare. Kassaflödet per månad blir därför delvis positivt för att amorteringen sprids över fler år än batteriet varar: skulden i kolumnen ovan återstår att betala när batteriet är slut. Netto livslängd räknar med hela investeringen plus räntan under batteriets livslängd.",
        "en": "The loan runs for {years} years but the battery lasts shorter. The monthly cash flow is therefore positive partly because repayment is spread over more years than the battery lasts: the debt in the column above is still owed when the battery is worn out. Net lifetime counts the full investment plus the interest paid during the battery lifetime.",
    },
    "fin_all_profitable": {
        "sv": '**Alla storlekar lönsamma under batteriets livslängd.** Bäst: **{label}** — {net_mo} kr/mån kassaflöde, {net_life} kr netto under {lifetime} år.',
        "en": '**All sizes profitable over battery lifetime.** Best: **{label}** — {net_mo} SEK/mo cash flow, {net_life} SEK net over {lifetime} years.',
    },
    "fin_best_result": {
        "sv": '**{label}** ger bäst resultat: {net_mo} kr/mån kassaflöde, {net_life} kr netto under {lifetime} år.',
        "en": '**{label}** gives best result: {net_mo} SEK/mo cash flow, {net_life} SEK net over {lifetime} years.',
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
    "fuse_year1_note": {
        "sv": 'Belopp per år avser första året (inkl. standby). Rekommendationen ovan väljer säkring efter netto över batteriets livslängd.',
        "en": 'Amounts per year are for the first year (incl. standby). The recommendation above picks the fuse by net over the battery lifetime.',
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
    "detail_of_which_standby": {
        "sv": '  varav standby',
        "en": '  of which standby',
    },
    "detail_of_which_fuse": {
        "sv": '  varav säkringsavgift',
        "en": '  of which fuse fee',
    },
    "detail_of_which_tariff": {
        "sv": '  varav tariffbyte',
        "en": '  of which tariff change',
    },
    "detail_solar_flows": {
        "sv": 'Vart solelen tar vägen (per år)',
        "en": 'Where the solar power goes (per year)',
    },
    "solar_flow_produced": {
        "sv": 'Producerat',
        "en": 'Produced',
    },
    "solar_flow_direct": {
        "sv": '  använt direkt i huset',
        "en": '  used directly in the house',
    },
    "solar_flow_battery": {
        "sv": '  laddat i batteriet',
        "en": '  charged into the battery',
    },
    "solar_flow_flex": {
        "sv": '  flexibla laster',
        "en": '  flexible loads',
    },
    "solar_flow_exported": {
        "sv": '  exporterat',
        "en": '  exported',
    },
    "solar_flow_curtailed": {
        "sv": '  spillt (strypt)',
        "en": '  wasted (curtailed)',
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
        "sv": "Prognos \u2014 {label}",
        "en": "Forecast \u2014 {label}",
    },
    "forecast_15yr_caption": {
        "sv": 'Ackumulerat kassaflöde under batteriets livslängd i varje scenario, med samma slitage och standbykostnad som huvudresultatet. Prisskillnaderna ändras linjärt till scenariots nivå under de första 10 åren.',
        "en": "Cumulative cash flow over the battery lifetime in each scenario, with the same wear and standby cost as the main result. Price differences change linearly to the scenario's level over the first 10 years.",
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
        "sv": "Netto {lifetime} \u00e5r",
        "en": "Net {lifetime} years",
    },
    "scenario_vol_desc": {
        "sv": "{vf:.1f}x om 10 \u00e5r",
        "en": "{vf:.1f}x in 10 years",
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
              "{payback_text}, "
              "netto {profit:,.0f} kr under {lifetime:.0f} år",
        "en": "**Recommendation: {label}{fuse_label}** — "
              "lower electricity cost {benefit:,.0f} SEK/yr ({benefit_mo:,.0f} SEK/mo), "
              "investment {invest:,.0f} SEK, "
              "{payback_text}, "
              "net {profit:,.0f} SEK over {lifetime:.0f} years",
    },
    "fuse_downgrade_tip": {
        "sv": "Tips, oberoende av investeringen: den modellerade förbrukningen ryms inom {fuse:.0f}A i stället för "
              "{current:.0f}A, vilket skulle sänka abonnemanget med {saving:,.0f} kr/år. Det är inte medräknat i "
              "kalkylen, eftersom det går att göra utan batteri eller solceller. Kalkylen bygger på timmedelvärden "
              "och ser inte korta toppar (spis, bastu, elbilsladdning), och med mindre säkring laddar batteriet "
              "långsammare än kalkylen antar. Rådgör med en elektriker.",
        "en": "Tip, independent of the investment: the modelled consumption fits within {fuse:.0f}A instead of "
              "{current:.0f}A, which would lower the subscription by {saving:,.0f} SEK/yr. It is not counted in "
              "the result, because it can be done without a battery or solar panels. The calculation uses hourly "
              "averages and does not see short peaks (stove, sauna, EV charging), and with a smaller fuse the "
              "battery charges more slowly than assumed here. Ask an electrician.",
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
              "istället för att exportera till nät (spotpris ~30–60 öre/kWh "
              "sedan skattereduktionen togs bort 2026)",
        "en": "Value of using solar surplus in the house "
              "instead of exporting to grid (spot price ~30–60 öre/kWh "
              "since the tax credit was abolished in 2026)",
    },
    "aa_other_flex": {
        "sv": "Övriga flex-laster",
        "en": "Other flex loads",
    },
    "aa_other_flex_help": {
        "sv": "Poolvärmepump, varmvatten etc. — separat från luft-luft",
        "en": "Pool heat pump, hot water, etc. — separate from air-to-air",
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
        "sv": "Typiskt 800-1500 SEK/kWh för LiFePO4. Ange pris inkl. moms.",
        "en": "Typically 800-1500 SEK/kWh for LiFePO4. Enter the price incl. VAT.",
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
        "sv": 'Linjerna räknar med batteriets kapacitetsförlust ({fade} %/år), solcellernas åldring ({deg} %/år, bara när solcellerna ingår i investeringen) och standbyförbrukning ({standby} W ≈ {standby_cost} kr/år). Varje linje slutar när batteriet är förbrukat.',
        "en": 'The lines include battery capacity fade ({fade}%/yr), panel degradation ({deg}%/yr, only when the panels are part of the investment) and standby consumption ({standby} W ≈ {standby_cost} SEK/yr). Each line stops when the battery is worn out.',
    },

    # ---- Added: validation, stale results, grön teknik, battery table ----
    "price_csv_error": {
        "sv": "Kunde inte läsa pris-CSV: {error}",
        "en": "Could not read price CSV: {error}",
    },
    "price_csv_missing_cols": {
        "sv": "filen är tom eller saknar kolumner ({cols}). Krävs: date, hour, sek_per_kwh (eller ore_per_kwh).",
        "en": "the file is empty or missing columns ({cols}). Required: date, hour, sek_per_kwh (or ore_per_kwh).",
    },
    "price_range_invalid": {
        "sv": "Startdatum måste vara före eller lika med slutdatum.",
        "en": "Start date must be on or before the end date.",
    },
    "price_range_future": {
        "sv": "Datumintervallet ligger helt i framtiden — det finns inga priser för det ännu.",
        "en": "The date range is entirely in the future — no prices exist for it yet.",
    },
    "no_battery_rows": {
        "sv": "Ange minst ett batteri i pristabellen.",
        "en": "Enter at least one battery in the price table.",
    },
    "results_outdated": {
        "sv": "⚠️ Indata har ändrats sedan simuleringen kördes. Resultaten och PDF-rapporten nedan gäller de tidigare inställningarna — kör simuleringen igen för att uppdatera.",
        "en": "⚠️ Inputs have changed since the simulation was run. The results and PDF report below reflect the previous settings — run the simulation again to update.",
    },
    "bt_col_name": {"sv": "Namn", "en": "Name"},
    "bt_col_capacity": {"sv": "Kapacitet (kWh)", "en": "Capacity (kWh)"},
    "bt_col_max_kw": {"sv": "Max effekt (kW)", "en": "Max power (kW)"},
    "bt_col_price": {"sv": "Pris (SEK)", "en": "Price (SEK)"},
    "price_per_kwh_caption": {"sv": "Pris per kWh:", "en": "Price per kWh:"},
    "nkon_vat_note": {
        "sv": "Standardpriserna är NKON:s listpriser i EUR omräknade till SEK **inkl. 25 % moms**, exkl. frakt. Ange gärna ditt faktiska pris.",
        "en": "Default prices are NKON list prices in EUR converted to SEK **incl. 25% VAT**, excl. shipping. Enter your actual price if you can.",
    },
    "green_deduction_label": {
        "sv": "Skattereduktion för grön teknik",
        "en": "Green technology tax deduction (grön teknik)",
    },
    "green_deduction_help": {
        "sv": "2026: 50 % av arbete + material för batterilagring av egenproducerad el, 15 % för solceller (20 % för installationer 2025). "
              "Max 50 000 kr per person och år, högst 2 personer (100 000 kr). Kräver installation av företag med F-skatt "
              "(egen installation/DIY ger inget avdrag). Batteriavdraget kräver att batteriet lagrar egen solel. Avdraget dras av från investeringen i kalkylen.",
        "en": "2026: 50% of labour + material for battery storage of self-produced electricity, 15% for solar panels (20% for 2025 installs). "
              "Max 50,000 SEK per person per year, at most 2 persons (100,000 SEK). Requires installation by a company with F-skatt "
              "(DIY installs do not qualify). The battery part requires that it stores your own solar power. The deduction is subtracted from the investment.",
    },
    "green_owners_label": {"sv": "Antal ägare", "en": "Number of owners"},
    "green_owners_help": {
        "sv": "Taket är 50 000 kr per person och år. Två ägare kan dela på avdraget (max 100 000 kr).",
        "en": "The cap is 50,000 SEK per person per year. Two owners can share the deduction (max 100,000 SEK).",
    },
    "green_deduction_info": {
        "sv": "Grönt avdrag: **{total} kr** (batteri {bat} kr + solceller {sol} kr). Investering efter avdrag: {net} kr (före avdrag {gross} kr).",
        "en": "Green deduction: **{total} SEK** (battery {bat} SEK + solar {sol} SEK). Investment after deduction: {net} SEK (before deduction {gross} SEK).",
    },
    "green_no_battery_without_solar": {
        "sv": "Batteriet ger inget grönt avdrag utan solceller (avdraget gäller lagring av egenproducerad el).",
        "en": "The battery gets no green deduction without solar panels (the deduction covers storage of self-produced electricity).",
    },
    "payback_text": {"sv": "återbetald på {years:.1f} år", "en": "payback in {years:.1f} years"},
    "payback_never": {"sv": "betalar sig inte", "en": "does not pay back"},
    "rec_not_profitable": {
        "sv": "Ingen av de testade batteristorlekarna blir lönsam under batteriets livslängd med dessa förutsättningar. Rekommendationen ovan är det minst dåliga alternativet.",
        "en": "None of the tested battery sizes is profitable over the battery lifetime with these inputs. The recommendation above is the least bad option.",
    },
    "horizon_note": {
        "sv": "Kalkylhorisont = batteriets livslängd. Solcellsinvesteringen fördelas över solcellernas livslängd ({solar_life} år); endast andelen för horisonten belastar nettot. Investeringar visas efter eventuellt grönt avdrag.",
        "en": "Calculation horizon = battery lifetime. The solar investment is spread over the panels' lifetime ({solar_life} years); only the share for the horizon is charged to the net result. Investments are shown after any green deduction.",
    },
    "assumptions_header": {
        "sv": 'Antaganden bakom resultatet',
        "en": 'Assumptions behind this result',
    },
    "assume_prices": {
        "sv": 'Elpriser: historiska spotpriser {range} ({days} dagar).',
        "en": 'Electricity prices: historical spot prices {range} ({days} days).',
    },
    "assume_battery_prices": {
        "sv": 'Batteripriser (från tabellen): {prices}. Installation: {install} kr{ex_install}.',
        "en": 'Battery prices (from the table): {prices}. Installation: {install} SEK{ex_install}.',
    },
    "assume_solar_price": {
        "sv": 'Solceller {kwp} kWp{ex_kwp}: {material} kr material + {install} kr installation{ex_price}.',
        "en": 'Solar panels {kwp} kWp{ex_kwp}: {material} SEK material + {install} SEK installation{ex_price}.',
    },
    "assume_solar_existing": {
        "sv": 'Befintliga solceller {kwp} kWp{ex_kwp} (ingår inte i investeringen).',
        "en": 'Existing solar panels {kwp} kWp{ex_kwp} (not part of the investment).',
    },
    "assume_grid": {
        "sv": 'Nätbolag: {operator}, säkring {fuse} A, {phases}-fas.',
        "en": 'Grid operator: {operator}, fuse {fuse} A, {phases}-phase.',
    },
    "assume_tariff_reference": {
        "sv": 'Besparingen räknas mot att stanna på nätbolagets billigaste tariff utan investering ({tariff}). '
              'Kräver batteriet en dyrare tariff räknas merkostnaden för hela hushållets förbrukning av.',
        "en": "The saving is measured against staying on the operator's cheapest tariff without investing ({tariff}). "
              "If the battery needs a dearer tariff, the extra cost on the whole household's consumption is deducted.",
    },
    "assume_consumption_own": {
        "sv": 'Förbrukning: från din egen förbrukningsdata (Tibber, uppladdad fil eller Tibber Insights).',
        "en": 'Consumption: from your own consumption data (Tibber, uploaded file or Tibber Insights).',
    },
    "assume_consumption_house": {
        "sv": 'Förbrukning: modellerad med uppvärmningsmodellen för energiklass {eclass}, {area} m², {heating}{ex}.',
        "en": 'Consumption: modelled with the heating model for energy class {eclass}, {area} m², {heating}{ex}.',
    },
    "example_mark": {
        "sv": 'exempel',
        "en": 'example',
    },
    "example_warning": {
        "sv": 'Exempelkalkyl: följande värden är exempel och inte dina egna: {items}. '
              'Ange dina egna värden för en kalkyl som gäller ditt hus.',
        "en": 'Example calculation: these values are examples, not your own: {items}. '
              'Enter your own values for a calculation that applies to your house.',
    },
    "example_pdf_note": {
        "sv": 'Observera: kalkylen bygger delvis på exempelvärden, inte på hushållets egna uppgifter: {items}.',
        "en": "Note: the calculation partly rests on example values, not on the household's own figures: {items}.",
    },
    "example_item_battery_table": {
        "sv": 'batteripriserna (NKON-listpriser)',
        "en": 'the battery prices (NKON list prices)',
    },
    "example_item_battery_sek_kwh": {
        "sv": 'batteripriset {price} kr/kWh',
        "en": 'the battery price {price} SEK/kWh',
    },
    "example_item_battery_install": {
        "sv": 'batteriinstallationen {amount} kr',
        "en": 'the battery installation {amount} SEK',
    },
    "example_item_solar_kwp": {
        "sv": 'solcellsanläggningens storlek {kwp} kWp',
        "en": 'the solar system size {kwp} kWp',
    },
    "example_item_solar_price": {
        "sv": 'solcellspriset {material} kr material + {install} kr installation',
        "en": 'the solar price {material} SEK material + {install} SEK installation',
    },
    "example_item_house": {
        "sv": 'förbrukningen, modellerad för ett exempelhus (energiklass {eclass}, {area} m², {heating})',
        "en": 'the consumption, modelled for an example house (energy class {eclass}, {area} m², {heating})',
    },
    "assume_green_off": {
        "sv": 'Inget grönt avdrag. Standardpriserna är ett gör-det-själv-exempel (importerat batteri, egen montering av solcellerna) som inte ger avdrag.',
        "en": 'No green deduction. The default prices are a do-it-yourself example (imported battery, own mounting of the panels), which gets no deduction.',
    },
    "assume_green_on": {
        "sv": 'Grönt avdrag på {amount} kr ingår (kräver installation av företag med F-skatt).',
        "en": 'A green deduction of {amount} SEK is included (requires installation by a company with F-skatt).',
    },
    "assume_efficiency": {
        "sv": 'Tur-retur-verkningsgrad: {eff} %.',
        "en": 'Round-trip efficiency: {eff}%.',
    },
    "assume_fade": {
        "sv": 'Batteriets kapacitet, och därmed dess värde, minskar {fade} % per år.',
        "en": 'Battery capacity, and with it its value, drops {fade}% per year.',
    },
    "assume_standby": {
        "sv": 'Standbyförbrukning växelriktare + BMS: {w} W, ca {cost} kr/år.',
        "en": 'Standby consumption inverter + BMS: {w} W, about {cost} SEK/yr.',
    },
    "assume_solar_deg": {
        "sv": 'Solcellernas produktion minskar {deg} % per år.',
        "en": 'Solar production drops {deg}% per year.',
    },
    "assume_horizon": {
        "sv": 'Kalkylhorisont: batteriets livslängd, {life} år ({cycles} cykler/år).',
        "en": "Horizon: the battery's lifetime, {life} years ({cycles} cycles/yr).",
    },
    "assume_future_prices": {
        "sv": 'Framtida elpriser antas vara som under den historiska perioden (se steg 6 för andra antaganden).',
        "en": 'Future prices are assumed equal to the historical period (see step 6 for other assumptions).',
    },
    "export_compare_button": {"sv": "Kör jämförelsen", "en": "Run comparison"},
    # --- Controller check (controller_check.py) ---
    "ctrl_header": {"sv": "Klarar ett riktigt styrsystem det här?", "en": "Can a real controller do this?"},
    "ctrl_caption": {
        "sv": "Kalkylen antar att batteriet gör exakt det dygnsplanen säger, med facit i hand. Kontrollen kör i "
              "stället ett riktigt styrsystem (NORVI-styrningen, öppen källkod i energikalkyl) genom samma period, "
              "minut för minut i ett simulerat hus: det hämtar morgondagens priser kl 13:30, gissar själv husets "
              "förbrukning och solen, skriver ett program i växelriktaren (högst sex steg per dygn), delar "
              "säkringen med elbilen och vaktar den. Resultatet visar hur mycket som går förlorat på vägen.",
        "en": "The calculation assumes the battery does exactly what the day plan says, knowing the answer in "
              "advance. The check instead runs a real controller (the NORVI controller, open source in "
              "energikalkyl) through the same period, minute by minute in a simulated house: it fetches "
              "tomorrow's prices at 13:30, forecasts the house load and the sun itself, writes an inverter "
              "program (at most six steps per day), shares the fuse with the EV and guards it. The result shows "
              "how much is lost on the way.",
    },
    "ctrl_export_mode": {
        "sv": "Kontrollen finns bara för nollexport: styrsystemet säljer inte el från batteriet.",
        "en": "The check is only available for zero export: the controller doesn't sell battery power.",
    },
    "ctrl_button": {"sv": "Kör kontrollen", "en": "Run the check"},
    "ctrl_running": {
        "sv": "Kör styrsystemet genom perioden (första gången kompileras koden, upp till en minut)...",
        "en": "Running the controller through the period (the first time compiles the code, up to a minute)...",
    },
    "ctrl_unavailable": {
        "sv": "Kontrollen kunde inte köras här: {error}",
        "en": "The check could not run here: {error}",
    },
    "ctrl_metric_calc": {"sv": "Kalkylen, år 1", "en": "Calculation, year 1"},
    "ctrl_metric_ctrl": {"sv": "Med riktigt styrsystem", "en": "With a real controller"},
    "ctrl_verdict_close": {
        "sv": "Styrsystemet hamnar inom {pct:.1f} % av kalkylen: siffrorna ovan går att lita på.",
        "en": "The controller lands within {pct:.1f} % of the calculation: the figures above hold.",
    },
    "ctrl_verdict_far": {
        "sv": "Styrsystemet hamnar {pct:+.1f} % från kalkylen. Räkna med den lägre siffran.",
        "en": "The controller lands {pct:+.1f} % from the calculation. Count on the lower figure.",
    },
    "ctrl_step_parity": {"sv": "Samma planering som kalkylen (ska vara 0)",
                         "en": "Same planning as the calculation (should be 0)"},
    "ctrl_step_program": {"sv": "Planen som växelriktarprogram (högst {n} steg per dygn)",
                          "en": "The plan as an inverter program (at most {n} steps per day)"},
    "ctrl_step_controller": {
        "sv": "Det riktiga styrsystemet: egen prognos, elbil och batteri delar {fuse} A-säkringen "
              "({reserve:.1f} kW reserv för huset), säkringsvakt, växelriktaren kör programmet",
        "en": "The real controller: its own forecast, EV and battery share the {fuse} A fuse "
              "({reserve:.1f} kW reserve for the house), fuse guard, the inverter runs the program",
    },
    "ctrl_step_ev_cost": {"sv": "Elbilens laddning ({calc:.2f} → {ctrl:.2f} kr/kWh)",
                          "en": "EV charging ({calc:.2f} → {ctrl:.2f} SEK/kWh)"},
    "ctrl_step_total": {"sv": "Summa", "en": "Total"},
    "ctrl_col_step": {"sv": "Steg", "en": "Step"},
    "ctrl_col_kr": {"sv": "kr/år", "en": "SEK/yr"},
    "ctrl_years_expander": {"sv": "Per år", "en": "Per year"},
    "ctrl_col_year": {"sv": "År", "en": "Year"},
    "ctrl_col_days": {"sv": "Dagar", "en": "Days"},
    "ctrl_col_calc": {"sv": "Kalkylen, batteri kr/år", "en": "Calculation, battery SEK/yr"},
    "ctrl_col_ctrl": {"sv": "Styrsystemet, kr/år", "en": "Controller, SEK/yr"},
    "ctrl_col_diff": {"sv": "Skillnad", "en": "Difference"},
    "ctrl_notes": {
        "sv": "Styrsystemets kod: NORVI-styrningen version {version}, samma kod som i simulatorn "
              "energy-scheduler-sim. Ingår inte: effektavgift och export (styrsystemet säljer inte). Skillnaden "
              "räknas på batteriets och elbilens el; den läggs på kalkylens besparing år 1.",
        "en": "Controller code: NORVI controller version {version}, the same code as in the energy-scheduler-sim "
              "simulator. Not included: power tariff and export (the controller doesn't sell). The difference is "
              "counted on the battery's and the EV's electricity and applied to the calculation's year-1 saving.",
    },
    "ctrl_learn_note": {
        "sv": " Styrsystemet planerar husets förbrukning efter utetemperaturen (SMHI-stationens mätningar i "
              "stället för prognos) och lärde sig huset under {days} dagar, som det gör på plats.",
        "en": " The controller plans the house's consumption from the outdoor temperature (the SMHI station's "
              "measurements in place of a forecast) and learned the house over {days} days, as it does on site.",
    },
    "ctrl_ev_note": {
        "sv": " Elbil: {daily:.1f} kWh/dygn; styrsystemet planerar {ctrl:,.0f} kWh/år mot kalkylens {calc:,.0f} "
              "(laddaren går i hela ampere, minst 6 A).",
        "en": " EV: {daily:.1f} kWh/day; the controller plans {ctrl:,.0f} kWh/yr against the calculation's "
              "{calc:,.0f} (the charger runs in whole amps, at least 6 A).",
    },
    # --- Energy flows ---
    "flow_header": {"sv": "Så flödar energin — {label}", "en": "How the energy flows — {label}"},
    "flow_caption": {
        "sv": "Ett genomsnittligt år: varifrån elen kommer (sol, elnät, batteri) och vart den tar vägen. "
              "Håll muspekaren över ett flöde för att se kWh per år.",
        "en": "An average year: where the electricity comes from (sun, grid, battery) and where it goes. "
              "Hover over a flow to see kWh per year.",
    },
    "flow_solar": {"sv": "Sol", "en": "Sun"},
    "flow_grid": {"sv": "Elnät", "en": "Grid"},
    "flow_battery": {"sv": "Batteri", "en": "Battery"},
    "flow_house": {"sv": "Huset", "en": "House"},
    "flow_ev": {"sv": "Elbil", "en": "EV"},
    "flow_flex": {"sv": "Varmvatten/flexlaster", "en": "Hot water/flex loads"},
    "flow_export": {"sv": "Såld till nätet", "en": "Sold to the grid"},
    "flow_curtailed": {"sv": "Spill (solel som inte togs till vara)", "en": "Curtailed solar"},
    "flow_losses": {"sv": "Batteriförluster", "en": "Battery losses"},
    "flow_battery_charging": {"sv": "Batteriet laddas", "en": "Battery charging"},
    "flow_day_pick": {"sv": "Visa en dag", "en": "Show a day"},
    "flow_day_help": {
        "sv": "Förvald är dagen då batteriet levererade mest. Välj vilken dag som helst i perioden.",
        "en": "Preselected is the day the battery delivered the most. Pick any day in the period.",
    },
    "flow_day_from": {"sv": "Varifrån elen kom (kWh per timme)", "en": "Where the power came from (kWh per hour)"},
    "flow_day_to": {"sv": "Vart den tog vägen", "en": "Where it went"},
    "flow_day_from_short": {"sv": "Från", "en": "From"},
    "flow_day_to_short": {"sv": "Till", "en": "To"},
    "flow_day_battery": {"sv": "Energi i batteriet", "en": "Energy in the battery"},
    "flow_day_price": {"sv": "Elpris inkl. nät och skatt", "en": "Electricity price incl. grid and tax"},
    "flow_day_hour": {"sv": "Timme", "en": "Hour"},
    "flow_day_summary": {
        "sv": "Dagen: {solar:.0f} kWh från solen, {battery:.0f} kWh från batteriet, {grid:.0f} kWh från "
              "elnätet; batteriet laddades med {charged:.0f} kWh.",
        "en": "The day: {solar:.0f} kWh from the sun, {battery:.0f} kWh from the battery, {grid:.0f} kWh from "
              "the grid; the battery was charged with {charged:.0f} kWh.",
    },
    "flow_day_missing": {"sv": "Ingen data för den dagen.", "en": "No data for that day."},
    "player_header": {"sv": "Spela upp hela perioden", "en": "Play back the whole period"},
    "player_caption": {
        "sv": "Följ energin timme för timme genom all data: tryck Spela, välj hastighet eller dra i reglaget. "
              "Linjernas tjocklek och fart följer effekten. Vid högre hastighet visas medeleffekten över de timmar "
              "som passerar.",
        "en": "Follow the energy hour by hour through all the data: press Play, pick a speed or drag the slider. "
              "Line width and speed follow the power. At higher speeds the average power over the hours that pass "
              "is shown.",
    },
    "player_play": {"sv": "Spela", "en": "Play"},
    "player_pause": {"sv": "Pausa", "en": "Pause"},
    "player_price": {"sv": "Elpris inkl. nät och skatt", "en": "Price incl. grid and tax"},
    "player_since": {"sv": "Sedan periodens början", "en": "Since the start of the period"},
    "player_saved": {"sv": "Batteriet har sparat", "en": "The battery has saved"},
    "player_solarUsed": {"sv": "Solel tagen till vara", "en": "Solar power used"},
    "player_bought": {"sv": "Köpt från elnätet", "en": "Bought from the grid"},
    "player_curtailedTotal": {"sv": "Spill (solel som inte togs till vara)", "en": "Curtailed solar"},
    "player_curtailed": {"sv": "Spill", "en": "Curtailed"},
    "player_hourly": {"sv": "Timme för timme", "en": "Hour by hour"},
    "player_average": {"sv": "Medeleffekt {from} – {to}", "en": "Average power {from} – {to}"},
    "player_aria": {"sv": "Energiflöden mellan sol, elnät, batteri och förbrukning",
                    "en": "Energy flows between sun, grid, battery and consumption"},
    "player_charging": {"sv": "laddar", "en": "charging"},
    "player_discharging": {"sv": "levererar", "en": "delivering"},
    "player_speed_0": {"sv": "1 timme/s", "en": "1 hour/s"},
    "player_speed_1": {"sv": "6 timmar/s", "en": "6 hours/s"},
    "player_speed_2": {"sv": "1 dygn/s", "en": "1 day/s"},
    "player_speed_3": {"sv": "1 vecka/s", "en": "1 week/s"},
    "player_speed_4": {"sv": "1 månad/s", "en": "1 month/s"},
    "current_tariff_label": {"sv": "Din nuvarande tariff", "en": "Your current tariff"},
    "current_tariff_unknown": {"sv": "Vet inte", "en": "Don't know"},
    "current_tariff_help": {
        "sv": "Tariffen du har idag (står på nätfakturan). Kalkylen testar ändå alla nätbolagets "
              "tariffer; detta visar vad enbart ett tariffbyte sparar, utan investering.",
        "en": "The tariff you have today (on your grid bill). The calculation tests all of the operator's "
              "tariffs anyway; this shows what switching tariff alone saves, without investing.",
    },
    "current_tariff_keep": {
        "sv": "Du har redan **{tariff}**, den tariff kalkylen väljer. Inget tariffbyte behövs.",
        "en": "You already have **{tariff}**, the tariff the calculation picks. No tariff switch needed.",
    },
    "current_tariff_change": {
        "sv": "Du har **{current}** idag; kalkylen förutsätter **{best}**.",
        "en": "You have **{current}** today; the calculation assumes **{best}**.",
    },
    "current_tariff_switch_saving": {
        "sv": "Bara att byta till {cheapest} sänker räkningen med **{saving:,.0f} kr/år redan utan "
              "investering** — det är inte medräknat i investeringens lönsamhet. Byte + {label} "
              "tillsammans: **{total:,.0f} kr/år lägre än idag** (år 1).",
        "en": "Just switching to {cheapest} lowers the bill by **{saving:,.0f} SEK/yr without investing** "
              "— this is not counted in the investment's profitability. Switch + {label} together: "
              "**{total:,.0f} SEK/yr lower than today** (year 1).",
    },
    "assume_current_tariff": {
        "sv": "Din nuvarande tariff: {tariff}. Ett tariffbyte kräver ingen investering och räknas därför inte in i lönsamheten.",
        "en": "Your current tariff: {tariff}. A tariff switch needs no investment, so it is not counted in the profitability.",
    },
    "scen_export_header": {
        "sv": "Sälja eller använda själv — i varje framtidsscenario",
        "en": "Sell or use yourself — in each future scenario",
    },
    "scen_export_caption": {
        "sv": "Lönar det sig att sälja el till nätet om priserna svänger mer? Samma batteri och "
              "samma fem scenarier, simulerat både med nollexport och med export (fullt spotpris "
              "− 5 öre/kWh). En kWh du använder själv sparar spot + moms + energiskatt + "
              "överföringsavgift, en såld kWh ger bara spotpriset — så export lönar sig bara för el "
              "huset inte kan använda.",
        "en": "Does selling to the grid pay off if prices swing more? Same battery and the same "
              "five scenarios, simulated both with zero export and with export (full spot "
              "− 5 öre/kWh). A kWh you use yourself saves spot + VAT + energy tax + grid fee, a "
              "sold kWh earns only the spot price — so export only pays for power the house "
              "can't use.",
    },
    "scen_export_button": {
        "sv": "Jämför med {mode} i alla scenarier",
        "en": "Compare with {mode} in all scenarios",
    },
    "scen_export_col_mode": {
        "sv": "Netto, {mode}",
        "en": "Net, {mode}",
    },
    "scen_export_col_diff": {
        "sv": "Skillnad med {mode}",
        "en": "Difference with {mode}",
    },
    "scen_export_col_better": {
        "sv": "Bäst",
        "en": "Better",
    },
    "scen_export_never": {
        "sv": "**{zero} är bäst i alla fem scenarier** — även om prissvängningarna blir "
              "extremt större lönar det sig inte att sälja el för just ditt hus och batteri.",
        "en": "**{zero} is better in all five scenarios** — even if price swings become "
              "extremely larger, selling does not pay off for your house and battery.",
    },
    "scen_export_always": {
        "sv": "**{export} är bäst i alla fem scenarier** — redan med dagens prissvängningar.",
        "en": "**{export} is better in all five scenarios** — already with today's price swings.",
    },
    "scen_export_some": {
        "sv": "**{export} är bäst i:** {scenarios}. I övriga scenarier är {zero} bäst.",
        "en": "**{export} is better in:** {scenarios}. In the other scenarios {zero} is better.",
    },
    "scen_export_assumptions": {
        "sv": "Netto över batteriets livslängd, samma bokföring som huvudresultatet (slitage, "
              "standby, säkringsavgift). Livslängd och solelsvärde hålls på dagens nivå i varje "
              "scenario: {life_cur:.0f} år nu, {life_oth:.0f} år med {mode} (fler/färre cykler). "
              "Skalade priser går aldrig under 0, så negativa priser (då export kostar pengar) "
              "finns inte med — det gör export något för positiv. Export kräver "
              "mikroproducentregistrering, exportavtal och en växelriktare som får mata ut. "
              "Ersättning för stödtjänster till nätet ingår inte.",
        "en": "Net over the battery lifetime, same accounting as the main result (wear, standby, "
              "fuse fee). Lifetime and solar value are held at today's level in every scenario: "
              "{life_cur:.0f} yr now, {life_oth:.0f} yr with {mode} (more/fewer cycles). "
              "Scaled prices never go below 0, so negative prices (when exporting costs money) "
              "are not included — this makes export look slightly too good. Export requires "
              "microproducer registration, an export agreement and an inverter allowed to feed "
              "the grid. Payments for grid services are not included.",
    },
    "detail_green_deduction": {"sv": "Grönt avdrag", "en": "Green deduction"},
}


def _session_state():
    """Return Streamlit's per-session state when running inside a Streamlit script, else None.

    The language must be per visitor session: a module global would be shared by all
    concurrent sessions in the same server process.
    """
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx(suppress_warning=True) is None:
            return None
        import streamlit as st
        return st.session_state
    except Exception:
        return None


def set_language(lang: str):
    """Set the current language ('sv' or 'en') for this session (or process, outside Streamlit)."""
    global _lang
    ss = _session_state()
    if ss is not None:
        ss["app_language"] = lang
    else:
        _lang = lang


def get_language() -> str:
    """Get the current language."""
    ss = _session_state()
    if ss is not None:
        return ss.get("app_language", "sv")
    return _lang


def t(key: str) -> str:
    """Get translated string for the current language."""
    entry = STRINGS.get(key)
    if entry is None:
        return f"[{key}]"
    lang = get_language()
    return entry.get(lang, entry.get("sv", f"[{key}]"))
