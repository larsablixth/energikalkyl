"""
Energikalkyl — El, Sol & Batteri (Web GUI)

Analysverktyg för att bedöma lönsamhet i hembatteri och solceller.
Start with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from elpriser import fetch_range, load_csv, ZONES, ZONE_NAMES
from batteri import BatteryConfig, LoadSchedule, FlexibleLoad, simulate
from solar import SolarConfig, estimate_yearly_production, estimate_lifetime_production
from tariff import (
    Tidstariff, FastTariff, EffektTariff,
    FUSE_YEARLY_FEE, get_fuse_fee_monthly, get_fuse_fee_yearly,
    GRID_OPERATORS, get_operator_fuse_fees, create_tariffs_for_operator,
)
from heating import (
    HeatingConfig, heating_electricity_kw,
    fit_heating_model, hourly_consumption_profile,
)
from weather import (
    load_temperatures, get_stations, find_nearest_station,
    fetch_station_data, SWEDISH_CITIES,
)
from report import generate_report

st.set_page_config(page_title="Energikalkyl", page_icon="⚡", layout="wide")
st.title("Energikalkyl — El, Sol & Batteri")
st.caption("Simulera lönsamheten i hembatteri och solceller baserat på verkliga elpriser och din förbrukning.")

# ================================================================
# STEP 1: LOAD DATA
# ================================================================
st.header("1. Ladda data")

col_prices, col_consumption = st.columns(2)

# --- Price data ---
with col_prices:
    st.subheader("Elpriser (spotpris)")
    st.caption("Historiska spotpriser behövs för simuleringen. Ju mer data, desto bättre resultat.")
    price_source = st.radio("Källa", ["Hämta från API", "Ladda CSV"], key="price_src",
                             help="API hämtar från elprisetjustnu.se. CSV om du har en egen fil.")

    if price_source == "Ladda CSV":
        price_file = st.file_uploader("Pris-CSV", type=["csv"], key="price_csv",
                                       help="CSV med kolumner: date, hour, sek_per_kwh")
        if price_file:
            df_prices = pd.read_csv(price_file)
            st.session_state["df_prices"] = df_prices
        else:
            df_prices = st.session_state.get("df_prices")
    else:
        zone = st.selectbox("Elområde", ZONES, index=2,
                            format_func=lambda z: f"{z} — {ZONE_NAMES[z]}")
        col_d1, col_d2 = st.columns(2)
        start_date = col_d1.date_input("Från", value=date.today() - timedelta(days=3*365))
        end_date = col_d2.date_input("Till", value=date.today() - timedelta(days=1))
        if st.button("Hämta priser", type="primary"):
            with st.spinner("Hämtar spotpriser..."):
                rows = fetch_range(start_date, end_date, zone)
                if rows:
                    df_prices = pd.DataFrame(rows)
                    st.session_state["df_prices"] = df_prices
                else:
                    st.error("Inga priser hittades. Kontrollera datum och elområde.")
        else:
            df_prices = st.session_state.get("df_prices")

    if df_prices is not None and len(df_prices) > 0:
        for col in ["sek_per_kwh", "ore_per_kwh"]:
            if col in df_prices.columns:
                df_prices[col] = pd.to_numeric(df_prices[col], errors="coerce")
        n_days = df_prices["date"].nunique()
        st.success(f"Prisdata laddad: **{n_days} dagar** ({df_prices['date'].min()} → {df_prices['date'].max()})")
    else:
        st.warning("Ladda spotpriser ovan för att kunna köra simuleringen.")

# --- Consumption data ---
with col_consumption:
    st.subheader("Förbrukningsprofil (valfritt)")
    st.caption("Ger bättre resultat om du har den. Annars används standardvärden i steg 2.")
    cons_source = st.radio("Källa", ["Manuell", "Tibber API", "Vattenfall/CSV/Excel"], key="cons_src",
                             help="Manuell = ange grundlast och laster i steg 2. Tibber/Vattenfall = importera din faktiska profil.")

    hourly_load_profile = None
    seasonal_load_profile = None

    if cons_source == "Tibber API":
        st.caption("Kräver .tibber_token-fil med din Tibber API-nyckel.")
        if st.button("Hämta från Tibber"):
            with st.spinner("Hämtar förbrukningsprofil från Tibber..."):
                try:
                    from tibber_source import (
                        fetch_consumption, consumption_to_load_profile,
                        fetch_monthly_consumption, build_seasonal_hourly_profile,
                    )
                    nodes = fetch_consumption(hours=24*30)
                    profile = consumption_to_load_profile(nodes)
                    st.session_state["hourly_profile"] = profile
                    monthly = fetch_monthly_consumption(months=36)
                    if len(monthly) >= 6:
                        seasonal = build_seasonal_hourly_profile(nodes, monthly)
                        st.session_state["seasonal_profile"] = seasonal
                    st.success("Förbrukningsprofil laddad från Tibber")
                except Exception as e:
                    st.error(f"Tibber-fel: {e}")

    elif cons_source == "Vattenfall/CSV/Excel":
        st.caption("Ladda upp Excel-filer från Vattenfall Mina sidor, eller CSV med timförbrukning.")
        cons_files = st.file_uploader("Förbrukningsdata", type=["csv", "txt", "xlsx", "xls"],
                                       accept_multiple_files=True, key="cons_upload")
        if cons_files:
            try:
                import tempfile, os
                all_vf = []
                all_csv = []
                for f in cons_files:
                    if f.name.lower().endswith((".xlsx", ".xls")):
                        from import_vattenfall import parse_vattenfall_excel
                        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                            tmp.write(f.getvalue())
                            tmp_path = tmp.name
                        try:
                            all_vf.extend(parse_vattenfall_excel(tmp_path))
                        finally:
                            os.unlink(tmp_path)
                    else:
                        from import_consumption import parse_consumption_csv
                        raw = f.getvalue()
                        for enc in ["utf-8", "utf-8-sig", "iso-8859-1", "cp1252"]:
                            try:
                                all_csv.extend(parse_consumption_csv(raw.decode(enc), f.name))
                                break
                            except (UnicodeDecodeError, ValueError):
                                continue

                if all_vf:
                    from import_vattenfall import vattenfall_to_seasonal_profile
                    seen = set()
                    unique = sorted([r for r in all_vf if r["date"] not in seen and not seen.add(r["date"])],
                                    key=lambda x: x["date"])
                    hourly_shape = st.session_state.get("hourly_profile")
                    seasonal = vattenfall_to_seasonal_profile(unique, hourly_shape)
                    st.session_state["seasonal_profile"] = seasonal
                    total = sum(r["consumption_kwh"] for r in unique)
                    avg = total / len(unique)
                    st.success(f"Förbrukning laddad: **{len(unique)} dagar** | Snitt: {avg:.0f} kWh/dag | ~{avg*365:,.0f} kWh/år")
                elif all_csv:
                    from import_consumption import consumption_to_hourly_profile, consumption_to_monthly_daily
                    profile = consumption_to_hourly_profile(all_csv)
                    st.session_state["hourly_profile"] = profile
                    monthly = consumption_to_monthly_daily(all_csv)
                    if sum(1 for v in monthly.values() if v > 0) >= 6:
                        base = sum(profile.values())
                        seasonal = {m: {h: profile[h] * (monthly[m]/base if base > 0 and monthly[m] > 0 else 1)
                                        for h in range(24)} for m in range(1, 13)}
                        st.session_state["seasonal_profile"] = seasonal
                    st.success(f"Förbrukning laddad: **{len(all_csv)} datapunkter**")
            except Exception as e:
                st.error(f"Importfel: {e}")

    # Show loaded profile status
    if "seasonal_profile" in st.session_state:
        seasonal_load_profile = st.session_state["seasonal_profile"]
        all_kw = [kw for m in seasonal_load_profile.values() for kw in m.values()]
        st.info(f"Förbrukningsprofil: säsongsanpassad, {min(all_kw):.1f}–{max(all_kw):.1f} kW")
    elif "hourly_profile" in st.session_state:
        hourly_load_profile = st.session_state["hourly_profile"]
        avg = sum(hourly_load_profile.values()) / 24
        st.info(f"Förbrukningsprofil: timvis, medel {avg:.1f} kW")
    elif cons_source == "Manuell":
        st.info("Ange grundlast och laster i steg 2 nedan.")

# --- Data status summary ---
if df_prices is None or len(df_prices) == 0:
    st.error("**Steg 1 ej klart** — ladda spotpriser ovan för att fortsätta.")
    st.stop()
else:
    has_consumption = "seasonal_profile" in st.session_state or "hourly_profile" in st.session_state
    if has_consumption:
        st.success("**Data laddad.** Konfigurera din anläggning nedan och kör simuleringen.")
    else:
        st.info("**Prisdata laddad.** Förbrukningsprofil saknas — standardvärden används. "
                "Konfigurera din anläggning nedan.")

# ================================================================
# SPREAD ANALYSIS (always shown, informational)
# ================================================================
df_plot = df_prices.copy()
df_plot["datetime"] = pd.to_datetime(df_plot["date"] + " " + df_plot["hour"])
spread_data = []
for day, group in df_plot.groupby("date"):
    hourly = group.groupby(group["datetime"].dt.hour)["ore_per_kwh"].mean()
    sorted_p = hourly.sort_values()
    n = min(4, len(sorted_p))
    cheap = sorted_p.iloc[:n].mean()
    rest = sorted_p.iloc[n:].mean() if len(sorted_p) > n else 0
    spread_data.append({"date": day, "cheap": round(cheap, 1), "rest": round(rest, 1),
                        "spread": round(rest - cheap, 1)})
df_spread = pd.DataFrame(spread_data)
df_spread["datetime"] = pd.to_datetime(df_spread["date"])
df_spread["month"] = pd.to_datetime(df_spread["date"]).dt.to_period("M").astype(str)

with st.expander(f"Prisspridning i din data (snitt {df_spread['spread'].mean():.0f} öre/kWh)", expanded=False):
    col1, col2, col3 = st.columns(3)
    col1.metric("Snitt billigaste 4h", f"{df_spread['cheap'].mean():.0f} öre/kWh")
    col2.metric("Snitt övriga 20h", f"{df_spread['rest'].mean():.0f} öre/kWh")
    col3.metric("Snitt spread", f"{df_spread['spread'].mean():.0f} öre/kWh")
    fig_sp = go.Figure()
    fig_sp.add_trace(go.Scatter(x=df_spread["datetime"], y=df_spread["spread"],
                                 mode="lines", name="Daglig spread", line=dict(width=1, color="#f39c12")))
    monthly_spread = df_spread.groupby("month")["spread"].mean().reset_index()
    monthly_spread["datetime"] = pd.to_datetime(monthly_spread["month"])
    fig_sp.add_trace(go.Scatter(x=monthly_spread["datetime"], y=monthly_spread["spread"],
                                 mode="lines+markers", name="Månadsmedel", line=dict(width=3, color="#e74c3c")))
    fig_sp.update_layout(yaxis_title="Spread (öre/kWh)", height=300, margin=dict(l=0, r=0, t=30, b=0),
                          legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig_sp, use_container_width=True)

# ================================================================
# STEP 2: YOUR SYSTEM
# ================================================================
st.header("2. Din anläggning")
st.caption("Beskriv ditt hus, elnät och elanvändare. Uppvärmningsmodellen anpassas automatiskt efter din plats och hustyp.")

col_sys1, col_sys2, col_sys3 = st.columns(3)

with col_sys1:
    st.subheader("Batteri")
    efficiency = st.slider("Verkningsgrad (%)", 70, 100, 93, help="Tur-retur-verkningsgrad. Gäller alla batteristorlekar.") / 100
    cycle_life = st.number_input("Cykellivslängd", value=8000, min_value=100, step=500,
                                  help="Antal cykler innan batteriet tappar kapacitet. LiFePO4: typiskt 6000-8000.")

with col_sys2:
    st.subheader("Solceller")
    use_solar = st.checkbox("Solceller", value=True)
    if use_solar:
        solar_kwp = st.number_input("System (kWp)", value=15.0, min_value=0.0, step=0.5)
        export_factor = st.number_input("Exportpris (andel av spot)", value=1.0, min_value=0.0, max_value=1.5, step=0.05)
        export_fee = st.number_input("Exportavgift (öre/kWh)", value=5.0, min_value=0.0, step=1.0)
        solar_config = SolarConfig(capacity_kwp=solar_kwp) if solar_kwp > 0 else None
    else:
        solar_config = None
        solar_kwp = 0
        export_factor = 1.0
        export_fee = 5.0

with col_sys3:
    st.subheader("Elnät")
    grid_operator = st.selectbox("Nätägare", list(GRID_OPERATORS.keys()), index=0,
                                  help="Din elnätsägare (står på elnätsfakturan). Avgör tariffer och avgifter.")
    op_info = GRID_OPERATORS[grid_operator]
    op_fuse_fees = get_operator_fuse_fees(grid_operator)
    fuse_options = sorted(op_fuse_fees.keys())
    fuse_amps = st.selectbox("Säkring (A)", fuse_options,
                              index=fuse_options.index(25) if 25 in fuse_options else 0)
    phases = st.selectbox("Faser", [3, 1], index=0)
    energy_tax = st.number_input("Energiskatt (öre/kWh)", value=54.88, step=0.1,
                                  help="43.90 öre + 25% moms = 54.88 (2026)")
    available_tariffs = op_info["tariffs"]
    has_effekt = "Effekttariff" in available_tariffs and op_info.get("effekttariff")
    if has_effekt:
        eff = op_info["effekttariff"]
        st.info(f"**{grid_operator}** har effekttariff: "
                f"{eff['effekt_rate']} kr/kW/mån, "
                f"{eff['energy_rate']} öre/kWh")
    else:
        st.info(f"**{grid_operator}**: {', '.join(available_tariffs)} — "
                f"alla simuleras, bästa väljs")
    with st.expander("Tariffdetaljer", expanded=False):
        if "tidstariff" in op_info:
            t = op_info["tidstariff"]
            peak_rate = st.number_input("Tidstariff höglast (öre/kWh)", value=t["peak"], step=0.5)
            offpeak_rate = st.number_input("Tidstariff övrig (öre/kWh)", value=t["offpeak"], step=0.5)
        else:
            peak_rate = 76.5
            offpeak_rate = 30.5
        if "enkeltariff" in op_info:
            t = op_info["enkeltariff"]
            flat_rate = st.number_input("Enkeltariff (öre/kWh)", value=t["flat_rate"], step=0.5)
        else:
            flat_rate = 44.5
        if has_effekt:
            eff = op_info["effekttariff"]
            effekt_rate = st.number_input("Effektavgift (kr/kW/mån)", value=eff["effekt_rate"], step=1.0)
            effekt_energy = st.number_input("Effekt energiavgift (öre/kWh)", value=eff["energy_rate"], step=0.5)
            effekt_top_n = st.number_input("Antal toppar", value=eff["top_n_peaks"], min_value=1, max_value=10)
        monthly_fee = op_fuse_fees.get(fuse_amps, 0) / 12
        st.caption(f"Abonnemang: {monthly_fee:,.0f} kr/mån ({op_fuse_fees.get(fuse_amps, 0):,.0f} kr/år)")

# Loads
st.subheader("Elanvändare")
st.caption("Laster utöver uppvärmning. EV och pool hanteras separat från hushållets grundlast.")
col_l1, col_l2 = st.columns(2)

with col_l1:
    if not (seasonal_load_profile or hourly_load_profile):
        base_load = st.number_input("Grundlast (kW)", value=1.5, min_value=0.0, step=0.5,
                                    help="Hushållets ständiga förbrukning. Ignoreras om uppvärmningsmodellen är aktiv.")
    else:
        base_load = 1.5  # overridden by profile or heating model

    if "scheduled_loads" not in st.session_state:
        st.session_state["scheduled_loads"] = [{"name": "Elbil", "power": 11.0, "start": 23, "end": 6}]

    st.markdown("**Tidsstyrda laster**")
    st.caption("Laster som alltid körs under specifika timmar, t.ex. elbil nattetid.")
    for i, load in enumerate(st.session_state["scheduled_loads"]):
        c = st.columns([3, 2, 2, 2, 1])
        load["name"] = c[0].text_input("", value=load["name"], key=f"ln_{i}", label_visibility="collapsed")
        load["power"] = c[1].number_input("kW", value=load["power"], min_value=0.0, step=0.5, key=f"lp_{i}")
        load["start"] = c[2].number_input("Från", value=load["start"], min_value=0, max_value=23, key=f"ls_{i}")
        load["end"] = c[3].number_input("Till", value=load["end"], min_value=0, max_value=23, key=f"le_{i}")
        if c[4].button("X", key=f"lx_{i}"):
            st.session_state["scheduled_loads"].pop(i)
            st.rerun()

    if st.button("+ Last"):
        st.session_state["scheduled_loads"].append({"name": "Ny", "power": 1.0, "start": 0, "end": 6})
        st.rerun()

with col_l2:
    if "flexible_loads" not in st.session_state:
        st.session_state["flexible_loads"] = [{"name": "Poolpump", "power": 3.0, "daily": 20.0, "sm": 5, "em": 9}]

    _month_names = ["Jan", "Feb", "Mar", "Apr", "Maj", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]
    _month_opts = list(range(1, 13))

    st.markdown("**Flexibla laster** (solöverskott)")
    st.caption("Körs när solöverskott finns. T.ex. poolpump, varmvattenberedare.")
    for i, fl in enumerate(st.session_state["flexible_loads"]):
        c = st.columns([3, 2, 2, 2, 2, 1])
        fl["name"] = c[0].text_input("", value=fl["name"], key=f"fn_{i}", label_visibility="collapsed")
        fl["power"] = c[1].number_input("kW", value=fl["power"], min_value=0.0, step=0.5, key=f"fp_{i}")
        fl["daily"] = c[2].number_input("Max kWh per dag", value=fl["daily"], min_value=0.0, step=1.0, key=f"fd_{i}",
                                       help=f"Max energi per dag. {fl['power']} kW × {fl['daily']/fl['power']:.0f}h = {fl['daily']:.0f} kWh" if fl["power"] > 0 else "")
        fl["sm"] = c[3].selectbox("Aktiv från", _month_opts, index=fl["sm"]-1,
                                   format_func=lambda m: _month_names[m-1], key=f"fs_{i}")
        fl["em"] = c[4].selectbox("Aktiv till", _month_opts, index=fl["em"]-1,
                                   format_func=lambda m: _month_names[m-1], key=f"fe_{i}")
        if c[5].button("X", key=f"fx_{i}"):
            st.session_state["flexible_loads"].pop(i)
            st.rerun()

    if st.button("+ Flexibel last"):
        st.session_state["flexible_loads"].append({"name": "Ny", "power": 2.0, "daily": 10.0, "sm": 1, "em": 12})
        st.rerun()

scheduled_loads = [LoadSchedule(l["name"], l["power"], l["start"], l["end"])
                   for l in st.session_state["scheduled_loads"] if l["power"] > 0]
flexible_loads = [FlexibleLoad(f["name"], f["power"], f["daily"], f["sm"], f["em"])
                  for f in st.session_state["flexible_loads"] if f["power"] > 0]

# Heating model
st.subheader("Uppvärmning")
use_heating_model = st.checkbox("Temperaturanpassad lastmodell", value=True,
                                 help="Modellerar värmepumpens elförbrukning baserat på väderdata och husets egenskaper")
daily_load_override = None
heating_config = None

if use_heating_model:
    # --- Location selection ---
    st.markdown("**Plats (för väderdata)**")
    city_names = sorted(SWEDISH_CITIES.keys())
    col_loc1, col_loc2 = st.columns([2, 3])
    with col_loc1:
        selected_city = st.selectbox("Stad / ort", city_names,
                                      index=city_names.index("Sigtuna") if "Sigtuna" in city_names else 0,
                                      help="Välj den ort som är närmast dig. Bestämmer vilken SMHI-station som används.")
    city_lat, city_lon = SWEDISH_CITIES[selected_city]

    # Find nearest SMHI station
    try:
        stations = get_stations()
    except Exception:
        stations = {"97400": ("Stockholm-Arlanda Flygplats", 59.6269, 17.9545)}
    station_id, station_name, station_dist = find_nearest_station(city_lat, city_lon, stations)

    with col_loc2:
        st.caption(f"Närmaste SMHI-station: **{station_name}** ({station_dist:.0f} km)")
        # Allow manual override
        with st.expander("Välj annan station", expanded=False):
            station_list = sorted(stations.items(), key=lambda x: x[1][0])
            station_options = {f"{name} ({sid})": sid for sid, (name, _, _) in station_list}
            default_key = f"{station_name} ({station_id})"
            selected_station = st.selectbox("Station", list(station_options.keys()),
                                             index=list(station_options.keys()).index(default_key)
                                             if default_key in station_options else 0)
            station_id = station_options[selected_station]
            station_name = selected_station.split(" (")[0]

    # Load or fetch temperature data
    temps_data = load_temperatures(station_id=station_id)
    if not temps_data:
        with st.spinner(f"Hämtar väderdata från {station_name}..."):
            try:
                fetch_station_data(station_id)
                temps_data = load_temperatures(station_id=station_id)
            except Exception as e:
                st.warning(f"Kunde inte hämta väderdata: {e}")

    if temps_data:
        # --- House calibration ---
        st.markdown("**Ditt hus**")
        st.caption("Välj energiklass och yta för att uppskatta värmeförlust. "
                   "Har du förbrukningsdata (Tibber/Vattenfall) kalibreras modellen automatiskt.")

        # Energy class → h_loss lookup (for ground-source heat pump, COP_avg ~3.2)
        # Computed from: h_loss = (energy_class × area - DHW_elec - vent_elec) × COP / degree_hours
        # Stockholm degree-hours ~123,000 °C·h/year, DHW ~2190 kWh/yr, vent ~750 kWh/yr
        _DEGREE_HOURS = 123000
        _COP_AVG = 3.2
        _DHW_ANNUAL = 2190
        _VENT_ANNUAL = 750

        _ENERGY_CLASSES = {
            "A (≤50 kWh/m²) — Passivhus": 50,
            "B (51-75 kWh/m²) — Nybyggt": 63,
            "C (76-100 kWh/m²) — Bra renoverat": 88,
            "D (101-130 kWh/m²) — Standard 1990-2010": 115,
            "E (131-160 kWh/m²) — Äldre hus": 145,
            "F (161-190 kWh/m²) — Dåligt isolerat": 175,
            "G (>190 kWh/m²) — Mycket dåligt isolerat": 220,
        }

        col_house1, col_house2 = st.columns(2)
        with col_house1:
            energy_class = st.selectbox("Energiklass (energideklaration)",
                                         list(_ENERGY_CLASSES.keys()), index=2,
                                         help="Finns i husets energideklaration. Vet du inte? "
                                              "Klass C-D är vanligast för hus byggda 1990-2020.")
            house_area = st.number_input("Boyta (m²)", value=150, min_value=30, max_value=500, step=10)

        # Derive h_loss from energy class + area
        kwh_m2 = _ENERGY_CLASSES[energy_class]
        bldg_energy = kwh_m2 * house_area
        heat_elec_est = max(0, bldg_energy - _DHW_ANNUAL - _VENT_ANNUAL)
        h_loss_default = round(heat_elec_est * _COP_AVG / _DEGREE_HOURS, 3)

        with col_house2:
            heating_type = st.selectbox("Uppvärmning", [
                "Bergvärme (mark/sjö)", "Luftvärmepump", "Fjärrvärme", "Direktel (element)"
            ], help="Typ av värmekälla. Påverkar COP-beräkningen.")

            if heating_type == "Bergvärme (mark/sjö)":
                cop_info = "COP 2.3–5.0 beroende på utetemperatur"
            elif heating_type == "Luftvärmepump":
                cop_info = "COP 1.5–4.5, sämre vid kyla"
            elif heating_type == "Fjärrvärme":
                cop_info = "Ingen VP — elkostnad bara för cirkulationspump"
            else:
                cop_info = "COP = 1.0 (ren eluppvärmning)"
            st.caption(cop_info)

        # Detailed settings in expander
        with st.expander("Detaljerade VP-inställningar", expanded=False):
            col_h1, col_h2, col_h3 = st.columns(3)
            with col_h1:
                h_loss = st.number_input("Värmeförlust (kW/°C)", value=h_loss_default,
                                          min_value=0.01, max_value=1.5, step=0.001, format="%.3f",
                                          help=f"Uppskattat {h_loss_default:.3f} kW/°C från energiklass + yta. "
                                               f"Kalibreras automatiskt om du har förbrukningsdata.")
                hp_max = st.number_input("VP max värmeeffekt (kW)", value=6.0, min_value=1.0, step=0.5,
                                          help="Termisk effekt från värmepumpen. Typiskt 4-8 kW för villa.")
            with col_h2:
                elpatron_kw = st.number_input("Elpatron (kW)", value=3.0, min_value=0.0, step=0.5,
                                               help="Tillsatsvärme vid extremkyla. 0 om ingen.")
                dhw_kwh = st.number_input("Varmvatten (kWh el/dag)", value=6.0, min_value=0.0, step=1.0,
                                           help="Elförbrukning för varmvatten via värmepumpen. ~5-8 kWh/dag för familj.")
            with col_h3:
                non_heat_base = st.number_input("Bas utan värme/EV (kW)", value=0.68, min_value=0.0,
                                                 step=0.01, format="%.2f",
                                                 help="Grundlast exkl. uppvärmning, EV och pool. "
                                                      "Belysning, kyl/frys, ventilation, etc. Typiskt 0.4-1.0 kW.")

        st.caption(f"Uppskattat: energiklass {energy_class.split()[0]}, {house_area} m², "
                   f"h_loss = {h_loss:.3f} kW/°C | "
                   f"Väderdata: {len(temps_data)} dagar ({min(temps_data.keys())} — {max(temps_data.keys())})")

        # Adjust COP model for heating type
        if heating_type == "Luftvärmepump":
            cop_base, cop_slope = 2.8, 0.08  # worse at cold temps
        elif heating_type == "Fjärrvärme":
            cop_base, cop_slope = 99.0, 0.0  # essentially free heating (no compressor)
        elif heating_type == "Direktel (element)":
            cop_base, cop_slope = 1.0, 0.0
        else:
            cop_base, cop_slope = 3.4, 0.056  # ground source default

        heating_config = HeatingConfig(
            h_loss=h_loss, hp_max_heat_kw=hp_max,
            elpatron_kw=elpatron_kw, dhw_kwh_per_day=dhw_kwh,
            cop_base=cop_base, cop_slope=cop_slope,
        )

        # Auto-calibrate if consumption data is available
        if "seasonal_profile" in st.session_state:
            seasonal = st.session_state["seasonal_profile"]
            consumption_daily = []
            for month, hourly in seasonal.items():
                days_in_month = [31,28,31,30,31,30,31,31,30,31,30,31][month-1]
                daily_kwh = sum(hourly.values())
                for d in range(1, days_in_month+1):
                    date_str = f"2024-{month:02d}-{d:02d}"
                    consumption_daily.append({"date": date_str, "consumption_kwh": daily_kwh})
            fitted = fit_heating_model(consumption_daily, temps_data, heating_config)
            if abs(fitted.h_loss - h_loss) > 0.005:
                st.success(f"Modellen kalibrerad mot din förbrukningsdata: "
                           f"**h_loss = {fitted.h_loss:.3f} kW/°C** "
                           f"(energiklass-uppskattning var {h_loss:.3f})")
                heating_config = fitted

        # Build daily_load_override: house load per hour per date
        daily_load_override = {}
        for date_str, hourly_temps in temps_data.items():
            t_by_hour = {h: t for h, t in hourly_temps}
            profile = {}
            for h in range(24):
                t = t_by_hour.get(h)
                if t is None:
                    available = sorted(t_by_hour.keys())
                    nearest = min(available, key=lambda k: abs(k - h))
                    t = t_by_hour[nearest]
                heat_kw = heating_electricity_kw(t, heating_config)
                dhw_kw = heating_config.dhw_kwh_per_day / 24
                profile[h] = non_heat_base + heat_kw + dhw_kw
            daily_load_override[date_str] = profile

        # Show summary
        import statistics
        winter_days = {d: sum(p.values()) for d, p in daily_load_override.items()
                       if int(d.split("-")[1]) in (1, 2, 12)}
        summer_days = {d: sum(p.values()) for d, p in daily_load_override.items()
                       if int(d.split("-")[1]) in (6, 7, 8)}
        if winter_days and summer_days:
            annual_house = sum(sum(p.values()) for p in daily_load_override.values()) / (len(daily_load_override) / 365.25)
            st.info(f"Husförbrukning (exkl. EV/pool): "
                    f"~{annual_house:,.0f} kWh/år | "
                    f"vinter ~{statistics.mean(winter_days.values()):.0f} kWh/dag, "
                    f"sommar ~{statistics.mean(summer_days.values()):.0f} kWh/dag")
    else:
        st.warning(f"Ingen väderdata från {station_name}. Klicka 'KÖR SIMULERING' för att hämta automatiskt, "
                   f"eller kör: `python -c \"from weather import fetch_station_data; fetch_station_data('{station_id}')\"`")
        use_heating_model = False

# ================================================================
# STEP 3: INVESTMENT — Battery price table + costs
# ================================================================
st.header("3. Investering")

# Battery price table
st.subheader("Batteripriser")
st.caption("Redigera tabellen nedan — lägg till/ta bort rader, ändra priser. "
           "NKON ESS Pro (LiFePO4) som standard.")

EUR_SEK = st.number_input("EUR/SEK växelkurs", value=11.5, min_value=5.0, max_value=20.0, step=0.1,
                           key="eur_sek_rate")

default_batteries = pd.DataFrame([
    {"Namn": "5 kWh",      "Kapacitet_kWh": 5.12,  "Max_kW": 3.8,  "Pris_SEK": round(600 * EUR_SEK)},
    {"Namn": "10 kWh",     "Kapacitet_kWh": 10.24, "Max_kW": 7.5,  "Pris_SEK": round(1177 * EUR_SEK)},
    {"Namn": "16 kWh",     "Kapacitet_kWh": 16.10, "Max_kW": 11.0, "Pris_SEK": round(1512 * EUR_SEK)},
    {"Namn": "32 kWh",     "Kapacitet_kWh": 32.15, "Max_kW": 15.0, "Pris_SEK": round(2857 * EUR_SEK)},
    {"Namn": "32+16 kWh",  "Kapacitet_kWh": 48.25, "Max_kW": 15.0, "Pris_SEK": round((2857+1512) * EUR_SEK)},
    {"Namn": "2x32 kWh",   "Kapacitet_kWh": 64.30, "Max_kW": 15.0, "Pris_SEK": round(2857 * 2 * EUR_SEK)},
])

battery_table = st.data_editor(
    default_batteries,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Namn": st.column_config.TextColumn("Namn"),
        "Kapacitet_kWh": st.column_config.NumberColumn("Kapacitet (kWh)", min_value=0.1, format="%.2f"),
        "Max_kW": st.column_config.NumberColumn("Max effekt (kW)", min_value=0.1, format="%.1f"),
        "Pris_SEK": st.column_config.NumberColumn("Pris (SEK)", min_value=0, format="%d"),
    },
    key="battery_table",
)

# Show kr/kWh for each row
if len(battery_table) > 0:
    battery_table["kr_per_kWh"] = (battery_table["Pris_SEK"] / battery_table["Kapacitet_kWh"]).round(0)
    st.caption("Pris per kWh: " + " | ".join(
        f"{r['Namn']}: {r['kr_per_kWh']:.0f} kr/kWh" for _, r in battery_table.iterrows()
        if r["Kapacitet_kWh"] > 0))

# Other costs
col_i1, col_i2, col_i3 = st.columns(3)
with col_i1:
    bat_install = st.number_input("Installation batteri (SEK)", value=10000, min_value=0, step=1000,
                                   help="Samma kostnad oavsett batteristorlek")
with col_i2:
    if use_solar:
        sol_price = st.number_input("Solceller material (SEK)", value=48000, min_value=0, step=5000,
                                    help="Paneler (~28,000 för 35st à 800kr) + inverter (~12,000) + montage/kabel (~8,000). Sätt 0 om redan installerat.")
        sol_install = st.number_input("Sol-installation arbete (SEK)", value=0, min_value=0, step=5000,
                                      help="0 om du installerar själv")
    else:
        sol_price = 0
        sol_install = 0
with col_i3:
    finance = st.radio("Finansiering", ["Eget kapital", "Bolån", "Annat lån"])
    if finance == "Bolån":
        loan_rate = st.number_input("Bolåneränta (%)", value=3.0, min_value=0.0, max_value=10.0, step=0.25)
        loan_years = st.number_input("Löptid (år)", value=50, min_value=1, max_value=100, step=5)
        st.caption("Investeringen läggs på bolånet")
    elif finance == "Annat lån":
        loan_rate = st.number_input("Ränta (%)", value=5.0, min_value=0.0, step=0.5)
        loan_years = st.number_input("Lånetid (år)", value=10, min_value=1, step=1)
        st.caption("Lånekostnaden visas i kassaflödesdiagrammet")
    else:
        loan_rate = 0
        loan_years = 0

sol_invest_total = sol_price + sol_install

# ================================================================
# STEP 4: SIMULATE ALL SIZES — find optimal battery
# ================================================================
st.divider()
st.header("4. Resultat")
st.caption("Tryck på knappen nedan för att simulera alla batteristorlekar. "
           "Simuleringen testar alla tariffer och väljer den bästa för varje storlek.")

def _estimate_effekt_savings(result, eff_tariff, cfg, num_days):
    """Estimate annual savings from peak demand reduction with effekttariff.

    Compares peak demand WITH battery (discharge reduces grid draw)
    vs WITHOUT battery (raw household load).
    """
    from collections import defaultdict

    monthly_slots = defaultdict(list)
    for s in result.slots:
        ym = s.date[:7]
        monthly_slots[ym].append(s)

    total_saving = 0
    for ym, slots in monthly_slots.items():
        daily_peaks_with = defaultdict(float)
        daily_peaks_without = defaultdict(float)

        for s in slots:
            h = int(s.hour.split(":")[0])
            month = int(s.date.split("-")[1])
            date_str = s.date

            load_kw = cfg.total_load_kw(h, month, date_str)

            without_kw = load_kw
            factor = eff_tariff.kw_factor(date_str, s.hour)
            if eff_tariff.is_peak_hour(date_str, s.hour):
                weighted_without = without_kw * factor
                if weighted_without > daily_peaks_without[date_str]:
                    daily_peaks_without[date_str] = weighted_without

            if s.action == "discharge":
                with_kw = max(0, load_kw - s.power_kw)
            elif s.action in ("charge", "solar_charge"):
                with_kw = load_kw + (s.power_kw if s.action == "charge" else 0)
            else:
                with_kw = load_kw
            if s.solar_kw > 0:
                with_kw = max(0, with_kw - s.solar_kw)

            if eff_tariff.is_peak_hour(date_str, s.hour):
                weighted_with = with_kw * factor
                if weighted_with > daily_peaks_with[date_str]:
                    daily_peaks_with[date_str] = weighted_with

        n = eff_tariff.top_n_peaks
        peaks_without = sorted(daily_peaks_without.values(), reverse=True)[:n]
        peaks_with = sorted(daily_peaks_with.values(), reverse=True)[:n]

        avg_without = sum(peaks_without) / len(peaks_without) if peaks_without else 0
        avg_with = sum(peaks_with) / len(peaks_with) if peaks_with else 0

        saving = (avg_without - avg_with) * eff_tariff.effekt_rate
        total_saving += max(0, saving)

    years = num_days / 365.25
    return total_saving / years if years > 0 else 0


if st.button("KÖR SIMULERING", type="primary", use_container_width=True):
    # Clear old results
    for key in ["all_results", "solar_cfg", "price_rows", "shared_config"]:
        st.session_state.pop(key, None)

    # Validate battery table
    valid_rows = battery_table.dropna(subset=["Kapacitet_kWh", "Max_kW", "Pris_SEK"])
    valid_rows = valid_rows[valid_rows["Kapacitet_kWh"] > 0]
    if len(valid_rows) == 0:
        st.error("Ange minst ett batteri i pristabellen.")
        st.stop()

    if solar_config:
        solar_config.purchase_price = sol_price
        solar_config.installation_cost = sol_install

    # Build tariffs from grid operator
    all_tariffs = create_tariffs_for_operator(grid_operator, fuse_amps, energy_tax)
    # Override rates if user changed them in expander
    for t in all_tariffs:
        if isinstance(t, Tidstariff):
            t.peak = peak_rate
            t.offpeak = offpeak_rate
        elif isinstance(t, FastTariff):
            t.flat_rate = flat_rate
        elif isinstance(t, EffektTariff) and has_effekt:
            t.effekt_rate = effekt_rate
            t.energy_rate = effekt_energy
            t.top_n_peaks = effekt_top_n
    # If operator has no tariffs defined, fall back to Vattenfall defaults
    if not all_tariffs:
        all_tariffs = [
            Tidstariff(peak=peak_rate, offpeak=offpeak_rate, energy_tax=energy_tax, fuse_amps=fuse_amps),
            FastTariff(flat_rate=flat_rate, energy_tax=energy_tax, fuse_amps=fuse_amps),
        ]

    price_rows = df_prices.to_dict("records")

    # Simulate ALL battery sizes
    all_results = []
    with st.spinner(f"Simulerar {len(valid_rows)} batteristorlekar × {len(all_tariffs)} tariffer..."):
        for _, row in valid_rows.iterrows():
            label = row["Namn"]
            cap = row["Kapacitet_kWh"]
            max_kw = row["Max_kW"]
            bat_cost = row["Pris_SEK"]

            cfg = BatteryConfig(
                capacity_kwh=cap, max_charge_kw=max_kw, max_discharge_kw=max_kw,
                efficiency=efficiency, fuse_amps=fuse_amps, phases=phases,
                base_load_kw=base_load,
                # Scheduled loads: always pass with daily_load_override (house-only, needs EV on top)
                # Skip when hourly/seasonal profile is loaded (those already include EV pattern)
                scheduled_loads=scheduled_loads if (daily_load_override or not (hourly_load_profile or seasonal_load_profile)) else [],
                hourly_load_profile=hourly_load_profile if not (seasonal_load_profile or daily_load_override) else None,
                seasonal_load_profile=seasonal_load_profile if not daily_load_override else None,
                daily_load_override=daily_load_override,
                flexible_loads=flexible_loads,
                purchase_price=bat_cost, installation_cost=bat_install,
                cycle_life=cycle_life, calendar_life_years=15,
                export_price_factor=export_factor, export_fee_ore=export_fee,
            )

            # Simulate all tariffs, pick best
            best_profit = -999999
            result = None
            tariff = None
            best_tariff = ""
            num_days = 0
            effekt_saving_yr = 0

            for t in all_tariffs:
                r = simulate(price_rows, cfg, tariff=t, solar=solar_config)
                d = len(set(s.date for s in r.slots))
                if d == 0:
                    continue
                p = r.net_profit_sek / d * 365.25

                # For effekttariff: estimate demand charge savings from battery
                eff_save = 0
                if isinstance(t, EffektTariff):
                    eff_save = _estimate_effekt_savings(r, t, cfg, d)
                    p += eff_save

                if p > best_profit:
                    best_profit = p
                    result = r
                    tariff = t
                    best_tariff = t.name
                    num_days = d
                    effekt_saving_yr = eff_save

            if result is None:
                continue

            arb_yr = result.net_profit_sek / num_days * 365.25 + effekt_saving_yr if num_days > 0 else 0

            # Solar self-consumption benefit
            solar_self_yr = 0
            if solar_config and num_days > 0:
                yrs = num_days / 365.25
                slots_per_day = len(result.slots) / num_days
                sh = 24 / slots_per_day
                total_prod = sum(s.solar_kw for s in result.slots) * sh
                self_consumed = max(0, total_prod - result.total_solar_charge_kwh
                                    - result.total_flex_consumed_kwh - result.total_grid_export_kwh)
                avg_ore = sum(s.total_cost_ore for s in result.slots) / len(result.slots)
                solar_self_yr = (self_consumed * avg_ore / 100) / yrs

            total_benefit_yr = arb_yr + (solar_self_yr if sol_invest_total > 0 else 0)
            invest = bat_cost + bat_install
            total_invest = invest + sol_invest_total
            cycles_yr = result.num_cycles / (num_days / 365.25) if num_days > 0 else 0
            lifetime = min(cycle_life / cycles_yr if cycles_yr > 0 else 15, 15)
            payback = total_invest / total_benefit_yr if total_benefit_yr > 0 else 999
            profit_life = total_benefit_yr * lifetime - total_invest

            all_results.append({
                "label": label, "capacity": cap, "max_kw": max_kw,
                "bat_cost": bat_cost, "invest": invest, "total_invest": total_invest,
                "arb_yr": arb_yr, "solar_self_yr": solar_self_yr,
                "total_benefit_yr": total_benefit_yr,
                "payback": payback, "profit_life": profit_life,
                "cycles_yr": cycles_yr, "lifetime": lifetime,
                "best_tariff": best_tariff,
                "result": result, "config": cfg, "tariff": tariff,
                "num_days": num_days,
            })

    st.session_state["all_results"] = all_results
    st.session_state["solar_cfg"] = solar_config
    st.session_state["price_rows"] = price_rows
    # Store a reference config for volatility section
    st.session_state["shared_config"] = all_results[0]["config"] if all_results else None

# ================================================================
# RESULTS — show comparison and recommendation
# ================================================================
if "all_results" in st.session_state:
    all_results = st.session_state["all_results"]
    solar_cfg = st.session_state.get("solar_cfg")
    price_rows = st.session_state.get("price_rows", [])

    if not all_results:
        st.warning("Inga resultat att visa.")
        st.stop()

    # === RECOMMENDATION ===
    best_idx = max(range(len(all_results)), key=lambda i: all_results[i]["profit_life"])
    best = all_results[best_idx]

    st.success(
        f"**Rekommendation: {best['label']}** — "
        f"lägre elkostnad {best['total_benefit_yr']:,.0f} kr/år ({best['total_benefit_yr']/12:,.0f} kr/mån), "
        f"investering {best['total_invest']:,.0f} kr, "
        f"återbetald på {best['payback']:.1f} år, "
        f"netto {best['profit_life']:,.0f} kr under {best['lifetime']:.0f} år"
    )

    # Tariff recommendation (from best size)
    st.info(f"Bästa tariff: **{best['best_tariff']}**")

    # === PDF REPORT ===
    # Calculate financing for report
    _report_loan_cost = 0
    _report_net = best["total_benefit_yr"] / 12
    if loan_rate > 0 and loan_years > 0:
        _mr = loan_rate / 100 / 12
        _np = loan_years * 12
        _report_loan_cost = best["total_invest"] * _mr / (1 - (1 + _mr) ** -_np) if _mr > 0 else best["total_invest"] / _np
        _report_net = best["total_benefit_yr"] / 12 - _report_loan_cost

    # Gather scenario data if available (computed below, but we can peek at price_rows)
    _normal_yrs = []
    _high_yrs = []
    _normal_save = 0
    _high_save = 0

    try:
        _pdf_address = selected_city if 'selected_city' in dir() else ""
    except Exception:
        _pdf_address = ""
    try:
        _pdf_weather = station_name if 'station_name' in dir() and temps_data else ""
    except Exception:
        _pdf_weather = ""

    try:
        pdf_bytes = generate_report(
        address=_pdf_address,
        grid_operator=grid_operator,
        fuse_amps=fuse_amps,
        solar_kwp=solar_kwp if use_solar else 0,
        battery_label=best["label"],
        battery_capacity=best["capacity"],
        battery_price=best["bat_cost"],
        installation_cost=bat_install,
        solar_price=sol_price if use_solar else 0,
        solar_install=sol_install if use_solar else 0,
        total_investment=best["total_invest"],
        savings_per_year=best["total_benefit_yr"],
        savings_per_month=best["total_benefit_yr"] / 12,
        payback_years=best["payback"],
        lifetime_years=best["lifetime"],
        lifetime_profit=best["profit_life"],
        cycles_per_year=best["cycles_yr"],
        best_tariff=best["best_tariff"],
        loan_rate=loan_rate,
        loan_years=loan_years,
        monthly_loan_cost=_report_loan_cost,
        monthly_net=_report_net,
        price_data_range=f"{df_prices['date'].min()} — {df_prices['date'].max()}" if df_prices is not None else "",
        price_data_days=df_prices["date"].nunique() if df_prices is not None else 0,
        weather_station=_pdf_weather,
        all_results=[{"label": r["label"], "total_benefit_yr": r["total_benefit_yr"],
                       "total_invest": r["total_invest"], "payback": r["payback"],
                       "profit_life": r["profit_life"]} for r in all_results],
    )
        st.download_button(
            "Ladda ner PDF-rapport (bankunderlag)",
            data=bytes(pdf_bytes),
            file_name=f"energikalkyl_{date.today().isoformat()}.pdf",
            mime="application/pdf",
        )
    except Exception as e:
        st.warning(f"Kunde inte generera PDF: {e}")

    # === SCENARIO SPLIT: Normal years vs High-price period ===
    # Split simulation results by year to show realistic range
    def _yearly_profit(result, year_prefix):
        """Compute annualized profit from slots matching a year prefix."""
        slots = [s for s in result.slots if s.date.startswith(year_prefix)]
        if not slots:
            return None
        days = len(set(s.date for s in slots))
        if days < 30:
            return None
        profit = sum(s.saving_sek - s.cost_sek + s.export_revenue_sek for s in slots)
        return profit / days * 365.25

    # Detect which years have enough data
    all_dates = set()
    for r in all_results:
        all_dates.update(s.date for s in r["result"].slots)
    year_counts = {}
    for d in all_dates:
        y = d[:4]
        year_counts[y] = year_counts.get(y, 0) + 1
    full_years = sorted(y for y, c in year_counts.items() if c >= 300)
    partial_years = sorted(y for y, c in year_counts.items() if 30 <= c < 300)

    # Compute per-year profits for the recommended battery
    if len(full_years) >= 1 or len(partial_years) >= 1:
        scenario_data = []
        for r in all_results:
            row = {"label": r["label"]}
            for y in full_years + partial_years:
                yp = _yearly_profit(r["result"], y)
                if yp is not None:
                    row[y] = yp
            row["all"] = r["total_benefit_yr"]
            scenario_data.append(row)

        # Identify "normal" and "high" scenarios
        avg_prices = {}
        for y in full_years + partial_years:
            yr_prices = [float(p["ore_per_kwh"]) for p in price_rows if p["date"].startswith(y)]
            if yr_prices:
                avg_prices[y] = sum(yr_prices) / len(yr_prices)

        normal_years = [y for y in full_years if avg_prices.get(y, 0) < 70]
        high_years = [y for y in full_years + partial_years if avg_prices.get(y, 0) >= 70]

        if normal_years or high_years:
            st.subheader("Scenariojämförelse")
            st.caption("Samma simulering — uppdelad per år. Elpriser varierar kraftigt mellan år.")

            # Build comparison table
            comp_rows = []
            for sd in scenario_data:
                comp = {"Batteri": sd["label"]}
                if normal_years:
                    vals = [sd[y] for y in normal_years if y in sd]
                    if vals:
                        avg_normal = sum(vals) / len(vals)
                        comp[f"Normal ({', '.join(normal_years)})"] = f"{avg_normal:,.0f} kr/år"
                        comp["Normal kr/mån"] = f"{avg_normal/12:,.0f}"
                if high_years:
                    vals = [sd[y] for y in high_years if y in sd]
                    if vals:
                        avg_high = sum(vals) / len(vals)
                        comp[f"Höga priser ({', '.join(high_years)})"] = f"{avg_high:,.0f} kr/år"
                        comp["Höga kr/mån"] = f"{avg_high/12:,.0f}"
                comp["Snitt alla år"] = f"{sd['all']:,.0f} kr/år"
                comp_rows.append(comp)

            st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)

            # Chart: grouped bars per battery, one bar per year
            fig_scen = go.Figure()
            colors_yr = {"2023": "#95a5a6", "2024": "#3498db", "2025": "#2ecc71", "2026": "#e74c3c"}
            for y in full_years + partial_years:
                vals = [sd.get(y) for sd in scenario_data]
                fig_scen.add_trace(go.Bar(
                    x=[sd["label"] for sd in scenario_data],
                    y=[v if v is not None else 0 for v in vals],
                    name=f"{y}" + (" (del)" if y in partial_years else ""),
                    marker_color=colors_yr.get(y, "#9b59b6"),
                    hovertemplate="%{x}<br>" + y + ": %{y:,.0f} kr/år<extra></extra>",
                ))
            fig_scen.update_layout(
                barmode="group", yaxis_title="Lägre elkostnad (kr/år)", height=400,
                margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02),
            )
            st.plotly_chart(fig_scen, use_container_width=True)

            if normal_years and high_years:
                # Show range for recommended battery
                best_sd = next(sd for sd in scenario_data if sd["label"] == best["label"])
                normal_vals = [best_sd[y] for y in normal_years if y in best_sd]
                high_vals = [best_sd[y] for y in high_years if y in best_sd]
                avg_n = sum(normal_vals) / len(normal_vals) if normal_vals else 0
                avg_h = sum(high_vals) / len(high_vals) if high_vals else 0
                st.info(
                    f"**{best['label']}**: Vid normala priser ({', '.join(normal_years)}) "
                    f"sparar du **{avg_n:,.0f} kr/år** ({avg_n/12:,.0f} kr/mån). "
                    f"Vid höga priser ({', '.join(high_years)}) "
                    f"sparar du **{avg_h:,.0f} kr/år** ({avg_h/12:,.0f} kr/mån)."
                )

    # === COMPARISON CHART: yearly savings (all data average) ===
    st.subheader("Jämförelse alla batteristorlekar")
    labels = [r["label"] for r in all_results]

    fig_comp = go.Figure()
    fig_comp.add_trace(go.Bar(
        x=labels, y=[r["total_benefit_yr"] for r in all_results],
        name="Lägre elkostnad (kr/år, snitt alla år)", marker_color="#2ecc71",
        hovertemplate="%{x}<br><b>%{y:,.0f} kr/år</b><extra></extra>",
    ))
    fig_comp.update_layout(yaxis_title="SEK per år", height=350,
                            margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig_comp, use_container_width=True)

    # === COMPARISON TABLE ===
    st.dataframe(pd.DataFrame([{
        "Batteri": r["label"],
        "Lägre elkostnad/år": f"{r['total_benefit_yr']:,.0f} kr",
        "Lägre elkostnad/mån": f"{r['total_benefit_yr']/12:,.0f} kr",
        "Batteripris": f"{r['bat_cost']:,.0f} kr",
        "Total investering": f"{r['total_invest']:,.0f} kr",
        "Payback": f"{r['payback']:.1f} år",
        "Netto under livslängd": f"{r['profit_life']:,.0f} kr",
        "Tariff": r["best_tariff"],
    } for r in all_results]), use_container_width=True, hide_index=True)

    # === LIFETIME PROFIT CHART ===
    fig_life = go.Figure()
    fig_life.add_trace(go.Bar(
        x=labels, y=[r["profit_life"] for r in all_results],
        name="Total vinst under livslängd",
        marker_color=["#2ecc71" if r["profit_life"] > 0 else "#e74c3c" for r in all_results],
        hovertemplate="%{x}<br><b>%{y:,.0f} kr</b> total vinst<extra></extra>",
    ))
    fig_life.add_trace(go.Scatter(
        x=labels, y=[-r["total_invest"] for r in all_results],
        mode="markers", name="Investering (negativt)",
        marker=dict(size=12, color="#e74c3c", symbol="diamond"),
        hovertemplate="%{x}<br>Investering: %{y:,.0f} kr<extra></extra>",
    ))
    fig_life.update_layout(yaxis_title="SEK", height=350,
                           margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig_life, use_container_width=True)

    # === MARGINAL VALUE ===
    if len(all_results) > 1:
        st.subheader("Vad ger varje uppgradering?")
        st.caption("Extra nytta per år om du väljer nästa storlek")

        marginal_data = []
        for i in range(1, len(all_results)):
            prev, curr = all_results[i-1], all_results[i]
            extra_cost = curr["bat_cost"] - prev["bat_cost"]
            extra_arb = curr["total_benefit_yr"] - prev["total_benefit_yr"]
            marginal_payback = extra_cost / extra_arb if extra_arb > 0 else 999
            marginal_data.append({
                "step": f"{prev['label']} → {curr['label']}",
                "extra_cost": extra_cost, "extra_arb": extra_arb,
                "payback": marginal_payback,
            })

        fig_marginal = go.Figure()
        fig_marginal.add_trace(go.Bar(
            x=[m["step"] for m in marginal_data],
            y=[m["extra_arb"] for m in marginal_data],
            marker_color=["#2ecc71" if m["extra_arb"] > 0 else "#e74c3c" for m in marginal_data],
            hovertemplate="%{x}<br>+%{y:,.0f} kr/år<extra></extra>",
        ))
        fig_marginal.update_layout(yaxis_title="Extra SEK/år", height=300,
                                    margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_marginal, use_container_width=True)

        st.dataframe(pd.DataFrame([{
            "Uppgradering": m["step"],
            "Extra kostnad": f"{m['extra_cost']:,.0f} kr",
            "Extra nytta/år": f"{m['extra_arb']:,.0f} kr",
            "Marginal payback": f"{m['payback']:.1f} år",
            "Värt det?": "Ja" if m["payback"] < 8 else ("Tveksamt" if m["payback"] < 15 else "Nej"),
        } for m in marginal_data]), use_container_width=True, hide_index=True)

    # === FINANCING PERSPECTIVE ===
    st.divider()
    st.subheader("Finansiering — netto per månad")

    if finance in ("Bolån", "Annat lån") and loan_rate > 0 and loan_years > 0:
        loan_label = "Bolån" if finance == "Bolån" else "Lån"
        st.caption(f"Investeringen finansieras via {loan_label.lower()} ({loan_rate}%, {loan_years} år). "
                   f"Besparing minus lånekostnad = pengar kvar i fickan varje månad.")

        m_rate = loan_rate / 100 / 12
        n_payments = loan_years * 12
        fin_data = []
        for r in all_results:
            total = r["total_invest"]
            if m_rate > 0:
                m_cost = total * m_rate / (1 - (1 + m_rate) ** -n_payments)
            else:
                m_cost = total / n_payments
            m_saving = r["total_benefit_yr"] / 12
            net = m_saving - m_cost
            fin_data.append({"label": r["label"], "total": total,
                             "monthly_cost": m_cost, "monthly_saving": m_saving, "net": net})

        # Chart
        fig_fin = go.Figure()
        fig_fin.add_trace(go.Bar(
            x=[d["label"] for d in fin_data],
            y=[d["monthly_saving"] for d in fin_data],
            name="Lägre elkostnad", marker_color="#2ecc71",
            hovertemplate="%{x}<br>Besparing: %{y:,.0f} kr/mån<extra></extra>",
        ))
        fig_fin.add_trace(go.Bar(
            x=[d["label"] for d in fin_data],
            y=[-d["monthly_cost"] for d in fin_data],
            name=f"{loan_label}kostnad", marker_color="#e74c3c",
            hovertemplate="%{x}<br>" + loan_label + ": %{y:,.0f} kr/mån<extra></extra>",
        ))
        fig_fin.add_trace(go.Scatter(
            x=[d["label"] for d in fin_data],
            y=[d["net"] for d in fin_data],
            mode="markers+text", name="Netto",
            marker=dict(size=14, color="#3498db", symbol="diamond"),
            text=[f"+{d['net']:,.0f}" if d["net"] >= 0 else f"{d['net']:,.0f}" for d in fin_data],
            textposition="top center",
            hovertemplate="%{x}<br><b>Netto: %{y:,.0f} kr/mån</b><extra></extra>",
        ))
        fig_fin.update_layout(barmode="relative", yaxis_title="kr/månad", height=400,
                               margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02))
        st.plotly_chart(fig_fin, use_container_width=True)

        st.dataframe(pd.DataFrame([{
            "Batteri": d["label"],
            "Total investering": f"{d['total']:,.0f} kr",
            f"{loan_label}kostnad": f"{d['monthly_cost']:,.0f} kr/mån",
            "Lägre elkostnad": f"{d['monthly_saving']:,.0f} kr/mån",
            "Netto i fickan": f"{d['net']:+,.0f} kr/mån",
            "Netto per år": f"{d['net']*12:+,.0f} kr/år",
        } for d in fin_data]), use_container_width=True, hide_index=True)

        best_fin = max(fin_data, key=lambda d: d["net"])
        all_positive = all(d["net"] > 0 for d in fin_data)
        if all_positive:
            st.success(f"**Alla storlekar ger positivt kassaflöde!** Bäst: **{best_fin['label']}** "
                       f"med **+{best_fin['net']:,.0f} kr/mån** netto.")
        elif best_fin["net"] > 0:
            st.info(f"**{best_fin['label']}** ger bäst kassaflöde: **+{best_fin['net']:,.0f} kr/mån** netto.")
        else:
            st.warning("Ingen storlek ger positivt kassaflöde med dessa lånvillkor.")
    else:
        # Eget kapital — show simple cashflow over time for recommended battery
        st.caption("Kontant betalning — ackumulerat kassaflöde per batteristorlek")

        fig_cf = go.Figure()
        colors = ["#3498db", "#2ecc71", "#e74c3c", "#9b59b6", "#f39c12", "#1abc9c"]
        for i, r in enumerate(all_results):
            years = list(range(0, 16))
            cf = [-r["total_invest"]]
            for y in range(1, 16):
                cf.append(cf[-1] + r["total_benefit_yr"])
            fig_cf.add_trace(go.Scatter(
                x=years, y=cf, mode="lines+markers", name=r["label"],
                line=dict(width=2, color=colors[i % len(colors)]),
                hovertemplate=f"{r['label']}<br>År %{{x}}: %{{y:,.0f}} kr<extra></extra>",
            ))
        fig_cf.add_hline(y=0, line_color="gray", line_width=1)
        fig_cf.update_layout(xaxis_title="År", yaxis_title="Ackumulerat (SEK)", height=400,
                              margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02))
        st.plotly_chart(fig_cf, use_container_width=True)

    # ================================================================
    # FUSE SIZE COMPARISON
    # ================================================================
    op_fees = get_operator_fuse_fees(grid_operator)
    available_fuses = sorted(op_fees.keys())
    current_fuse_idx = available_fuses.index(fuse_amps) if fuse_amps in available_fuses else 0
    # Only show if there are fuses to compare above current
    larger_fuses = [f for f in available_fuses if f > fuse_amps]
    if larger_fuses and best:
        st.divider()
        st.subheader("Lönar sig en större säkring?")
        current_fee_yr = op_fees.get(fuse_amps, 0)
        st.caption(f"Större säkring ger mer laddkapacitet för batteriet. "
                   f"Din nuvarande: {fuse_amps:.0f}A ({current_fee_yr:,.0f} kr/år). "
                   f"Simuleringen körs för rekommenderat batteri ({best['label']}).")

        # Re-simulate best battery at different fuse sizes
        fuse_comparison = []
        best_cfg_base = best["config"]
        best_tariff_obj = best["tariff"]

        # Current fuse result (already computed)
        fuse_comparison.append({
            "fuse": fuse_amps,
            "fee_yr": current_fee_yr,
            "benefit_yr": best["total_benefit_yr"],
            "net_yr": best["total_benefit_yr"],
            "current": True,
        })

        fuses_to_test = [f for f in available_fuses if f > fuse_amps][:3]  # max 3 upgrades
        if fuses_to_test:
            with st.spinner("Jämför säkringsstorlekar..."):
                for f in fuses_to_test:
                    fuse_cfg = BatteryConfig(
                        capacity_kwh=best_cfg_base.capacity_kwh,
                        max_charge_kw=best_cfg_base.max_charge_kw,
                        max_discharge_kw=best_cfg_base.max_discharge_kw,
                        efficiency=best_cfg_base.efficiency,
                        fuse_amps=f, phases=best_cfg_base.phases,
                        base_load_kw=best_cfg_base.base_load_kw,
                        scheduled_loads=best_cfg_base.scheduled_loads,
                        hourly_load_profile=best_cfg_base.hourly_load_profile,
                        seasonal_load_profile=best_cfg_base.seasonal_load_profile,
                        daily_load_override=best_cfg_base.daily_load_override,
                        flexible_loads=best_cfg_base.flexible_loads,
                        purchase_price=best_cfg_base.purchase_price,
                        installation_cost=best_cfg_base.installation_cost,
                        cycle_life=best_cfg_base.cycle_life,
                        calendar_life_years=best_cfg_base.calendar_life_years,
                        export_price_factor=best_cfg_base.export_price_factor,
                        export_fee_ore=best_cfg_base.export_fee_ore,
                    )
                    r_fuse = simulate(price_rows, fuse_cfg, tariff=best_tariff_obj,
                                       solar=solar_cfg)
                    d_fuse = len(set(s.date for s in r_fuse.slots))
                    if d_fuse == 0:
                        continue
                    arb_fuse = r_fuse.net_profit_sek / d_fuse * 365.25
                    eff_save = 0
                    if isinstance(best_tariff_obj, EffektTariff):
                        eff_save = _estimate_effekt_savings(r_fuse, best_tariff_obj, fuse_cfg, d_fuse)
                    benefit_fuse = arb_fuse + eff_save
                    fee_yr = op_fees.get(f, 0)
                    extra_fee = fee_yr - current_fee_yr
                    net = benefit_fuse - extra_fee  # net benefit after paying extra fuse cost

                    fuse_comparison.append({
                        "fuse": f,
                        "fee_yr": fee_yr,
                        "benefit_yr": benefit_fuse,
                        "extra_fee_yr": extra_fee,
                        "extra_benefit_yr": benefit_fuse - best["total_benefit_yr"],
                        "net_yr": net,
                        "current": False,
                    })

        if len(fuse_comparison) > 1:
            # Chart
            fig_fuse = go.Figure()
            fuse_labels = [f"{fc['fuse']:.0f}A" + (" (nu)" if fc["current"] else "") for fc in fuse_comparison]
            fig_fuse.add_trace(go.Bar(
                x=fuse_labels,
                y=[fc["benefit_yr"] for fc in fuse_comparison],
                name="Lägre elkostnad (kr/år)",
                marker_color=["#2ecc71" if not fc["current"] else "#3498db" for fc in fuse_comparison],
                hovertemplate="%{x}<br>Besparing: %{y:,.0f} kr/år<extra></extra>",
            ))
            fig_fuse.add_trace(go.Bar(
                x=fuse_labels,
                y=[-fc.get("extra_fee_yr", 0) for fc in fuse_comparison],
                name="Extra abonnemangskostnad (kr/år)",
                marker_color="#e74c3c",
                hovertemplate="%{x}<br>Extra avgift: %{y:,.0f} kr/år<extra></extra>",
            ))
            fig_fuse.update_layout(barmode="relative", yaxis_title="kr/år", height=350,
                                    margin=dict(l=0, r=0, t=30, b=0),
                                    legend=dict(orientation="h", y=1.02))
            st.plotly_chart(fig_fuse, use_container_width=True)

            # Table
            st.dataframe(pd.DataFrame([{
                "Säkring": f"{fc['fuse']:.0f}A" + (" (nuvarande)" if fc["current"] else ""),
                "Abonnemang": f"{fc['fee_yr']:,.0f} kr/år",
                "Lägre elkostnad": f"{fc['benefit_yr']:,.0f} kr/år",
                "Extra abonnemang": f"{fc.get('extra_fee_yr', 0):+,.0f} kr/år" if not fc["current"] else "—",
                "Extra besparing": f"{fc.get('extra_benefit_yr', 0):+,.0f} kr/år" if not fc["current"] else "—",
                "Netto": f"{fc['net_yr']:,.0f} kr/år ({fc['net_yr']/12:,.0f} kr/mån)",
            } for fc in fuse_comparison]), use_container_width=True, hide_index=True)

            # Recommendation
            best_fuse = max(fuse_comparison, key=lambda fc: fc["net_yr"])
            if not best_fuse["current"]:
                extra = best_fuse["net_yr"] - fuse_comparison[0]["net_yr"]
                st.success(f"**Uppgradera till {best_fuse['fuse']:.0f}A** — "
                           f"ger {extra:+,.0f} kr/år netto efter abonnemangshöjning "
                           f"({best_fuse.get('extra_fee_yr', 0):+,.0f} kr/år avgift, "
                           f"{best_fuse.get('extra_benefit_yr', 0):+,.0f} kr/år extra besparing)")
            else:
                st.info(f"Nuvarande {fuse_amps:.0f}A är optimal — "
                        f"större säkring ger inte tillräckligt extra besparing.")

    # ================================================================
    # STEP 5: DEEP-DIVE — detail view for selected battery
    # ================================================================
    st.divider()
    st.header("5. Detaljvy")

    detail_labels = [r["label"] for r in all_results]
    default_idx = best_idx if best_idx < len(detail_labels) else 0
    selected_label = st.selectbox("Visa detaljer för:", detail_labels, index=default_idx)
    sel = next(r for r in all_results if r["label"] == selected_label)

    result = sel["result"]
    config = sel["config"]
    tariff = sel["tariff"]
    num_days = sel["num_days"]
    per_year = sel["total_benefit_yr"]

    col_d1, col_d2, col_d3, col_d4 = st.columns(4)
    col_d1.metric("Lägre elkostnad", f"{per_year/12:,.0f} kr/mån")
    col_d2.metric("Per år", f"{per_year:,.0f} kr/år")
    col_d3.metric("Payback", f"{sel['payback']:.1f} år")
    col_d4.metric("Cykler/år", f"{sel['cycles_yr']:.0f}")

    with st.expander("Detaljer"):
        st.text(f"Batteri:                 {sel['label']} ({sel['capacity']:.1f} kWh)")
        st.text(f"Batteripris:             {sel['bat_cost']:>10,.0f} kr")
        st.text(f"Total investering:       {sel['total_invest']:>10,.0f} kr")
        st.text(f"Lägre elkostnad:         {per_year:>10,.0f} kr/år ({per_year/12:,.0f} kr/mån)")
        if sel["arb_yr"] > 0:
            st.text(f"  varav batteri:         {sel['arb_yr']:>10,.0f} kr/år")
        if sel["solar_self_yr"] > 0:
            st.text(f"  varav sol egenanvänd:  {sel['solar_self_yr']:>10,.0f} kr/år")
        st.text(f"Återbetalningstid:       {sel['payback']:>10.1f} år")
        st.text(f"Netto under {sel['lifetime']:.0f} år:       {sel['profit_life']:>10,.0f} kr")
        st.text(f"Batterilivslängd:        {sel['lifetime']:>10.1f} år ({sel['cycles_yr']:.0f} cykler/år)")
        st.text(f"Tariff:                  {sel['best_tariff']}")

    # Monthly cashflow breakdown
    st.subheader("Typiskt år — skillnad i elkostnad per månad")

    slot_data = []
    for s in result.slots:
        slot_data.append({
            "date": s.date, "hour": s.hour, "cost_sek": s.cost_sek,
            "saving_sek": s.saving_sek, "solar_charge_kwh": s.solar_charge_kwh,
            "export_revenue_sek": s.export_revenue_sek,
            "solar_kw": s.solar_kw,
        })

    df_slots = pd.DataFrame(slot_data)

    months_sv = ["", "Jan", "Feb", "Mar", "Apr", "Maj", "Jun",
                 "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]
    df_slots["cal_month"] = pd.to_datetime(df_slots["date"]).dt.month
    years_in_data = num_days / 365.25

    monthly_detail = []
    for m_num, grp in df_slots.groupby("cal_month"):
        charge_cost = grp["cost_sek"].sum() / years_in_data
        discharge_value = grp["saving_sek"].sum() / years_in_data
        export_rev = grp["export_revenue_sek"].sum() / years_in_data
        solar_charged = grp["solar_charge_kwh"].sum() / years_in_data
        net = discharge_value - charge_cost + export_rev
        monthly_detail.append({
            "month": months_sv[m_num], "month_num": m_num,
            "charge_cost": charge_cost, "discharge_value": discharge_value,
            "export_rev": export_rev, "solar_charged": solar_charged, "net": net,
        })

    df_md = pd.DataFrame(monthly_detail).sort_values("month_num")

    # Summary: savings per month
    col_w1, col_w2 = st.columns(2)
    col_w1.metric("Lägre elkostnad", f"{per_year/12:,.0f} kr/mån",
                   delta=f"{per_year:,.0f} kr/år")
    op_fees = get_operator_fuse_fees(grid_operator)
    fuse_monthly = op_fees.get(fuse_amps, 0) / 12
    col_w2.metric("Fasta kostnader (samma med/utan)", f"{49 + fuse_monthly:,.0f} kr/mån",
                   help=f"Tibber 49 kr + {grid_operator} {fuse_monthly:,.0f} kr ({fuse_amps}A)")

    fig_stack = go.Figure()
    fig_stack.add_trace(go.Bar(
        x=df_md["month"], y=df_md["discharge_value"],
        name="Urladdat (undviken elkostnad)", marker_color="#2ecc71",
        hovertemplate="%{x}<br>%{y:,.0f} kr<extra>Batteri ersätter nätköp</extra>",
    ))
    if df_md["export_rev"].sum() > 0:
        fig_stack.add_trace(go.Bar(
            x=df_md["month"], y=df_md["export_rev"],
            name="Sålt till nät", marker_color="#3498db",
            hovertemplate="%{x}<br>%{y:,.0f} kr<extra>Överskott sålt</extra>",
        ))
    fig_stack.add_trace(go.Bar(
        x=df_md["month"], y=-df_md["charge_cost"],
        name="Laddkostnad (från nät)", marker_color="#e74c3c",
        hovertemplate="%{x}<br>%{y:,.0f} kr<extra>Kostnad att ladda</extra>",
    ))
    # Net per month as line
    fig_stack.add_trace(go.Scatter(
        x=df_md["month"], y=df_md["net"],
        mode="lines+markers", name="Netto besparing",
        line=dict(width=3, color="#2c3e50"),
        hovertemplate="%{x}<br>Netto: %{y:,.0f} kr/mån<extra></extra>",
    ))
    fig_stack.add_hline(y=sel["arb_yr"]/12, line_dash="dash", line_color="gray",
                         annotation_text=f"Snitt {sel['arb_yr']/12:,.0f} kr/mån")
    fig_stack.update_layout(barmode="relative", yaxis_title="kr/månad (typiskt år)", height=400,
                             margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig_stack, use_container_width=True)

    with st.expander("Detaljer per månad"):
        st.dataframe(pd.DataFrame([{
            "Månad": r["month"],
            "Urladdat (kr)": f"{r['discharge_value']:,.0f}",
            "Laddkostnad (kr)": f"{r['charge_cost']:,.0f}",
            "Export (kr)": f"{r['export_rev']:,.0f}",
            "Sol→batteri (kWh)": f"{r['solar_charged']:,.0f}",
            "Netto besparing (kr)": f"{r['net']:,.0f}",
        } for r in monthly_detail]), use_container_width=True, hide_index=True)

    # ================================================================
    # STEP 6: FUTURE VOLATILITY
    # ================================================================
    st.divider()
    st.header("6. Framtidsprognos")
    st.caption("Hur påverkas lönsamheten om prisvolatiliteten ökar? "
               "Mer sol/vind i elnätet → större prisskillnader → mer att tjäna.")

    target_vol = st.slider("Förväntad volatilitet om 10 år (relativt idag)", 1.0, 3.0, 1.5, 0.1, format="%.1fx")

    def scale_vol(rows, factor):
        days_map = {}
        for r in rows:
            days_map.setdefault(r["date"], []).append(r)
        out = []
        for d, drs in days_map.items():
            mean = sum(float(r["sek_per_kwh"]) for r in drs) / len(drs)
            for r in drs:
                nr = dict(r)
                nr["sek_per_kwh"] = round(max(0.001, mean + (float(r["sek_per_kwh"]) - mean) * factor), 4)
                nr["ore_per_kwh"] = round(nr["sek_per_kwh"] * 100, 2)
                out.append(nr)
        return out

    # Use top 3 sizes from user's price table for volatility scenarios
    sorted_by_cap = sorted(all_results, key=lambda r: r["capacity"])
    if len(sorted_by_cap) > 3:
        # Pick small, recommended, and largest
        vol_picks = [sorted_by_cap[0], best, sorted_by_cap[-1]]
        # Deduplicate
        seen = set()
        vol_picks = [r for r in vol_picks if r["label"] not in seen and not seen.add(r["label"])]
    else:
        vol_picks = sorted_by_cap

    bat_configs = [(r["label"], r["capacity"], r["max_kw"], round(r["bat_cost"]))
                   for r in vol_picks]
    vol_levels = [1.0, 1.2, 1.5, 2.0, 2.5]
    palette = ["#3498db", "#2ecc71", "#e74c3c", "#9b59b6", "#f39c12"]
    colors_bat = {bc[0]: palette[i % len(palette)] for i, bc in enumerate(bat_configs)}

    ref_cfg = st.session_state.get("shared_config") or all_results[0]["config"]
    ref_tariff = best["tariff"]

    with st.spinner("Beräknar scenarier..."):
        fc_data = []
        for vf in vol_levels:
            scaled = scale_vol(price_rows, vf)
            for bl, cap, chg, bp in bat_configs:
                fc_cfg = BatteryConfig(
                    capacity_kwh=cap, max_charge_kw=chg, max_discharge_kw=chg,
                    efficiency=ref_cfg.efficiency, fuse_amps=ref_cfg.fuse_amps, phases=ref_cfg.phases,
                    base_load_kw=ref_cfg.base_load_kw, scheduled_loads=ref_cfg.scheduled_loads,
                    hourly_load_profile=ref_cfg.hourly_load_profile,
                    seasonal_load_profile=ref_cfg.seasonal_load_profile,
                    daily_load_override=ref_cfg.daily_load_override,
                    flexible_loads=ref_cfg.flexible_loads,
                    export_price_factor=ref_cfg.export_price_factor, export_fee_ore=ref_cfg.export_fee_ore,
                    purchase_price=bp, installation_cost=ref_cfg.installation_cost,
                    cycle_life=ref_cfg.cycle_life, calendar_life_years=15,
                )
                r = simulate(scaled, fc_cfg, tariff=ref_tariff, solar=solar_cfg)
                d = len(set(s.date for s in r.slots))
                ay = r.net_profit_sek / d * 365.25 if d > 0 else 0
                inv = bp + ref_cfg.installation_cost
                fc_data.append({"vol": vf, "bat": bl, "arb_yr": ay, "invest": inv,
                                "payback": inv/ay if ay > 0 else 999})

    df_fc = pd.DataFrame(fc_data)

    fig_fc = go.Figure()
    for bl in [bc[0] for bc in bat_configs]:
        d = df_fc[df_fc["bat"] == bl]
        fig_fc.add_trace(go.Scatter(
            x=[f"{v:.0%}" for v in d["vol"]], y=d["arb_yr"],
            mode="lines+markers", name=bl, line=dict(width=2, color=colors_bat.get(bl)),
        ))
    fig_fc.update_layout(xaxis_title="Volatilitet", yaxis_title="Arbitrage (SEK/år)", height=350,
                          margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig_fc, use_container_width=True)

    st.subheader("15-årsprognos")
    st.caption(f"Volatiliteten ökar linjärt till {target_vol:.1f}x över 10 år, sedan konstant")

    fig_15 = go.Figure()
    for bl, cap, chg, bp in bat_configs:
        inv = bp + ref_cfg.installation_cost
        cum = [-inv]
        for yr in range(1, 16):
            vol = 1.0 + (target_vol - 1.0) * min(yr, 10) / 10
            below = [v for v in vol_levels if v <= vol]
            above = [v for v in vol_levels if v > vol]
            if below and above:
                b, a = below[-1], above[0]
                rb = df_fc[(df_fc["bat"]==bl) & (df_fc["vol"]==b)]["arb_yr"].iloc[0]
                ra = df_fc[(df_fc["bat"]==bl) & (df_fc["vol"]==a)]["arb_yr"].iloc[0]
                t = (vol - b) / (a - b)
                yr_profit = rb * (1-t) + ra * t
            elif below:
                yr_profit = df_fc[(df_fc["bat"]==bl) & (df_fc["vol"]==below[-1])]["arb_yr"].iloc[0]
            else:
                yr_profit = df_fc[(df_fc["bat"]==bl) & (df_fc["vol"]==vol_levels[0])]["arb_yr"].iloc[0]
            cum.append(cum[-1] + yr_profit)

        fig_15.add_trace(go.Scatter(x=list(range(16)), y=cum, mode="lines+markers",
                                     name=bl, line=dict(width=2, color=colors_bat.get(bl))))

    fig_15.add_hline(y=0, line_color="gray", line_width=1)
    fig_15.update_layout(xaxis_title="År", yaxis_title="Ackumulerat (SEK)", height=400,
                          margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig_15, use_container_width=True)

    summary = []
    for bl in [bc[0] for bc in bat_configs]:
        for vl in vol_levels:
            r = df_fc[(df_fc["bat"]==bl) & (df_fc["vol"]==vl)].iloc[0]
            summary.append({"Batteri": bl, "Volatilitet": f"{vl:.0%}",
                            "Vinst/år": f"{r['arb_yr']:,.0f} kr",
                            "Payback": f"{r['payback']:.1f} år"})
    st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)
