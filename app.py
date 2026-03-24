"""
Energikalkyl — El, Sol & Batteri (Web GUI)

Analysverktyg för att bedöma lönsamhet i hembatteri och solceller.
Start with:  streamlit run app.py

HOW THIS APP WORKS (for non-coders):
=====================================
The app has 6 steps that run top-to-bottom:

  1. LOAD DATA — Fetch your electricity consumption (from Tibber, E.ON, or CSV files)
     and historical spot prices. This is the raw input the simulation needs.

  2. CONFIGURE YOUR SYSTEM — Describe your house: battery settings, solar panels,
     grid operator, fuse size, heating system, EV charging, and flexible loads.
     The app auto-fills as much as possible from Tibber.

  3. INVESTMENT — Set battery prices (NKON defaults or custom SEK/kWh) and
     financing (cash, mortgage, or loan).

  4. RESULTS — The core simulation runs here. It tests EVERY battery size against
     EVERY tariff type and picks the best combination. Shows recommendation,
     yearly/monthly breakdown, cashflow charts, and financing analysis.

  5. DETAIL VIEW — Deep-dive into a specific battery: monthly cost/savings breakdown,
     solar charging, and export revenue.

  6. FUTURE SCENARIOS — "What if electricity price swings increase?" Three scenarios
     (conservative, likely, high volatility) show how the investment performs
     as the energy market evolves.

KEY CONCEPTS:
- "Arbitrage" = buy cheap electricity at night, use it during expensive peak hours
- "Effekttariff" = you pay for your highest power peak each month (kW), not just energy (kWh)
- "Flex loads" = pool pumps, hot water tanks, heat pumps that can shift to use free solar
- "Self-consumption" = using your own solar power instead of exporting it to the grid
- "Spread" = difference between cheapest and most expensive hour — this is what the battery earns

STREAMLIT BASICS (for non-coders):
- st.header() / st.subheader() / st.caption() = display text headings
- st.number_input() / st.selectbox() / st.checkbox() = user input widgets
- st.session_state = a dictionary that remembers values between page refreshes
- st.columns() = side-by-side layout
- st.expander() = collapsible section
- st.metric() = big number with optional delta (green/red arrow)
- st.plotly_chart() = interactive chart
- st.dataframe() = data table
- st.success/info/warning/error() = colored message boxes
"""

# ============================================================
# IMPORTS — load all the modules this app depends on
# ============================================================
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from elpriser import fetch_range, load_csv, ZONES, ZONE_NAMES
from batteri import BatteryConfig, LoadSchedule, FlexibleLoad, simulate
from solar import SolarConfig, estimate_yearly_production, estimate_lifetime_production, MONTHLY_KWH_PER_KWP
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
from app_state import save_state, load_state
from translations import t, set_language, get_language

st.set_page_config(page_title="Energikalkyl", page_icon="⚡", layout="wide")

# Language selector — placed before everything else so all text respects the choice.
# Stored in session_state so it survives Streamlit reruns.
_lang_options = {"Svenska": "sv", "English": "en"}
_lang_display = list(_lang_options.keys())
_saved_lang = st.session_state.get("app_language", "sv")
_lang_default = 0 if _saved_lang == "sv" else 1
_selected_lang = st.selectbox(t("language"), _lang_display, index=_lang_default,
                               key="lang_select", label_visibility="collapsed")
st.session_state["app_language"] = _lang_options[_selected_lang]
set_language(st.session_state["app_language"])

# Restore persisted state on first load.
# This means your consumption data, prices, and settings survive page refreshes.
# Data is saved as JSON files in the .app_state/ directory.
if "_state_restored" not in st.session_state:
    if load_state(st.session_state):
        st.session_state["_state_restored"] = "loaded"
    else:
        st.session_state["_state_restored"] = "empty"

st.title(t("app_title"))
st.caption(t("app_subtitle"))

# ================================================================
# STEP 1: LOAD DATA
# ================================================================
# This section fetches two types of input data:
#   LEFT COLUMN: Your electricity consumption (how much you use, hour by hour)
#     - Tibber: fetches ~30 days hourly + 3 years monthly. Also auto-fills house info.
#     - E.ON: fetches from E.ON's API (needs credentials)
#     - File upload: Vattenfall Excel or generic CSV files
#   RIGHT COLUMN: Historical spot prices (what electricity costs each hour)
#     - API: fetches from elprisetjustnu.se for your price zone
#     - CSV: upload your own price file
#
# The consumption profile tells the simulation HOW you use electricity.
# The spot prices tell it WHEN electricity is cheap vs expensive.
# Together, they determine how much a battery can save you.
# ================================================================
st.header(t("step1_header"))
st.caption(t("step1_caption"))

col_consumption, col_prices = st.columns(2)

# --- Consumption data (FIRST — Tibber auto-fills everything) ---
with col_consumption:
    st.subheader(t("consumption_header"))
    st.caption(t("consumption_best"))

    hourly_load_profile = None
    seasonal_load_profile = None

    # Tibber section — always visible
    with st.expander(t("tibber_expander"), expanded=not st.session_state.get("tibber_home")):
        st.caption(t("tibber_caption"))
        _tibber_token_input = st.text_input(t("tibber_token_label"), key="tibber_token_input",
                                             placeholder=t("tibber_token_placeholder"),
                                             help=t("tibber_token_help"))
        st.caption(t("tibber_token_security"))
        if _tibber_token_input:
            import os
            os.environ["TIBBER_TOKEN"] = _tibber_token_input
        if st.button(t("fetch_data"), type="primary"):
            with st.spinner(t("fetching_tibber")):
                try:
                    from tibber_source import (
                        fetch_consumption, consumption_to_load_profile,
                        fetch_monthly_consumption, build_seasonal_hourly_profile,
                        get_homes, fetch_production, fetch_daily_production,
                        production_to_hourly_dict, production_to_monthly_kwh,
                    )
                    # Fetch home info (address, grid company, fuse, house size, heating)
                    homes = get_homes()
                    if homes:
                        home = homes[0]
                        addr = home.get("address", {})
                        tibber_home = {
                            "address": addr.get("address1", ""),
                            "city": addr.get("city", ""),
                            "postal_code": addr.get("postalCode", ""),
                            "latitude": float(addr.get("latitude", 0) or 0),
                            "longitude": float(addr.get("longitude", 0) or 0),
                        }
                        # Extended home data
                        try:
                            from tibber_source import _get_token, _query
                            token = _get_token()
                            hq = ('{viewer{homes{'
                                  'meteringPointData{gridCompany priceAreaCode estimatedAnnualConsumption}'
                                  ' mainFuseSize size numberOfResidents primaryHeatingSource'
                                  '}}}')
                            hdata = _query(hq, token)
                            hinfo = hdata["data"]["viewer"]["homes"][0]
                            mp = hinfo.get("meteringPointData", {})
                            tibber_home["grid_company"] = mp.get("gridCompany", "")
                            tibber_home["price_area"] = mp.get("priceAreaCode", "")
                            tibber_home["annual_consumption"] = mp.get("estimatedAnnualConsumption", 0)
                            tibber_home["fuse_size"] = hinfo.get("mainFuseSize", 0)
                            tibber_home["house_size"] = hinfo.get("size", 0)
                            tibber_home["residents"] = hinfo.get("numberOfResidents", 0)
                            tibber_home["heating_source"] = hinfo.get("primaryHeatingSource", "")
                        except Exception:
                            tibber_home["grid_company"] = ""
                        st.session_state["tibber_home"] = tibber_home

                    nodes = fetch_consumption(hours=24*30)
                    profile = consumption_to_load_profile(nodes)
                    st.session_state["hourly_profile"] = profile
                    monthly = fetch_monthly_consumption(months=36)
                    if len(monthly) >= 6:
                        seasonal = build_seasonal_hourly_profile(nodes, monthly)
                        st.session_state["seasonal_profile"] = seasonal

                    # Fetch solar production data if available
                    try:
                        prod_hourly = fetch_production(hours=24*30)
                        prod_daily = fetch_daily_production(days=365*3) if prod_hourly else []
                        if prod_hourly:
                            st.session_state["tibber_solar_hourly"] = production_to_hourly_dict(prod_hourly)
                            # Use daily data for monthly averages (longer history)
                            prod_for_monthly = prod_daily if prod_daily else prod_hourly
                            st.session_state["tibber_solar_monthly"] = production_to_monthly_kwh(prod_for_monthly)
                    except Exception:
                        pass  # No solar panels on this Tibber account

                    home_info = st.session_state.get("tibber_home", {})
                    addr_str = f"{home_info.get('address', '')} {home_info.get('city', '')}".strip()
                    parts = [t("tibber_loaded")]
                    if addr_str:
                        parts.append(addr_str)
                    if home_info.get("grid_company"):
                        parts.append(f"Nät: {home_info['grid_company']}")
                    if home_info.get("fuse_size"):
                        parts.append(f"Säkring: {home_info['fuse_size']}A")
                    if home_info.get("house_size"):
                        parts.append(f"Yta: {home_info['house_size']} m²")
                    if home_info.get("heating_source"):
                        _hs_map = {"GROUND": "Bergvärme", "AIR2AIR": "Luft-luft",
                                    "AIR2WATER": "Luft-vatten", "DISTRICT": "Fjärrvärme",
                                    "ELECTRIC": "Direktel", "OTHER": "Övrigt"}
                        parts.append(_hs_map.get(home_info["heating_source"],
                                                  home_info["heating_source"]))
                    if st.session_state.get("tibber_solar_monthly"):
                        monthly_kwh = st.session_state["tibber_solar_monthly"]
                        yearly = sum(monthly_kwh.values())
                        parts.append(f"Sol: {yearly:,.0f} kWh/år")
                    st.success(" | ".join(parts))
                except Exception as e:
                    st.error(f"{t('tibber_error')}: {e}")

    # E.ON section
    with st.expander(t("eon_expander"), expanded=False):
        st.caption(t("eon_caption"))
        col_eon1, col_eon2 = st.columns(2)
        eon_install_id = col_eon1.text_input(t("installation_id"), key="eon_install",
                                              help="Ditt E.ON installations-ID (finns på fakturan)")
        eon_years = col_eon2.number_input(t("years_count"), value=3, min_value=1, max_value=5, key="eon_years")
        if st.button(t("fetch_eon"), type="primary", key="eon_fetch"):
            if not eon_install_id:
                st.error("Ange installations-ID")
            else:
                with st.spinner("Hämtar förbrukningsdata från E.ON..."):
                    try:
                        from eon_source import fetch_consumption as eon_fetch, eon_to_seasonal_profile
                        from datetime import timedelta
                        end = date.today() - timedelta(days=1)
                        start = date(end.year - eon_years, end.month, end.day)
                        eon_data = eon_fetch(eon_install_id, start, end, resolution="hour")
                        if eon_data:
                            seasonal = eon_to_seasonal_profile(eon_data)
                            st.session_state["seasonal_profile"] = seasonal
                            days = len(set(h["date"] for h in eon_data))
                            total = sum(h["kwh"] for h in eon_data)
                            st.success(f"E.ON data laddad: {len(eon_data):,} timvärden ({days} dagar), "
                                       f"{total:,.0f} kWh")
                        else:
                            st.warning("Inga data returnerades. Kontrollera installations-ID.")
                    except Exception as e:
                        st.error(f"E.ON-fel: {e}")

    # File upload section — always visible (works alongside Tibber/E.ON)
    with st.expander(t("upload_expander"), expanded=not st.session_state.get("seasonal_profile")):
        st.caption(t("upload_caption"))
        cons_files = st.file_uploader(t("consumption_data"), type=["csv", "txt", "xlsx", "xls"],
                                       accept_multiple_files=True, key="cons_upload")
        if cons_files:
            try:
                import tempfile, os
                # Clear previous data to avoid mixing old + new
                for _clear_key in ["seasonal_profile", "vattenfall_hourly", "hourly_profile"]:
                    st.session_state.pop(_clear_key, None)
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
                    from import_vattenfall import (
                        vattenfall_to_seasonal_profile, parse_vattenfall_hourly,
                        vattenfall_hourly_to_seasonal_profile,
                    )
                    # Try hourly extraction first (much better)
                    all_hourly = []
                    for f2 in cons_files:
                        if f2.name.lower().endswith((".xlsx", ".xls")):
                            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp2:
                                tmp2.write(f2.getvalue())
                                tmp2_path = tmp2.name
                            try:
                                all_hourly.extend(parse_vattenfall_hourly(tmp2_path))
                            except Exception:
                                pass
                            finally:
                                os.unlink(tmp2_path)

                    if all_hourly:
                        # Use real hourly data — best quality
                        seasonal = vattenfall_hourly_to_seasonal_profile(all_hourly)
                        st.session_state["seasonal_profile"] = seasonal
                        st.session_state["vattenfall_hourly"] = all_hourly
                        days = len(set(h["date"] for h in all_hourly))
                        total = sum(h["kwh"] for h in all_hourly)
                        avg = total / days if days > 0 else 0
                        st.success(f"Timdata laddad: **{len(all_hourly):,} timvärden** ({days} dagar) | "
                                   f"Snitt: {avg:.0f} kWh/dag | ~{avg*365:,.0f} kWh/år")
                    else:
                        # Fallback to daily totals
                        seen = set()
                        unique = sorted([r for r in all_vf if r["date"] not in seen and not seen.add(r["date"])],
                                        key=lambda x: x["date"])
                        hourly_shape = st.session_state.get("hourly_profile")
                        seasonal = vattenfall_to_seasonal_profile(unique, hourly_shape)
                        st.session_state["seasonal_profile"] = seasonal
                        total = sum(r["consumption_kwh"] for r in unique)
                        avg = total / len(unique)
                        st.success(f"Daglig data laddad: **{len(unique)} dagar** | "
                                   f"Snitt: {avg:.0f} kWh/dag | ~{avg*365:,.0f} kWh/år")
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
        _vf = st.session_state.get("vattenfall_hourly", [])
        if _vf:
            _vf_days = len(set(r["date"] for r in _vf))
            _vf_total = sum(r["kwh"] for r in _vf)
            _vf_avg = _vf_total / _vf_days if _vf_days > 0 else 0
            st.info(f"Förbrukningsdata: **{len(_vf):,} timvärden** ({_vf_days} dagar) | "
                    f"Snitt: {_vf_avg:.0f} kWh/dag | ~{_vf_avg*365:,.0f} kWh/år")
        else:
            st.info(f"Förbrukningsprofil laddad: {min(all_kw):.1f}–{max(all_kw):.1f} kW")
    elif "hourly_profile" in st.session_state:
        hourly_load_profile = st.session_state["hourly_profile"]
        avg = sum(hourly_load_profile.values()) / 24
        st.info(f"Förbrukningsprofil laddad: medel {avg:.1f} kW")
    else:
        st.info(t("no_consumption"))

# --- Price data (right column) ---
with col_prices:
    st.subheader(t("prices_header"))
    st.caption(t("prices_caption"))

    # Auto-detect zone from Tibber city if available
    _tibber_city = st.session_state.get("tibber_home", {}).get("city", "")
    _default_zone_idx = 2  # SE3 default
    # Most of Sweden is SE3; Skåne/Blekinge is SE4; Norrland varies
    _se4_cities = {"malmö", "lund", "helsingborg", "kristianstad", "karlskrona", "växjö", "kalmar"}
    if _tibber_city.lower() in _se4_cities:
        _default_zone_idx = 3  # SE4

    price_source = st.radio(t("source"), [t("fetch_api"), t("load_csv")], key="price_src",
                             help="API hämtar från elprisetjustnu.se. CSV om du har en egen fil.")

    if price_source == t("load_csv"):
        price_file = st.file_uploader("Pris-CSV", type=["csv"], key="price_csv",
                                       help="CSV med kolumner: date, hour, sek_per_kwh")
        if price_file:
            df_prices = pd.read_csv(price_file)
            st.session_state["df_prices"] = df_prices
        else:
            df_prices = st.session_state.get("df_prices")
    else:
        zone = st.selectbox(t("price_zone"), ZONES, index=_default_zone_idx,
                            format_func=lambda z: f"{z} — {ZONE_NAMES[z]}")
        # Auto-detect date range from loaded consumption data
        _vf_hourly = st.session_state.get("vattenfall_hourly", [])
        _seasonal = st.session_state.get("seasonal_profile")
        if _vf_hourly:
            _vf_dates = sorted(set(h["date"] for h in _vf_hourly))
            _default_start = date.fromisoformat(_vf_dates[0])
            _default_end = date.fromisoformat(_vf_dates[-1])
        else:
            _default_start = date.today() - timedelta(days=3*365)
            _default_end = date.today() - timedelta(days=1)

        col_d1, col_d2 = st.columns(2)
        start_date = col_d1.date_input(t("from_date"), value=_default_start)
        end_date = col_d2.date_input(t("to_date"), value=_default_end)
        if _vf_hourly:
            st.caption(f"Datumintervall anpassat till Vattenfall-data ({_vf_dates[0]} — {_vf_dates[-1]})")
        if st.button(t("fetch_prices"), type="primary"):
            with st.spinner(t("fetching_prices")):
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
        st.warning(t("load_prices_warning"))

# --- Data status summary ---
# Persist loaded data so it survives page refresh (may fail on cloud deployments)
try:
    save_state(st.session_state)
except (OSError, IOError):
    pass  # Read-only filesystem (e.g., Streamlit Cloud) — state lives in session only

if df_prices is None or len(df_prices) == 0:
    st.error(t("step1_incomplete"))
    st.stop()
else:
    has_consumption = "seasonal_profile" in st.session_state or "hourly_profile" in st.session_state
    if has_consumption:
        # Check date overlap
        _price_min = df_prices["date"].min()
        _price_max = df_prices["date"].max()
        _vf_h = st.session_state.get("vattenfall_hourly", [])
        if _vf_h:
            _cons_min = min(h["date"] for h in _vf_h)
            _cons_max = max(h["date"] for h in _vf_h)
            if _price_min > _cons_min or _price_max < _cons_max:
                st.warning(f"Prisdata ({_price_min} — {_price_max}) täcker inte hela "
                           f"förbrukningsperioden ({_cons_min} — {_cons_max}). "
                           f"Hämta priser för samma period för bästa resultat.")
            else:
                st.success(t("data_synced"))
        else:
            st.success(t("data_loaded"))
    else:
        st.info("**Prisdata laddad.** Förbrukningsprofil saknas — standardvärden används. "
                "Konfigurera din anläggning nedan.")

# ================================================================
# SPREAD ANALYSIS (always shown, informational)
# ================================================================
# "Spread" = the difference between the cheapest and most expensive hour each day.
# This is the battery's earning potential: buy low, sell high.
# A spread of 50 öre/kWh means a 32 kWh battery can earn ~16 kr/day.
# If the spread is consistently under 20 öre, the battery barely breaks even.
# This chart helps the user understand WHY the battery is (or isn't) profitable.
df_plot = df_prices.copy()
df_plot["datetime"] = pd.to_datetime(df_plot["date"] + " " + df_plot["hour"])
spread_data = []
for day, group in df_plot.groupby("date"):
    hourly = group.groupby(group["datetime"].dt.hour)["ore_per_kwh"].mean()
    sorted_p = hourly.sort_values()
    n_cheap = min(4, len(sorted_p))
    cheap = sorted_p.iloc[:n_cheap].mean()
    expensive = sorted_p.iloc[-n_cheap:].mean() if len(sorted_p) > n_cheap else cheap
    rest = sorted_p.iloc[n_cheap:].mean() if len(sorted_p) > n_cheap else 0
    day_min = sorted_p.iloc[0]
    day_max = sorted_p.iloc[-1]
    spread_data.append({"date": day,
                        "cheap": round(cheap, 1), "expensive": round(expensive, 1),
                        "rest": round(rest, 1), "spread": round(rest - cheap, 1),
                        "min": round(day_min, 1), "max": round(day_max, 1),
                        "range": round(day_max - day_min, 1)})
df_spread = pd.DataFrame(spread_data)
df_spread["datetime"] = pd.to_datetime(df_spread["date"])
df_spread["month"] = pd.to_datetime(df_spread["date"]).dt.to_period("M").astype(str)

_median_range = df_spread["range"].median()
_pct80_range = df_spread["range"].quantile(0.8)
with st.expander(t("spread_expander").format(median=f"{_median_range:.0f}", p80=f"{_pct80_range:.0f}"), expanded=False):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t("cheapest_hour"), f"{df_spread['min'].mean():.0f} öre/kWh",
                help="Genomsnittlig lägsta timpris per dag")
    col2.metric(t("most_expensive_hour"), f"{df_spread['max'].mean():.0f} öre/kWh",
                help="Genomsnittlig högsta timpris per dag")
    col3.metric(t("typical_spread"), f"{_median_range:.0f} öre/kWh",
                help="Median skillnad mellan billigaste och dyraste timmen")
    col4.metric(t("good_days"), f"{_pct80_range:.0f} öre/kWh",
                help="Skillnad på de 20% mest lönsamma dagarna")
    st.caption(t("spread_explanation"))
    fig_sp = go.Figure()
    fig_sp.add_trace(go.Scatter(x=df_spread["datetime"], y=df_spread["range"],
                                 mode="lines", name="Daglig skillnad (max-min)",
                                 line=dict(width=1, color="#f39c12")))
    monthly_range = df_spread.groupby("month")["range"].median().reset_index()
    monthly_range["datetime"] = pd.to_datetime(monthly_range["month"])
    fig_sp.add_hline(y=20, line_dash="dash", line_color="gray",
                      annotation_text="Min spread för lönsamhet (~20 öre)")
    fig_sp.update_layout(yaxis_title="Prisskillnad (öre/kWh)", height=300,
                          margin=dict(l=0, r=0, t=30, b=0),
                          legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig_sp, use_container_width=True)

# ================================================================
# STEP 2: YOUR SYSTEM
# ================================================================
# This is the biggest configuration section, split into three columns:
#
# COLUMN 1 — BATTERY: efficiency (93% = 7% lost per charge/discharge cycle),
#   cycle life (8000 = how many cycles before the battery degrades).
#
# COLUMN 2 — SOLAR PANELS: system size (kWp), export price, and solar data source.
#   Three options for solar production data:
#     - PVGIS: satellite-based hourly data from EU (recommended, most accurate)
#     - CSV: upload from your inverter portal (Huawei, SMA, Fronius, etc.)
#     - Model: simplified cos³ curve (least accurate, used as fallback)
#   When real solar data is loaded, the simulation uses actual production
#   instead of estimates — much more accurate for your specific roof/location.
#
# COLUMN 3 — GRID: your grid operator (determines tariff rates), fuse size
#   (limits how fast the battery can charge), and energy tax.
#
# BELOW THE COLUMNS:
#   - Loads: EV charging schedule, flexible loads (pool, hot water)
#   - Heating model: temperature-dependent electricity usage based on SMHI weather
#   - Calibration: fine-tune the model against your actual consumption data
# ================================================================
st.header(t("step2_header"))
st.caption(t("step2_caption"))

col_sys1, col_sys2, col_sys3 = st.columns(3)

with col_sys1:
    st.subheader(t("battery"))
    efficiency = st.slider(t("efficiency"), 70, 100, 93, help=t("efficiency_help")) / 100
    cycle_life = st.number_input(t("cycle_life"), value=8000, min_value=100, step=500,
                                  help=t("cycle_life_help"))

with col_sys2:
    st.subheader(t("solar_panels"))
    use_solar = st.checkbox(t("solar_panels"), value=True)
    if use_solar:
        solar_kwp = st.number_input(t("system_kwp"), value=15.0, min_value=0.0, step=0.5)
        export_factor = st.number_input(t("export_price"), value=1.0, min_value=0.0, max_value=1.5, step=0.05,
                                        help=t("export_price_help"))
        export_fee = st.number_input(t("export_fee"), value=5.0, min_value=0.0, step=1.0,
                                      help=t("export_fee_help"))
        # --- Solar production data sources ---
        _solar_source = st.radio(t("solar_data"), [t("solar_model"), t("solar_pvgis"), t("solar_csv")],
                                  index=1 if not st.session_state.get("tibber_solar_monthly") else 0,
                                  horizontal=True, key="solar_source",
                                  help=t("solar_data_help"))

        if _solar_source == t("solar_pvgis"):
            from weather import SWEDISH_CITIES
            _th = st.session_state.get("tibber_home", {})
            _pvgis_lat = _th.get("latitude", 0)
            _pvgis_lon = _th.get("longitude", 0)
            if not (_pvgis_lat and _pvgis_lon):
                _pvgis_city = st.selectbox(t("solar_location"), list(SWEDISH_CITIES.keys()),
                                            index=0, key="pvgis_city")
                _pvgis_lat, _pvgis_lon = SWEDISH_CITIES[_pvgis_city]
            _c1, _c2 = st.columns(2)
            _pvgis_tilt = _c1.number_input(t("tilt"), value=35, min_value=0, max_value=90, step=5,
                                            key="pvgis_tilt", help=t("tilt_help"))
            _pvgis_aspect = _c2.number_input(t("direction"), value=0, min_value=-180, max_value=180, step=15,
                                              key="pvgis_aspect", help=t("direction_help"))
            if st.button(t("fetch_pvgis"), key="pvgis_fetch"):
                with st.spinner(t("fetching_pvgis")):
                    try:
                        from pvgis_source import fetch_pvgis, pvgis_to_hourly_dict, pvgis_to_monthly_kwh
                        records = fetch_pvgis(lat=_pvgis_lat, lon=_pvgis_lon, peakpower=solar_kwp,
                                              loss=14, angle=_pvgis_tilt, aspect=_pvgis_aspect,
                                              startyear=2020, endyear=2023)
                        if records:
                            st.session_state["tibber_solar_hourly"] = pvgis_to_hourly_dict(records)
                            st.session_state["tibber_solar_monthly"] = pvgis_to_monthly_kwh(records)
                            yearly = sum(pvgis_to_monthly_kwh(records).values())
                            years = len(set(r["date"][:4] for r in records))
                            st.success(f"PVGIS: {len(records):,} timvärden ({years} år), "
                                       f"~{yearly:,.0f} kWh/år")
                        else:
                            st.warning("Inga data från PVGIS. Kontrollera koordinater.")
                    except Exception as e:
                        st.error(f"PVGIS-fel: {e}")

        elif _solar_source == t("solar_csv"):
            solar_csv = st.file_uploader(t("solar_production_csv"), type=["csv", "txt"],
                                          key="solar_csv_upload",
                                          help=t("solar_csv_help"))
            if solar_csv:
                try:
                    from import_solar import parse_solar_csv, solar_to_hourly_dict, solar_to_monthly_kwh
                    raw = solar_csv.getvalue()
                    records = None
                    for enc in ["utf-8", "utf-8-sig", "iso-8859-1", "cp1252"]:
                        try:
                            records = parse_solar_csv(raw.decode(enc), solar_csv.name)
                            break
                        except (UnicodeDecodeError, ValueError):
                            continue
                    if records:
                        st.session_state["tibber_solar_hourly"] = solar_to_hourly_dict(records)
                        st.session_state["tibber_solar_monthly"] = solar_to_monthly_kwh(records)
                        days = len(set(r["date"] for r in records))
                        total = sum(r["production_kwh"] for r in records)
                        st.success(f"Soldata laddad: {len(records):,} timvärden ({days} dagar), {total:,.0f} kWh totalt")
                    else:
                        st.warning("Kunde inte tolka soldata-CSV. Kontrollera format.")
                except Exception as e:
                    st.error(f"Importfel soldata: {e}")

        _has_real_solar = bool(st.session_state.get("tibber_solar_monthly"))
        _use_real_solar = _has_real_solar and _solar_source != t("solar_model")
        if solar_kwp > 0:
            solar_config = SolarConfig(capacity_kwp=solar_kwp)
            if _use_real_solar:
                solar_config.real_production = st.session_state.get("tibber_solar_hourly")
                solar_config.real_monthly_kwh = st.session_state.get("tibber_solar_monthly")
                monthly_kwh = solar_config.real_monthly_kwh
                yearly = sum(monthly_kwh.values())
                _src_label = {t("solar_pvgis"): "PVGIS", t("solar_csv"): "CSV"}.get(
                    _solar_source, "Tibber")
                st.caption(f"{_src_label}: {yearly:,.0f} kWh/år "
                           f"(cos³-modell: {sum(MONTHLY_KWH_PER_KWP.values()) * solar_kwp * 0.85:,.0f} kWh/år)")
        else:
            solar_config = None
    else:
        solar_config = None
        solar_kwp = 0
        export_factor = 1.0
        export_fee = 5.0

with col_sys3:
    st.subheader(t("grid"))
    # Auto-detect grid operator from Tibber if available
    _op_names = list(GRID_OPERATORS.keys())
    _op_default = 0
    _tibber_home = st.session_state.get("tibber_home", {})
    if _tibber_home.get("grid_company"):
        _gc = _tibber_home["grid_company"].lower()
        for i, name in enumerate(_op_names):
            if name.lower().split()[0] in _gc or _gc.split()[0] in name.lower():
                _op_default = i
                break
    grid_operator = st.selectbox(t("grid_operator"), _op_names, index=_op_default,
                                  help=t("grid_operator_help"))
    op_info = GRID_OPERATORS[grid_operator]
    op_fuse_fees = get_operator_fuse_fees(grid_operator)
    fuse_options = sorted(op_fuse_fees.keys())
    # Auto-detect fuse size from Tibber
    _fuse_default = 25
    _tibber_fuse = st.session_state.get("tibber_home", {}).get("fuse_size", 0)
    if _tibber_fuse and _tibber_fuse in fuse_options:
        _fuse_default = _tibber_fuse
    fuse_amps = st.selectbox(t("fuse_size"), fuse_options,
                              index=fuse_options.index(_fuse_default) if _fuse_default in fuse_options else 0,
                              format_func=lambda a: f"{a:.0f}A — {op_fuse_fees[a]:,.0f} kr/år",
                              help=t("fuse_help"))
    phases = st.selectbox(t("phases"), [3, 1], index=0)
    energy_tax = st.number_input(t("energy_tax"), value=45.0, step=0.1,
                                  help=t("energy_tax_help"))
    available_tariffs = op_info["tariffs"]
    has_effekt = "Effekttariff" in available_tariffs and op_info.get("effekttariff")
    _fuse_fee_yr = op_fuse_fees.get(fuse_amps, 0)
    _fuse_list = ", ".join(f"{f:.0f}A" for f in fuse_options)
    if has_effekt:
        eff = op_info["effekttariff"]
        st.info(f"**{grid_operator}** — simulerar: {', '.join(available_tariffs)} "
                f"({eff['effekt_rate']} kr/kW/mån) och säkring {_fuse_list}")
    else:
        st.info(f"**{grid_operator}** — simulerar: {', '.join(available_tariffs)} "
                f"och säkring {_fuse_list}")
    with st.expander("Tariffdetaljer", expanded=False):
        if "tidstariff" in op_info:
            _tid = op_info["tidstariff"]
            st.markdown("**Tidstariff**")
            st.caption("Höglast: jan-mar + nov-dec, vardagar 06-22 (ej helgdagar). Övrig tid: alla andra timmar.")
            peak_rate = st.number_input("Höglast (öre/kWh)", value=_tid["peak"], step=0.5)
            offpeak_rate = st.number_input("Övrig tid (öre/kWh)", value=_tid["offpeak"], step=0.5)
        else:
            peak_rate = 76.5
            offpeak_rate = 30.5
        if "enkeltariff" in op_info:
            _enkel = op_info["enkeltariff"]
            st.markdown("**Enkeltariff**")
            st.caption("Samma avgift alla timmar, alla dagar.")
            flat_rate = st.number_input("Överföring (öre/kWh)", value=_enkel["flat_rate"], step=0.5)
        else:
            flat_rate = 44.5
        if has_effekt:
            eff = op_info["effekttariff"]
            st.markdown("**Effekttariff**")
            _peak_desc = "alla timmar" if not eff.get("peak_months") else (
                f"vardagar {eff.get('peak_hour_start', 0):02d}-{eff.get('peak_hour_end', 24):02d}, "
                f"nov-mar" if eff.get("peak_weekday_only") else "alla dagar")
            _night_desc = f", natt (22-06) räknas till {eff.get('night_discount', 1)*100:.0f}%" if eff.get("night_discount", 1) < 1 else ""
            st.caption(f"Effektmätning: medel av {eff['top_n_peaks']} högsta toppar från olika dagar. "
                       f"Mätperiod: {_peak_desc}{_night_desc}.")
            effekt_rate = st.number_input("Effektavgift (kr/kW/mån)", value=eff["effekt_rate"], step=1.0)
            effekt_energy = st.number_input("Energiavgift (öre/kWh)", value=eff["energy_rate"], step=0.5)
            effekt_top_n = st.number_input("Antal toppar", value=eff["top_n_peaks"], min_value=1, max_value=10)
        st.markdown("---")
        monthly_fee = op_fuse_fees.get(fuse_amps, 0) / 12
        st.caption(f"Energiskatt: {energy_tax} öre/kWh | "
                   f"Abonnemang {fuse_amps:.0f}A: {monthly_fee:,.0f} kr/mån ({op_fuse_fees.get(fuse_amps, 0):,.0f} kr/år)")

# ---- LOADS ----
# Two types of electricity loads beyond basic household use:
#
# SCHEDULED LOADS (left column):
#   Fixed-schedule loads like EV charging. Example: "Elbil 11 kW, 23:00-03:00"
#   These always run at their scheduled time regardless of price.
#   The battery can't shift these, but it can discharge to cover part of them.
#
# FLEXIBLE LOADS (right column):
#   Loads that can shift to when solar surplus is available. Example: pool pump, hot water.
#   The simulation runs these AFTER the battery is charged, using leftover solar.
#   This means: solar → battery → flex loads → grid export (priority order).
#   The goal is near-zero grid export — use ALL solar production in the house.
st.subheader(t("loads_header"))
st.caption(t("loads_caption"))
col_l1, col_l2 = st.columns(2)

with col_l1:
    if not (seasonal_load_profile or hourly_load_profile):
        base_load = st.number_input(t("base_load"), value=1.5, min_value=0.0, step=0.5,
                                    help=t("base_load_help"))
    else:
        base_load = 1.5  # overridden by profile or heating model

    if "scheduled_loads" not in st.session_state:
        st.session_state["scheduled_loads"] = [{"name": "Elbil", "power": 11.0, "start": 23, "end": 3}]

    st.markdown(t("scheduled_loads"))
    st.caption(t("scheduled_caption"))
    for i, load in enumerate(st.session_state["scheduled_loads"]):
        c = st.columns([3, 2, 2, 2, 1])
        load["name"] = c[0].text_input("", value=load["name"], key=f"ln_{i}", label_visibility="collapsed")
        load["power"] = c[1].number_input("kW", value=load["power"], min_value=0.0, step=0.5, key=f"lp_{i}")
        load["start"] = c[2].number_input("Från", value=load["start"], min_value=0, max_value=23, key=f"ls_{i}")
        load["end"] = c[3].number_input("Till", value=load["end"], min_value=0, max_value=23, key=f"le_{i}")
        if c[4].button("X", key=f"lx_{i}"):
            st.session_state["scheduled_loads"].pop(i)
            st.rerun()

    if st.button(t("add_load")):
        st.session_state["scheduled_loads"].append({"name": "Ny", "power": 1.0, "start": 0, "end": 6})
        st.rerun()

with col_l2:
    if "flexible_loads" not in st.session_state:
        st.session_state["flexible_loads"] = [
            {"name": "Poolpump", "power": 3.0, "daily": 20.0, "sm": 5, "em": 9},
            {"name": "Varmvatten", "power": 3.0, "daily": 99.0, "sm": 1, "em": 12},
        ]

    _month_names = ["Jan", "Feb", "Mar", "Apr", "Maj", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]
    _month_opts = list(range(1, 13))

    st.markdown(t("flexible_loads"))
    st.caption(t("flexible_caption"))
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

    if st.button(t("add_flex_load")):
        st.session_state["flexible_loads"].append({"name": "Ny", "power": 2.0, "daily": 10.0, "sm": 1, "em": 12})
        st.rerun()

scheduled_loads = [LoadSchedule(l["name"], l["power"], l["start"], l["end"])
                   for l in st.session_state["scheduled_loads"] if l["power"] > 0]
flexible_loads = [FlexibleLoad(f["name"], f["power"], f["daily"], f["sm"], f["em"])
                  for f in st.session_state["flexible_loads"] if f["power"] > 0]

# Add luft-luft as flexible load when enabled (absorbs solar surplus)
if st.session_state.get("use_aa", False):
    _aa_kw = st.session_state.get("aa_heat_kw", 3.2)
    _aa_cool = st.session_state.get("aa_cool_kw", 2.5)
    # Summer: pre-cool house on solar surplus (thermal storage)
    flexible_loads.append(FlexibleLoad("Luft-luft AC (solöverskott)", _aa_cool, daily_kwh=8.0,
                                        start_month=6, end_month=8))
    # Spring/autumn: pre-heat on solar surplus
    flexible_loads.append(FlexibleLoad("Luft-luft värme (solöverskott)", _aa_kw, daily_kwh=8.0,
                                        start_month=3, end_month=5))
    flexible_loads.append(FlexibleLoad("Luft-luft värme (solöverskott)", _aa_kw, daily_kwh=8.0,
                                        start_month=9, end_month=10))

# ---- HEATING MODEL ----
# This is the most complex part of the configuration. It calculates how much
# electricity your heating system uses each hour, based on outdoor temperature.
#
# WHY IT MATTERS: In winter, heating can be 60-70% of your electricity bill.
# A cold hour means high demand, which means the battery has more to work with.
# Without this model, the simulation would assume constant load all year —
# missing the fact that winter has both highest prices AND highest consumption.
#
# HOW IT WORKS:
#   1. Fetch hourly temperatures from SMHI (nearest weather station)
#   2. Calculate heat loss: P_heat = h_loss × (21°C - outdoor_temp)
#   3. Divide by heat pump COP (efficiency) to get electricity needed
#   4. Add hot water (DHW) and base load (fridge, lights, etc.)
#   5. Result: a full year of hourly electricity profiles per date
#
# CALIBRATION: If you have real consumption data (Tibber/Vattenfall), the model
# auto-calibrates h_loss (heat loss coefficient) to match your actual usage.
# This is much more accurate than estimating from energy class + house area.
st.subheader("Uppvärmning")
use_heating_model = st.checkbox("Temperaturanpassad lastmodell", value=True,
                                 help="Modellerar värmepumpens elförbrukning baserat på väderdata och husets egenskaper")
daily_load_override = None
heating_config = None

if use_heating_model:
    st.caption(
        "Modellen beräknar husets elförbrukning för uppvärmning timme för timme, "
        "baserat på **verklig temperatur** från SMHI och **husets egenskaper** (energiklass, yta, värmepumptyp). "
        "Kall timme = hög förbrukning = mer egenanvändning av sol/batteri. "
        "Varm timme = låg förbrukning = mer överskott att sälja. "
        "Har du laddat förbrukningsdata (Tibber/Vattenfall) kalibreras modellen automatiskt mot din verkliga förbrukning."
    )
    # --- Location selection ---
    st.markdown("**Plats (för väderdata)**")
    city_names = sorted(SWEDISH_CITIES.keys())
    # Auto-detect city from Tibber if available
    _city_default = city_names.index("Sigtuna") if "Sigtuna" in city_names else 0
    _th = st.session_state.get("tibber_home", {})
    _tibber_city = _th.get("city", "")
    _tibber_lat = _th.get("latitude", 0)
    _tibber_lon = _th.get("longitude", 0)
    if _tibber_city:
        for i, c in enumerate(city_names):
            if c.lower() == _tibber_city.lower():
                _city_default = i
                break

    col_loc1, col_loc2 = st.columns([2, 3])
    with col_loc1:
        selected_city = st.selectbox("Stad / ort", city_names, index=_city_default,
                                      help="Välj den ort som är närmast dig. "
                                           "Hämtas automatiskt från Tibber om tillgänglig.")

    # Use exact Tibber coordinates if available, otherwise city center
    if _tibber_lat and _tibber_lon and selected_city.lower() == _tibber_city.lower():
        city_lat, city_lon = _tibber_lat, _tibber_lon
    else:
        city_lat, city_lon = SWEDISH_CITIES[selected_city]

    # Find nearest SMHI station
    try:
        stations = get_stations()
    except Exception:
        stations = {"97400": ("Stockholm-Arlanda Flygplats", 59.6269, 17.9545)}
    station_id, station_name, station_dist = find_nearest_station(city_lat, city_lon, stations)

    with col_loc2:
        _loc_source = "exakta koordinater från Tibber" if (_tibber_lat and _tibber_lon and selected_city.lower() == _tibber_city.lower()) else "stadscentrum"
        st.caption(f"Närmaste SMHI-station: **{station_name}** ({station_dist:.0f} km, baserat på {_loc_source})")
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
            _tibber_size = st.session_state.get("tibber_home", {}).get("house_size", 0)
            _area_default = _tibber_size if _tibber_size > 0 else 150
            house_area = st.number_input("Boyta (m²)", value=_area_default, min_value=30, max_value=500, step=10,
                                          help="Hämtas från Tibber om tillgänglig.")

        # Derive h_loss: calibrated data wins over energy class estimate
        kwh_m2 = _ENERGY_CLASSES[energy_class]
        bldg_energy = kwh_m2 * house_area
        heat_elec_est = max(0, bldg_energy - _DHW_ANNUAL - _VENT_ANNUAL)
        h_loss_from_class = round(heat_elec_est * _COP_AVG / _DEGREE_HOURS, 3)

        # Check if manual calibration data exists (from "Kalibrera" section below)
        # or if we can auto-calibrate from loaded consumption profile
        h_loss_default = h_loss_from_class
        _calibrated = False

        # Auto-calibrate from consumption profile if available
        if "seasonal_profile" in st.session_state and temps_data:
            from heating import fit_heating_model
            _cal_seasonal = st.session_state["seasonal_profile"]
            _cal_daily = []
            for month, hourly in _cal_seasonal.items():
                days_in_month = [31,28,31,30,31,30,31,31,30,31,30,31][month-1]
                daily_kwh = sum(hourly.values())
                for d in range(1, days_in_month+1):
                    _cal_daily.append({"date": f"2024-{month:02d}-{d:02d}", "consumption_kwh": daily_kwh})
            _cal_cfg = HeatingConfig(h_loss=h_loss_from_class)
            _fitted = fit_heating_model(_cal_daily, temps_data, _cal_cfg)
            if abs(_fitted.h_loss - h_loss_from_class) > 0.005:
                h_loss_default = round(_fitted.h_loss, 3)
                _calibrated = True

        with col_house2:
            _heating_options = ["Bergvärme (mark/sjö)", "Luftvärmepump", "Fjärrvärme", "Direktel (element)"]
            _tibber_heat = st.session_state.get("tibber_home", {}).get("heating_source", "")
            _heat_map = {"GROUND": 0, "AIR2AIR": 1, "AIR2WATER": 1,
                          "DISTRICT": 2, "ELECTRIC": 3}
            _heat_default = _heat_map.get(_tibber_heat, 0)
            heating_type = st.selectbox("Uppvärmning", _heating_options, index=_heat_default,
                                         help="Hämtas från Tibber om tillgänglig. Påverkar COP-beräkningen.")

            if heating_type == "Bergvärme (mark/sjö)":
                cop_info = "COP ~3.2–3.5 (nära konstant, brintemp varierar inte med utetemperatur)"
            elif heating_type == "Luftvärmepump":
                cop_info = "COP 1.5–4.5, sämre vid kyla"
            elif heating_type == "Fjärrvärme":
                cop_info = "Ingen VP — elkostnad för cirkulationspump"
            else:
                cop_info = "COP = 1.0 (ren eluppvärmning)"
            st.caption(cop_info)

            # Air-to-air supplement (works with any primary heating)
            use_aa = st.checkbox("Luft-luft komplement (AC + uppvärmning)", value=False,
                                  key="use_aa",
                                  help="Luft-luft VP som komplement: AC på sommaren, "
                                       "uppvärmning när utetemperaturen är tillräckligt hög.")
            if use_aa:
                # Preset models
                _AA_PRESETS = {
                    "Mitsubishi Hero 2.0 LN25 (SCOP 5.2, A+++)": {
                        "heat_kw": 3.2, "cool_kw": 2.5, "price": 30000,
                        "info": "23,990 kr + ~6,000 installation. 6.3 kW max värme, -35°C till +31°C.",
                    },
                    "Anpassad": {
                        "heat_kw": 3.0, "cool_kw": 2.5, "price": 25000,
                        "info": "Fyll i egna värden.",
                    },
                }
                aa_model = st.selectbox("Modell", list(_AA_PRESETS.keys()), index=0, key="aa_model")
                _aa_preset = _AA_PRESETS[aa_model]
                _aa_custom = aa_model == "Anpassad"

                col_aa1, col_aa2, col_aa3 = st.columns(3)
                with col_aa1:
                    aa_heat_kw = st.number_input("Luft-luft värmeeffekt (kW)",
                                                  value=_aa_preset["heat_kw"],
                                                  min_value=0.5, max_value=10.0, step=0.5,
                                                  key="aa_heat_kw", disabled=not _aa_custom,
                                                  help="Nominell värmeeffekt.")
                    aa_min_temp = st.number_input("Min utetemperatur för drift (°C)", value=1.0,
                                                   min_value=-20.0, max_value=10.0, step=1.0,
                                                   key="aa_min_temp",
                                                   help="Under denna temperatur stängs luft-luft av.")
                with col_aa2:
                    aa_cool_kw = st.number_input("Luft-luft kyleffekt (kW)",
                                                  value=_aa_preset["cool_kw"],
                                                  min_value=0.5, max_value=10.0, step=0.5,
                                                  key="aa_cool_kw", disabled=not _aa_custom,
                                                  help="Nominell kyleffekt.")
                    aa_cool_threshold = st.number_input("Kylning startar vid (°C ute)", value=24.0,
                                                         min_value=18.0, max_value=35.0, step=1.0,
                                                         key="aa_cool_threshold",
                                                         help="Utetemperatur då AC startar.")
                with col_aa3:
                    aa_price = st.number_input("Pris inkl installation (SEK)",
                                                value=_aa_preset["price"],
                                                min_value=0, step=1000, key="aa_price",
                                                disabled=not _aa_custom,
                                                help=_aa_preset["info"])
                    aa_lifetime = st.number_input("Livslängd (år)", value=15,
                                                    min_value=5, max_value=25, step=1, key="aa_lifetime")
                if not _aa_custom:
                    # Use preset values (override any widget state from previous custom selection)
                    aa_heat_kw = _aa_preset["heat_kw"]
                    aa_cool_kw = _aa_preset["cool_kw"]
                    aa_price = _aa_preset["price"]
                st.caption(_aa_preset["info"])

        # Derive defaults: if calibrated from real data, use calibration-consistent values.
        # If not calibrated, estimate from house area.
        _tibber_residents = st.session_state.get("tibber_home", {}).get("residents", 0)

        if _calibrated:
            # We know h_loss from real data. Derive HP size from peak demand at design temp (-15°C)
            _peak_demand = h_loss_default * (21 - (-15))  # kW thermal
            _hp_max_default = round(max(4.0, min(12.0, _peak_demand)), 1)
            # Base and DHW: use Tibber Insights if available, otherwise conservative defaults
            _cal_data = st.session_state.get("tibber_home", {})
            if _tibber_residents > 0:
                _dhw_default = round(max(3.0, min(12.0, _tibber_residents * 2.0)), 1)
                _base_default = round(max(0.3, min(1.2, 0.3 + _tibber_residents * 0.1)), 2)
            else:
                _dhw_default = 6.0
                _base_default = 0.68
        else:
            # No calibration — estimate from house area
            _hp_max_default = round(max(4.0, min(12.0, house_area / 25)), 1)
            _base_default = round(max(0.3, min(1.2, 0.3 + house_area / 300)), 2)
            if _tibber_residents > 0:
                _dhw_default = round(max(3.0, min(12.0, _tibber_residents * 2.0)), 1)
            else:
                _dhw_default = round(max(3.0, min(10.0, 3.0 + house_area / 50)), 1)

        # Detailed settings in expander
        with st.expander("Detaljerade VP-inställningar", expanded=False):
            col_h1, col_h2, col_h3 = st.columns(3)
            with col_h1:
                _hloss_help = (f"Kalibrerat {h_loss_default:.3f} kW/°C från din förbrukningsdata."
                               if _calibrated else
                               f"Uppskattat {h_loss_default:.3f} kW/°C från energiklass + yta. "
                               f"Ladda förbrukningsdata eller fyll i Tibber Insikter för exakt kalibrering.")
                h_loss = st.number_input("Värmeförlust (kW/°C)", value=h_loss_default,
                                          min_value=0.01, max_value=1.5, step=0.001, format="%.3f",
                                          help=_hloss_help)
                if _calibrated:
                    st.caption(f"Kalibrerat mot verklig förbrukning. "
                               f"Energiklass, yta och VP-inställningar nedan påverkar inte simuleringen.")
                hp_max = st.number_input("VP max värmeeffekt (kW)", value=_hp_max_default, min_value=1.0, step=0.5,
                                          help=f"Uppskattat {_hp_max_default} kW för {house_area} m². "
                                               f"Typiskt 4-8 kW för villa, 8-12 kW för större hus.")
            with col_h2:
                elpatron_kw = st.number_input("Elpatron (kW)", value=3.0, min_value=0.0, step=0.5,
                                               help="Tillsatsvärme vid extremkyla. 0 om ingen.")
                dhw_kwh = st.number_input("Varmvatten (kWh el/dag)", value=_dhw_default, min_value=0.0, step=1.0,
                                           help=f"Uppskattat {_dhw_default} kWh/dag för {house_area} m². "
                                                f"Beror på antal personer (~2 kWh/person/dag via VP).")
            with col_h3:
                non_heat_base = st.number_input("Bas utan värme/EV (kW)", value=_base_default, min_value=0.0,
                                                 step=0.01, format="%.2f",
                                                 help=f"Uppskattat {_base_default} kW för {house_area} m². "
                                                      f"Belysning, kyl/frys, ventilation, etc.")

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

        _aa_kwargs = {}
        if use_aa:
            _aa_kwargs = dict(
                aa_enabled=True,
                aa_max_heat_kw=aa_heat_kw,
                aa_max_cool_kw=aa_cool_kw,
                aa_min_temp=aa_min_temp,
                aa_cool_threshold=aa_cool_threshold,
            )
        heating_config = HeatingConfig(
            h_loss=h_loss, hp_max_heat_kw=hp_max,
            elpatron_kw=elpatron_kw, dhw_kwh_per_day=dhw_kwh,
            cop_base=cop_base, cop_slope=cop_slope,
            **_aa_kwargs,
        )

        # Luft-luft ROI estimate (compare electricity with vs without)
        if use_aa and temps_data:
            cfg_without = HeatingConfig(
                h_loss=h_loss, hp_max_heat_kw=hp_max,
                elpatron_kw=elpatron_kw, dhw_kwh_per_day=dhw_kwh,
                cop_base=cop_base, cop_slope=cop_slope,
            )
            _aa_kwh_with = 0
            _aa_kwh_without = 0
            for _d, _hourly in temps_data.items():
                for _hr, _t in _hourly:
                    _aa_kwh_with += heating_electricity_kw(_t, heating_config)
                    _aa_kwh_without += heating_electricity_kw(_t, cfg_without)
            _aa_years = len(temps_data) / 365.25
            _aa_saving_kwh = (_aa_kwh_without - _aa_kwh_with) / _aa_years
            _aa_cooling_kwh = 0
            for _d, _hourly in temps_data.items():
                for _hr, _t in _hourly:
                    from heating import cooling_electricity_kw
                    _aa_cooling_kwh += cooling_electricity_kw(_t, heating_config)
            _aa_cooling_kwh_yr = _aa_cooling_kwh / _aa_years
            # Estimate value: heating savings × avg spot price, cooling is added cost
            _avg_ore = 60  # rough average spot + grid fee
            _aa_saving_kr = _aa_saving_kwh * _avg_ore / 100
            _aa_cooling_kr = _aa_cooling_kwh_yr * _avg_ore / 100
            _aa_net_kr = _aa_saving_kr - _aa_cooling_kr
            _aa_payback = aa_price / _aa_net_kr if _aa_net_kr > 0 else 999
            _aa_profit = _aa_net_kr * aa_lifetime - aa_price

            with st.expander("Luft-luft investering", expanded=False):
                col_roi1, col_roi2 = st.columns(2)
                with col_roi1:
                    st.metric("Värmebesparing", f"{_aa_saving_kwh:,.0f} kWh/år",
                              help="Minskad elförbrukning för uppvärmning tack vare luft-luft")
                    st.metric("AC-förbrukning", f"{_aa_cooling_kwh_yr:,.0f} kWh/år",
                              help="Tillkommande elförbrukning för kylning")
                with col_roi2:
                    st.metric("Nettobesparing", f"{_aa_net_kr:,.0f} kr/år",
                              help="Värmebesparing minus AC-kostnad (vid ~60 öre/kWh snitt)")
                    if _aa_net_kr > 0:
                        st.metric("Återbetalningstid", f"{_aa_payback:.1f} år")
                    else:
                        st.metric("Återbetalningstid", "—",
                                  help="AC-kostnaden överstiger värmebesparingen. "
                                       "Investeringen motiveras av komfort, inte besparing.")
                if _aa_net_kr > 0:
                    st.info(f"Investering {aa_price:,} kr → netto **{_aa_profit:+,.0f} kr** "
                            f"under {aa_lifetime} år ({_aa_net_kr/12:,.0f} kr/mån)")
                else:
                    st.info(f"Luft-luft sparar {_aa_saving_kwh:,.0f} kWh/år på uppvärmning "
                            f"men AC-driften kostar {_aa_cooling_kwh_yr:,.0f} kWh/år. "
                            f"Investeringen motiveras av komfort (AC), inte elbesparing.")

        # --- Manual calibration from Tibber Insights ---
        with st.expander("Kalibrera mot din förbrukning", expanded=True):
            st.caption(
                "Fyll i din årsförbrukning uppdelad per kategori för exakt kalibrering. "
                "Hittas i din elapp: Tibber (Insikter), Greenely (Förbrukningsanalys), "
                "eller på din elnätsägares Mina sidor."
            )
            col_cal1, col_cal2 = st.columns(2)
            with col_cal1:
                cal_year = st.selectbox("År att kalibrera mot", [2025, 2024, 2023], index=0,
                                         key="cal_year")
                cal_total = st.number_input("Total förbrukning (kWh/år)", value=0, min_value=0,
                                             step=100, key="cal_total",
                                             help="Hela årets elförbrukning. Finns på elräkningen eller i din elapp.")
                cal_heating = st.number_input("Uppvärmning + varmvatten (kWh/år)", value=0, min_value=0,
                                               step=100, key="cal_heating",
                                               help="Värmepump + varmvatten. Kallas 'Uppvärmning' i Tibber/Greenely.")
            with col_cal2:
                cal_ev = st.number_input("Elbil (kWh/år)", value=0, min_value=0,
                                          step=100, key="cal_ev",
                                          help="Laddning av elbil. 0 om ingen elbil.")
                cal_active = st.number_input("Matlagning, belysning etc (kWh/år)", value=0, min_value=0,
                                              step=100, key="cal_active",
                                              help="Spis, ugn, belysning, tvätt, disk — det du aktivt använder.")
                cal_always = st.number_input("Alltid på (kWh/år)", value=0, min_value=0,
                                              step=100, key="cal_always",
                                              help="Kyl, frys, ventilation, standby — det som alltid drar.")

            if cal_heating > 0 and cal_total > 0:
                # Calibrate h_loss from heating data + temperature
                year_temps = {d: h for d, h in temps_data.items() if d.startswith(str(cal_year))}
                if len(year_temps) > 300:
                    # DHW is included in Tibber's "heating" category
                    # Estimate: heating_kwh = space_heating_elec + DHW_elec
                    _cal_dhw_annual = dhw_kwh * 365
                    _cal_space = max(0, cal_heating - _cal_dhw_annual)

                    _cal_sum = 0
                    for d, hourly in year_temps.items():
                        for hr, temp_c in hourly:
                            delta_t = max(0, heating_config.t_indoor - temp_c)
                            if delta_t > 0:
                                cop = max(heating_config.cop_min,
                                          heating_config.cop_base + heating_config.cop_slope * temp_c)
                                _cal_sum += delta_t / cop

                    if _cal_sum > 0:
                        cal_h_loss = _cal_space / _cal_sum
                        # Update base load from non-heating data
                        cal_base = (cal_active + cal_always) / 365 / 24 if (cal_active + cal_always) > 0 else non_heat_base

                        st.success(
                            f"Kalibrerat mot {cal_year}: **h_loss = {cal_h_loss:.3f} kW/°C**, "
                            f"bas = {cal_base:.2f} kW "
                            f"(uppvärmning {cal_heating:,} kWh, EV {cal_ev:,} kWh, "
                            f"övrigt {cal_active + cal_always:,} kWh)"
                        )

                        # Apply calibration
                        heating_config = HeatingConfig(
                            h_loss=round(cal_h_loss, 4),
                            hp_max_heat_kw=hp_max,
                            elpatron_kw=elpatron_kw,
                            dhw_kwh_per_day=dhw_kwh,
                            cop_base=cop_base, cop_slope=cop_slope,
                        )
                        non_heat_base = cal_base
                else:
                    st.warning(f"Inte tillräckligt med väderdata för {cal_year} "
                               f"({len(year_temps)} dagar). Behöver minst 300.")

        # Note: auto-calibration from consumption profile is done BEFORE the widget
        # (see h_loss_default computation above) so it's already applied

        # Build daily_load_override: house load per hour per date
        daily_load_override = {}
        for date_str, hourly_temps in temps_data.items():
            t_by_hour = {h: _temp for h, _temp in hourly_temps}
            profile = {}
            for h in range(24):
                _temp = t_by_hour.get(h)
                if _temp is None:
                    available = sorted(t_by_hour.keys())
                    nearest = min(available, key=lambda k: abs(k - h))
                    _temp = t_by_hour[nearest]
                heat_kw = heating_electricity_kw(_temp, heating_config)
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
# Two pricing modes:
#   1. "Specificerade batterier (NKON)" — an editable table with real NKON ESS Pro
#      prices. User can add/remove rows. Multi-unit configs (2x32 kWh) supported.
#   2. "SEK per kWh" — enter a single price per kWh, and the app generates
#      sizes from 5-100 kWh to find the optimal one (self-consumption mode).
#
# The installation cost is shared across all sizes (same electrician work).
# Solar costs are separate (material + installation).
# Financing: cash, mortgage (bolån), or separate loan — affects monthly cashflow.
# ================================================================
st.header(t("step3_header"))

# Battery pricing mode
st.subheader(t("battery_prices"))
_pricing_mode = st.radio(t("pricing_mode"), [t("specific_batteries"), t("sek_per_kwh_mode")],
                          key="pricing_mode", horizontal=True)

if _pricing_mode == t("sek_per_kwh_mode"):
    st.caption("Ange pris per kWh och max laddeffekt. Simuleringen testar storlekar "
               "från 5 till 100 kWh och hittar den storlek som maximerar egenförbrukning.")
    col_sek1, col_sek2, col_sek3 = st.columns(3)
    with col_sek1:
        sek_per_kwh = st.number_input(t("battery_price_kwh"), value=1000, min_value=100, max_value=5000,
                                       step=50, key="sek_per_kwh",
                                       help="Typiskt 800-1500 SEK/kWh för LiFePO4.")
    with col_sek2:
        max_charge_kw = st.number_input(t("max_charge_kw"), value=11.0, min_value=1.0, max_value=30.0,
                                         step=0.5, key="max_charge_kw_auto",
                                         help="Begränsas av inverter. NKON: 11 kW (16 kWh), 15 kW (32 kWh).")
    with col_sek3:
        _step_kwh = st.number_input(t("step_kwh"), value=5, min_value=1, max_value=20, step=1,
                                     key="auto_step_kwh",
                                     help="Storlekar testas i detta steg: 5, 10, 15, ... kWh")

    # Generate battery table from SEK/kWh
    _sizes = list(range(_step_kwh, 101, _step_kwh))
    battery_table = pd.DataFrame([
        {"Namn": f"{s} kWh", "Kapacitet_kWh": float(s),
         "Max_kW": min(max_charge_kw, s * 0.5),  # C-rate max ~0.5C
         "Pris_SEK": round(s * sek_per_kwh)}
        for s in _sizes
    ])
    st.caption(f"Testar {len(_sizes)} storlekar: {_sizes[0]}–{_sizes[-1]} kWh à {sek_per_kwh} kr/kWh")

else:
    st.caption("Redigera tabellen nedan — lägg till/ta bort rader, ändra priser. "
               "NKON ESS Pro (LiFePO4) som standard.")

    EUR_SEK = st.number_input(t("eur_sek_rate"), value=11.5, min_value=5.0, max_value=20.0, step=0.1,
                               key="eur_sek_rate")

    default_batteries = pd.DataFrame([
        {"Namn": "5 kWh",       "Kapacitet_kWh": 5.12,   "Max_kW": 3.8,  "Pris_SEK": round(600 * EUR_SEK)},
        {"Namn": "10 kWh",      "Kapacitet_kWh": 10.24,  "Max_kW": 7.5,  "Pris_SEK": round(1177 * EUR_SEK)},
        {"Namn": "16 kWh",      "Kapacitet_kWh": 16.10,  "Max_kW": 11.0, "Pris_SEK": round(1512 * EUR_SEK)},
        {"Namn": "32 kWh",      "Kapacitet_kWh": 32.15,  "Max_kW": 15.0, "Pris_SEK": round(2857 * EUR_SEK)},
        {"Namn": "32+16 kWh",   "Kapacitet_kWh": 48.25,  "Max_kW": 15.0, "Pris_SEK": round((2857+1512) * EUR_SEK)},
        {"Namn": "2x32 kWh",    "Kapacitet_kWh": 64.30,  "Max_kW": 15.0, "Pris_SEK": round(2857 * 2 * EUR_SEK)},
        {"Namn": "2x32+16 kWh", "Kapacitet_kWh": 80.40,  "Max_kW": 15.0, "Pris_SEK": round((2857*2+1512) * EUR_SEK)},
        {"Namn": "3x32 kWh",    "Kapacitet_kWh": 96.45,  "Max_kW": 15.0, "Pris_SEK": round(2857 * 3 * EUR_SEK)},
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
    bat_install = st.number_input(t("battery_install"), value=10000, min_value=0, step=1000,
                                   help="Samma kostnad oavsett batteristorlek")
with col_i2:
    if use_solar:
        sol_price = st.number_input(t("solar_material"), value=48000, min_value=0, step=5000,
                                    help="Paneler (~28,000 för 35st à 800kr) + inverter (~12,000) + montage/kabel (~8,000). Sätt 0 om redan installerat.")
        sol_install = st.number_input(t("solar_install"), value=0, min_value=0, step=5000,
                                      help="0 om du installerar själv")
    else:
        sol_price = 0
        sol_install = 0
with col_i3:
    finance = st.radio(t("financing"), [t("own_capital"), t("mortgage"), t("other_loan")])
    if finance == t("mortgage"):
        loan_rate = st.number_input(t("mortgage_rate"), value=3.0, min_value=0.0, max_value=10.0, step=0.25)
        loan_years = st.number_input(t("loan_term"), value=50, min_value=1, max_value=100, step=5)
        st.caption("Investeringen läggs på bolånet")
    elif finance == t("other_loan"):
        loan_rate = st.number_input(t("interest_rate"), value=5.0, min_value=0.0, step=0.5)
        loan_years = st.number_input(t("loan_years"), value=10, min_value=1, step=1)
        st.caption("Lånekostnaden visas i kassaflödesdiagrammet")
    else:
        loan_rate = 0
        loan_years = 0

sol_invest_total = sol_price + sol_install

# ================================================================
# STEP 4: SIMULATE ALL SIZES — find optimal battery
# ================================================================
# THE CORE OF THE APP. When the user clicks "KÖR SIMULERING":
#
# For EACH battery size in the price table:
#   For EACH tariff type the grid operator offers:
#     → Run the full simulation (batteri.py simulate())
#     → This goes day by day through all the price data:
#       1. Look at today's 24 hourly prices
#       2. Find the cheapest hours → charge the battery
#       3. Find the most expensive hours → discharge the battery
#       4. Solar charges the battery for free (priority over grid)
#       5. Flex loads absorb remaining solar surplus
#       6. Calculate cost savings vs grid-only scenario
#     → Also estimate effekttariff savings (peak shaving)
#   Pick the tariff that gives the highest annual profit.
#
# Result: a ranked list of all battery sizes with their ROI, payback time,
# and lifetime profit. The best one becomes the recommendation.
#
# The results are stored in st.session_state so they survive page refreshes
# and can be viewed in the detail section below.
# ================================================================
st.divider()
st.header(t("step4_header"))
st.caption(t("step4_caption"))

def _estimate_effekt_savings(result, eff_tariff, cfg, num_days):
    """Estimate annual savings from peak demand reduction with effekttariff.

    Compares peak demand WITH battery (discharge reduces grid draw)
    vs WITHOUT battery (raw household load).

    WHAT IS EFFEKTTARIFF?
    Some grid operators (Ellevio, SEOM, Göteborg Energi) charge you based on
    your PEAK power demand each month — not just total kWh. If your house
    draws 15 kW for one hour (e.g., EV + heating + cooking), you pay for
    that peak all month. A battery can discharge during high-demand hours
    to reduce the peak the grid sees. This can save 400-900 kr/month.

    The measurement varies by operator: Ellevio uses top-3 peaks from
    different days, SEOM uses a single peak, etc.
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

        month = int(ym.split("-")[1])
        rate = eff_tariff.get_effekt_rate(month) if hasattr(eff_tariff, 'get_effekt_rate') else eff_tariff.effekt_rate
        saving = (avg_without - avg_with) * rate
        total_saving += max(0, saving)

    years = num_days / 365.25
    return total_saving / years if years > 0 else 0


if st.button(t("run_simulation"), type="primary", use_container_width=True):
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

    # Determine fuse sizes to sweep (down + user's selection + larger)
    # Minimum fuse: must handle household peak load (base + all scheduled loads running)
    _peak_load_kw = base_load + sum(l.power_kw for l in scheduled_loads)
    _min_fuse_amps = _peak_load_kw / (0.23 * phases) if phases > 0 else 16
    _op_fuse_fees = get_operator_fuse_fees(grid_operator)
    _available_fuses = sorted(_op_fuse_fees.keys())
    # Only include smaller fuses that can still handle household peak load
    _smaller = [f for f in _available_fuses if f < fuse_amps and f >= _min_fuse_amps][-1:]
    _larger = [f for f in _available_fuses if f > fuse_amps][:3]
    _fuses_to_sweep = _smaller + [f for f in _available_fuses if f == fuse_amps] + _larger
    _base_fuse_fee_yr = _op_fuse_fees.get(fuse_amps, 0)

    def _build_tariffs_for_fuse(f_amps):
        """Build tariffs for a given fuse size, applying user overrides."""
        tariffs = create_tariffs_for_operator(grid_operator, f_amps, energy_tax)
        for _tf in tariffs:
            if isinstance(_tf, Tidstariff):
                _tf.peak = peak_rate
                _tf.offpeak = offpeak_rate
            elif isinstance(_tf, FastTariff):
                _tf.flat_rate = flat_rate
            elif isinstance(_tf, EffektTariff) and has_effekt:
                _tf.effekt_rate = effekt_rate
                _tf.energy_rate = effekt_energy
                _tf.top_n_peaks = effekt_top_n
        if not tariffs:
            tariffs = [
                Tidstariff(peak=peak_rate, offpeak=offpeak_rate, energy_tax=energy_tax, fuse_amps=f_amps),
                FastTariff(flat_rate=flat_rate, energy_tax=energy_tax, fuse_amps=f_amps),
            ]
        return tariffs

    price_rows = df_prices.to_dict("records")

    # Simulate ALL battery sizes × tariffs × fuse sizes
    _all_raw_results = []
    _n_tariffs = len(_build_tariffs_for_fuse(fuse_amps))
    with st.spinner(f"Simulerar {len(valid_rows)} batteristorlekar × {_n_tariffs} tariffer × {len(_fuses_to_sweep)} säkringar..."):
      for _fuse in _fuses_to_sweep:
        _fuse_tariffs = _build_tariffs_for_fuse(_fuse)
        _fuse_fee_delta_yr = _op_fuse_fees.get(_fuse, 0) - _base_fuse_fee_yr

        for _, row in valid_rows.iterrows():
            label = row["Namn"]
            cap = row["Kapacitet_kWh"]
            max_kw = row["Max_kW"]
            bat_cost = row["Pris_SEK"]

            cfg = BatteryConfig(
                capacity_kwh=cap, max_charge_kw=max_kw, max_discharge_kw=max_kw,
                efficiency=efficiency, fuse_amps=_fuse, phases=phases,
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

            for _tf in _fuse_tariffs:
                r = simulate(price_rows, cfg, tariff=_tf, solar=solar_config)
                d = len(set(s.date for s in r.slots))
                if d == 0:
                    continue
                p = r.net_profit_sek / d * 365.25

                # For effekttariff: estimate demand charge savings from battery
                eff_save = 0
                if isinstance(_tf, EffektTariff):
                    eff_save = _estimate_effekt_savings(r, _tf, cfg, d)
                    p += eff_save

                if p > best_profit:
                    best_profit = p
                    result = r
                    tariff = _tf
                    best_tariff = _tf.name
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
            net_benefit_yr = total_benefit_yr - _fuse_fee_delta_yr
            invest = bat_cost + bat_install
            total_invest = invest + sol_invest_total
            cycles_yr = result.num_cycles / (num_days / 365.25) if num_days > 0 else 0
            lifetime = min(cycle_life / cycles_yr if cycles_yr > 0 else 15, 15)
            payback = total_invest / net_benefit_yr if net_benefit_yr > 0 else 999
            profit_life = net_benefit_yr * lifetime - total_invest

            # Track grid export for self-consumption optimization
            _yrs = num_days / 365.25 if num_days > 0 else 1
            grid_export_yr = result.total_grid_export_kwh / _yrs

            # Track luft-luft flex contribution (from solar surplus)
            _aa_flex_kwh = 0
            if st.session_state.get("use_aa", False):
                for s in result.slots:
                    month = int(s.date.split("-")[1])
                    # Luft-luft flex loads are active Mar-May, Jun-Aug, Sep-Oct
                    if month in (3, 4, 5, 6, 7, 8, 9, 10) and s.flex_consumed_kwh > 0:
                        _aa_flex_kwh += s.flex_consumed_kwh

            _all_raw_results.append({
                "label": label, "capacity": cap, "max_kw": max_kw,
                "bat_cost": bat_cost, "invest": invest, "total_invest": total_invest,
                "arb_yr": arb_yr, "solar_self_yr": solar_self_yr,
                "total_benefit_yr": total_benefit_yr,
                "net_benefit_yr": net_benefit_yr,
                "fuse_amps": _fuse, "fuse_fee_yr": _op_fuse_fees.get(_fuse, 0),
                "fuse_fee_delta_yr": _fuse_fee_delta_yr,
                "payback": payback, "profit_life": profit_life,
                "cycles_yr": cycles_yr, "lifetime": lifetime,
                "best_tariff": best_tariff,
                "result": result, "config": cfg, "tariff": tariff,
                "num_days": num_days,
                "grid_export_yr": grid_export_yr,
                "aa_flex_kwh_yr": _aa_flex_kwh / _yrs if st.session_state.get("use_aa") else 0,
                "total_flex_kwh_yr": result.total_flex_consumed_kwh / _yrs,
            })

    # Keep best fuse per battery label (dedup across fuse sweep)
    _fuse_variants = {}  # label -> list of results (for fuse comparison display)
    _best_per_label = {}
    for r in _all_raw_results:
        lbl = r["label"]
        _fuse_variants.setdefault(lbl, []).append(r)
        if lbl not in _best_per_label or r["profit_life"] > _best_per_label[lbl]["profit_life"]:
            _best_per_label[lbl] = r
    all_results = sorted(_best_per_label.values(), key=lambda r: r["capacity"])

    st.session_state["all_results"] = all_results
    st.session_state["solar_cfg"] = solar_config
    st.session_state["price_rows"] = price_rows
    st.session_state["fuse_variants"] = _fuse_variants
    # Store a reference config for volatility section
    st.session_state["shared_config"] = all_results[0]["config"] if all_results else None

# ================================================================
# RESULTS — show comparison and recommendation
# ================================================================
# Everything below here displays the simulation results.
# The sections are:
#   - RECOMMENDATION: the single best battery + tariff combo
#   - SELF-CONSUMPTION (SEK/kWh mode): smallest battery for zero grid export
#   - LUFT-LUFT CONTRIBUTION: air-to-air HP solar surplus absorption (bonus, not in main ROI)
#   - PDF REPORT: downloadable bank-grade report with methodology
#   - SCENARIO SPLIT: results broken down by year (normal vs high-price years)
#   - COMPARISON: annualized cost vs savings bar chart for all sizes
#   - CUMULATIVE CASHFLOW: 15-year investment curve
#   - FINANCING: monthly cashflow if financed via mortgage/loan
#   - FUSE COMPARISON: "should I upgrade my fuse?"
#   - DETAIL VIEW: monthly breakdown for selected battery
#   - FUTURE SCENARIOS: what happens if price volatility increases?
if "all_results" in st.session_state:
    all_results = st.session_state["all_results"]
    solar_cfg = st.session_state.get("solar_cfg")
    price_rows = st.session_state.get("price_rows", [])

    if not all_results:
        st.warning(t("no_results"))
        st.stop()

    # === RECOMMENDATION ===
    best_idx = max(range(len(all_results)), key=lambda i: all_results[i]["profit_life"])
    best = all_results[best_idx]

    _rec_fuse = best.get("fuse_amps", fuse_amps)
    if _rec_fuse > fuse_amps:
        _rec_fuse_label = f" + uppgradera till {_rec_fuse:.0f}A"
    elif _rec_fuse < fuse_amps:
        _rec_fuse_label = f" + nedgradera till {_rec_fuse:.0f}A"
    else:
        _rec_fuse_label = ""
    _rec_benefit = best["net_benefit_yr"]
    st.success(
        f"**Rekommendation: {best['label']}{_rec_fuse_label}** — "
        f"lägre elkostnad {_rec_benefit:,.0f} kr/år ({_rec_benefit/12:,.0f} kr/mån), "
        f"investering {best['total_invest']:,.0f} kr, "
        f"återbetald på {best['payback']:.1f} år, "
        f"netto {best['profit_life']:,.0f} kr under {best['lifetime']:.0f} år"
    )
    if _rec_fuse != fuse_amps:
        _fv = st.session_state.get("fuse_variants", {}).get(best["label"], [])
        _current_fuse_result = next((r for r in _fv if r["fuse_amps"] == fuse_amps), None)
        _extra_benefit = best["net_benefit_yr"] - _current_fuse_result["net_benefit_yr"] if _current_fuse_result else best["fuse_fee_delta_yr"]
        _change_word = "Uppgradering" if _rec_fuse > fuse_amps else "Nedgradering"
        st.info(
            f"Säkring: {_change_word} {fuse_amps:.0f}A → {_rec_fuse:.0f}A: "
            f"abonnemang {best['fuse_fee_delta_yr']:+,.0f} kr/år, "
            f"netto {_extra_benefit:+,.0f} kr/år bättre än nuvarande säkring"
        )

    # Tariff recommendation (from best size)
    st.info(f"Bästa tariff: **{best['best_tariff']}**")

    # Self-consumption optimization (when using SEK/kWh mode)
    if st.session_state.get("pricing_mode", "") == t("sek_per_kwh_mode"):
        # Find smallest battery where grid export is near zero
        _sorted_by_cap = sorted(all_results, key=lambda r: r["capacity"])
        _zero_export = None
        for r in _sorted_by_cap:
            if r["grid_export_yr"] < 10:  # less than 10 kWh/yr = effectively zero
                _zero_export = r
                break
        if _zero_export:
            st.success(
                f"**Maximal egenförbrukning: {_zero_export['label']}** — "
                f"nära noll export ({_zero_export['grid_export_yr']:.0f} kWh/år till nät), "
                f"investering {_zero_export['total_invest']:,.0f} kr, "
                f"lägre elkostnad {_zero_export['net_benefit_yr']:,.0f} kr/år"
            )
        else:
            _min_export = min(all_results, key=lambda r: r["grid_export_yr"])
            st.info(
                f"**Lägst export: {_min_export['label']}** — "
                f"{_min_export['grid_export_yr']:.0f} kWh/år exporteras fortfarande till nät. "
                f"Investering {_min_export['total_invest']:,.0f} kr. "
                f"Överväg större batteri eller fler flexibla laster för att nå noll export."
            )

        # Show export vs battery size chart
        _cap_list = [r["capacity"] for r in _sorted_by_cap]
        _export_list = [r["grid_export_yr"] for r in _sorted_by_cap]
        _benefit_list = [r["net_benefit_yr"] for r in _sorted_by_cap]
        fig_self = go.Figure()
        fig_self.add_trace(go.Bar(x=_cap_list, y=_export_list, name="Export till nät (kWh/år)",
                                   marker_color="indianred"))
        fig_self.add_trace(go.Scatter(x=_cap_list, y=_benefit_list, name="Lägre elkostnad (kr/år)",
                                       yaxis="y2", mode="lines+markers", marker_color="seagreen"))
        fig_self.update_layout(
            title="Egenförbrukning vs batteristorlek",
            xaxis_title="Batterikapacitet (kWh)",
            yaxis_title="Export till nät (kWh/år)",
            yaxis2=dict(title="Lägre elkostnad (kr/år)", overlaying="y", side="right"),
            height=400,
        )
        st.plotly_chart(fig_self, use_container_width=True)

    # === LUFT-LUFT CONTRIBUTION (separate from main investment) ===
    if st.session_state.get("use_aa", False) and best.get("aa_flex_kwh_yr", 0) > 0:
        with st.expander("Luft-luft bidrag (utanför huvudinvesteringen)", expanded=False):
            _aa_flex = best["aa_flex_kwh_yr"]
            _total_flex = best["total_flex_kwh_yr"]
            _other_flex = _total_flex - _aa_flex
            _avg_ore = 60  # approximate average price
            _aa_value_kr = _aa_flex * _avg_ore / 100

            col_aaf1, col_aaf2, col_aaf3 = st.columns(3)
            with col_aaf1:
                st.metric("Luft-luft solöverskott", f"{_aa_flex:,.0f} kWh/år",
                          help="Solöverskott som luft-luft absorberar genom "
                               "förvärme/förkylning av huset (termisk lagring)")
            with col_aaf2:
                st.metric("Undviken export", f"{_aa_value_kr:,.0f} kr/år",
                          help="Värdet av att använda solöverskottet i huset "
                               "istället för att exportera till nät (~60 öre/kWh)")
            with col_aaf3:
                st.metric("Övriga flex-laster", f"{_other_flex:,.0f} kWh/år",
                          help="Poolpump, varmvatten etc. — separat från luft-luft")

            st.caption(
                f"Luft-luft absorberar {_aa_flex:,.0f} kWh/år solöverskott "
                f"av totalt {_total_flex:,.0f} kWh/år flex-förbrukning. "
                f"Detta är inte inräknat i huvudinvesteringens lönsamhet ovan — "
                f"det är en bonus som minskar exportförluster."
            )

    # === PDF REPORT ===
    # Calculate financing for report
    _report_loan_cost = 0
    _report_net = best["net_benefit_yr"] / 12
    if loan_rate > 0 and loan_years > 0:
        _mr = loan_rate / 100 / 12
        _np = loan_years * 12
        _report_loan_cost = best["total_invest"] * _mr / (1 - (1 + _mr) ** -_np) if _mr > 0 else best["total_invest"] / _np
        _report_net = best["net_benefit_yr"] / 12 - _report_loan_cost

    # Gather scenario data if available (computed below, but we can peek at price_rows)
    _normal_yrs = []
    _high_yrs = []
    _normal_save = 0
    _high_save = 0

    try:
        _th = st.session_state.get("tibber_home", {})
        if _th.get("address") and _th.get("city"):
            _pdf_address = f"{_th['address']}, {_th['city']}"
        elif 'selected_city' in dir():
            _pdf_address = selected_city
        else:
            _pdf_address = ""
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
        fuse_amps=best.get("fuse_amps", fuse_amps),
        solar_kwp=solar_kwp if use_solar else 0,
        battery_label=best["label"],
        battery_capacity=best["capacity"],
        battery_price=best["bat_cost"],
        installation_cost=bat_install,
        solar_price=sol_price if use_solar else 0,
        solar_install=sol_install if use_solar else 0,
        total_investment=best["total_invest"],
        savings_per_year=best["net_benefit_yr"],
        savings_per_month=best["net_benefit_yr"] / 12,
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
        all_results=[{"label": r["label"], "total_benefit_yr": r["net_benefit_yr"],
                       "total_invest": r["total_invest"], "payback": r["payback"],
                       "profit_life": r["profit_life"]} for r in all_results],
        future_scenarios=st.session_state.get("scenario_results"),
    )
        st.download_button(
            t("download_pdf"),
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
            row["all"] = r["net_benefit_yr"]
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
            st.subheader(t("scenario_header"))
            st.caption(t("scenario_caption"))

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

    # === COMPARISON: annualized cost vs annualized savings ===
    labels = [r["label"] for r in all_results]
    st.subheader(t("compare_all_header"))
    st.caption(t("compare_all_caption"))

    fig_annual = go.Figure()
    fig_annual.add_trace(go.Bar(
        x=labels,
        y=[r["total_invest"] / r["lifetime"] for r in all_results],
        name="Investeringskostnad per år",
        marker_color="#e74c3c",
        hovertemplate="%{x}<br>Kostnad: %{y:,.0f} kr/år<extra></extra>",
    ))
    fig_annual.add_trace(go.Bar(
        x=labels,
        y=[r["net_benefit_yr"] for r in all_results],
        name="Lägre elkostnad per år",
        marker_color="#2ecc71",
        hovertemplate="%{x}<br>Besparing: %{y:,.0f} kr/år<extra></extra>",
    ))
    fig_annual.update_layout(barmode="group", yaxis_title="kr/år", height=350,
                              margin=dict(l=0, r=0, t=30, b=0),
                              legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig_annual, use_container_width=True)

    # === COMPARISON TABLE ===
    def _fuse_label(r):
        f = r.get("fuse_amps", fuse_amps)
        return f" ({f:.0f}A)" if f != fuse_amps else ""
    st.dataframe(pd.DataFrame([{
        "Batteri": r["label"] + _fuse_label(r),
        "Besparing/år": f"{r['net_benefit_yr']:,.0f} kr",
        "Kostnad/år": f"{r['total_invest'] / r['lifetime']:,.0f} kr",
        "Netto/år": f"{r['net_benefit_yr'] - r['total_invest'] / r['lifetime']:,.0f} kr",
        "Netto/mån": f"{(r['net_benefit_yr'] - r['total_invest'] / r['lifetime']) / 12:,.0f} kr",
        "Investering": f"{r['total_invest']:,.0f} kr",
        "Livslängd": f"{r['lifetime']:.0f} år",
        "Tariff": r["best_tariff"],
    } for r in all_results]), use_container_width=True, hide_index=True)

    # === CUMULATIVE CASHFLOW OVER TIME (top 3 only) ===
    # Show smallest, recommended, and largest to keep chart readable
    if len(all_results) > 3:
        _sorted = sorted(all_results, key=lambda r: r["capacity"])
        _picks = [_sorted[0], best, _sorted[-1]]
        # Deduplicate
        _seen = set()
        _show = [r for r in _picks if r["label"] not in _seen and not _seen.add(r["label"])]
    else:
        _show = all_results

    fig_life = go.Figure()
    colors = ["#3498db", "#2ecc71", "#e74c3c"]
    years = list(range(0, 16))
    for i, r in enumerate(_show):
        cum = [-r["total_invest"]]
        for yr in range(1, 16):
            cum.append(cum[-1] + r["net_benefit_yr"])
        is_best = r["label"] == best["label"]
        fig_life.add_trace(go.Scatter(
            x=years, y=cum, mode="lines+markers", name=r["label"],
            line=dict(width=4 if is_best else 2, color=colors[i % len(colors)]),
            hovertemplate=f"{r['label']}<br>År %{{x}}: %{{y:,.0f}} kr<extra></extra>",
        ))
    fig_life.add_hline(y=0, line_color="gray", line_width=1,
                        annotation_text="Återbetald", annotation_position="bottom right")
    fig_life.update_layout(
        xaxis_title="År", yaxis_title="Ackumulerat kassaflöde (SEK)", height=400,
        margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02),
    )
    st.plotly_chart(fig_life, use_container_width=True)

    # === FINANCING PERSPECTIVE ===
    st.divider()
    st.subheader(t("financing_header"))

    if finance in (t("mortgage"), t("other_loan")) and loan_rate > 0 and loan_years > 0:
        loan_label = t("mortgage") if finance == t("mortgage") else "Lån"
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
            m_saving = r["net_benefit_yr"] / 12
            net = m_saving - m_cost
            # True lifetime profit: savings during battery life - loan payments during same period
            lifetime = r["lifetime"]
            total_savings_life = r["net_benefit_yr"] * lifetime
            total_loan_life = m_cost * 12 * lifetime
            net_lifetime = total_savings_life - total_loan_life
            fin_data.append({"label": r["label"], "total": total,
                             "monthly_cost": m_cost, "monthly_saving": m_saving,
                             "net": net, "net_lifetime": net_lifetime,
                             "lifetime": lifetime})

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
            "Investering": f"{d['total']:,.0f} kr",
            f"{loan_label}/mån": f"{d['monthly_cost']:,.0f} kr",
            "Besparing/mån": f"{d['monthly_saving']:,.0f} kr",
            "Kassaflöde/mån": f"{d['net']:+,.0f} kr",
            "Livslängd": f"{d['lifetime']:.0f} år",
            "Netto livslängd": f"{d['net_lifetime']:+,.0f} kr",
        } for d in fin_data]), use_container_width=True, hide_index=True)

        best_fin = max(fin_data, key=lambda d: d["net_lifetime"])
        profitable = [d for d in fin_data if d["net_lifetime"] > 0]
        if len(profitable) == len(fin_data):
            st.success(f"**Alla storlekar lönsamma under batteriets livslängd.** "
                       f"Bäst: **{best_fin['label']}** — "
                       f"+{best_fin['net']:,.0f} kr/mån kassaflöde, "
                       f"+{best_fin['net_lifetime']:,.0f} kr netto under {best_fin['lifetime']:.0f} år.")
        elif profitable:
            st.info(f"**{best_fin['label']}** ger bäst resultat: "
                    f"+{best_fin['net']:,.0f} kr/mån kassaflöde, "
                    f"+{best_fin['net_lifetime']:,.0f} kr netto under {best_fin['lifetime']:.0f} år.")
        else:
            st.warning("Ingen storlek ger positivt netto under batteriets livslängd med dessa lånvillkor.")
    else:
        # Eget kapital — show simple cashflow over time for recommended battery
        st.caption("Kontant betalning — ackumulerat kassaflöde per batteristorlek")

        fig_cf = go.Figure()
        colors = ["#3498db", "#2ecc71", "#e74c3c", "#9b59b6", "#f39c12", "#1abc9c"]
        for i, r in enumerate(all_results):
            years = list(range(0, 16))
            cf = [-r["total_invest"]]
            for y in range(1, 16):
                cf.append(cf[-1] + r["net_benefit_yr"])
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
    # FUSE COMPARISON — show pre-computed fuse variants for recommended battery
    # The main optimization already swept fuse sizes and picked the best.
    # This section shows the full comparison for transparency.
    _fuse_variants_display = st.session_state.get("fuse_variants", {}).get(best["label"], [])
    _fuse_variants_display = sorted(_fuse_variants_display, key=lambda r: r["fuse_amps"])
    if len(_fuse_variants_display) > 1 and best:
        st.divider()
        st.subheader(t("fuse_header"))
        _base_fee = get_operator_fuse_fees(grid_operator).get(fuse_amps, 0)
        st.caption(f"Säkringsstorleken påverkar laddkapacitet och abonnemangskostnad. "
                   f"Din nuvarande: {fuse_amps:.0f}A ({_base_fee:,.0f} kr/år). "
                   f"Resultat för rekommenderat batteri ({best['label']}).")

        fuse_comparison = []
        for fv in _fuse_variants_display:
            is_current = fv["fuse_amps"] == fuse_amps
            is_optimal = fv["fuse_amps"] == best.get("fuse_amps", fuse_amps)
            fuse_comparison.append({
                "fuse": fv["fuse_amps"],
                "fee_yr": fv["fuse_fee_yr"],
                "benefit_yr": fv["total_benefit_yr"],  # gross savings
                "extra_fee_yr": fv["fuse_fee_delta_yr"],
                "net_yr": fv["net_benefit_yr"],
                "current": is_current,
                "optimal": is_optimal,
            })

        # Chart
        fig_fuse = go.Figure()
        fuse_labels = [f"{fc['fuse']:.0f}A" + (" (nu)" if fc["current"] else "") + (" ★" if fc["optimal"] and not fc["current"] else "") for fc in fuse_comparison]
        fig_fuse.add_trace(go.Bar(
            x=fuse_labels,
            y=[fc["net_yr"] for fc in fuse_comparison],
            name="Netto besparing (kr/år)",
            marker_color=["#2ecc71" if fc["optimal"] else "#3498db" for fc in fuse_comparison],
            hovertemplate="%{x}<br>Netto: %{y:,.0f} kr/år<extra></extra>",
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
        _current_net = next((fc["net_yr"] for fc in fuse_comparison if fc["current"]), 0)
        st.dataframe(pd.DataFrame([{
            "Säkring": f"{fc['fuse']:.0f}A" + (" (nuvarande)" if fc["current"] else "") + (" ★ optimal" if fc["optimal"] and not fc["current"] else ""),
            "Abonnemang": f"{fc['fee_yr']:,.0f} kr/år",
            "Brutto besparing": f"{fc['benefit_yr']:,.0f} kr/år",
            "Extra abonnemang": f"{fc.get('extra_fee_yr', 0):+,.0f} kr/år" if not fc["current"] else "—",
            "Netto": f"{fc['net_yr']:,.0f} kr/år ({fc['net_yr']/12:,.0f} kr/mån)",
            "vs nuvarande": f"{fc['net_yr'] - _current_net:+,.0f} kr/år" if not fc["current"] else "—",
        } for fc in fuse_comparison]), use_container_width=True, hide_index=True)

        # Recommendation
        best_fuse = max(fuse_comparison, key=lambda fc: fc["net_yr"])
        if not best_fuse["current"]:
            extra = best_fuse["net_yr"] - _current_net
            st.success(f"**{best_fuse['fuse']:.0f}A ger bäst netto** — "
                       f"{extra:+,.0f} kr/år mer än {fuse_amps:.0f}A "
                       f"(extra avgift {best_fuse.get('extra_fee_yr', 0):+,.0f} kr/år)")
        else:
            upgrades = [fc for fc in fuse_comparison if not fc["current"]]
            if upgrades:
                next_up = upgrades[0]
                st.info(f"**{fuse_amps:.0f}A ger bäst netto för batteriet.** "
                        f"Uppgradering till {next_up['fuse']:.0f}A kostar "
                        f"{next_up.get('extra_fee_yr', 0):,.0f} kr/år mer.")

    # ================================================================
    # STEP 5: DEEP-DIVE — detail view for selected battery
    # ================================================================
    # Shows a monthly breakdown of the selected battery's performance:
    #   - Green bars: money saved by discharging (avoided expensive grid purchases)
    #   - Blue bars: revenue from selling surplus solar to the grid
    #   - Red bars: cost of charging from the grid (bought at cheap hours)
    #   - Black line: net savings per month
    # Summer months typically show more solar income, winter more arbitrage.
    st.divider()
    st.header(t("step5_header"))

    detail_labels = [r["label"] for r in all_results]
    default_idx = best_idx if best_idx < len(detail_labels) else 0
    selected_label = st.selectbox(t("show_details_for"), detail_labels, index=default_idx)
    sel = next(r for r in all_results if r["label"] == selected_label)

    result = sel["result"]
    config = sel["config"]
    tariff = sel["tariff"]
    num_days = sel["num_days"]
    per_year = sel["net_benefit_yr"]

    col_d1, col_d2, col_d3, col_d4 = st.columns(4)
    col_d1.metric(t("lower_cost"), f"{per_year/12:,.0f} kr/mån")
    col_d2.metric(t("per_year"), f"{per_year:,.0f} kr/år")
    col_d3.metric(t("payback"), f"{sel['payback']:.1f} år")
    col_d4.metric(t("cycles_yr"), f"{sel['cycles_yr']:.0f}")

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
    st.subheader(t("typical_year"))

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
            "Sålt till nät (kr)": f"{r['export_rev']:,.0f}",
            "Sol→batteri (kWh)": f"{r['solar_charged']:,.0f}",
            "Netto besparing (kr)": f"{r['net']:,.0f}",
        } for r in monthly_detail]), use_container_width=True, hide_index=True)

    # ================================================================
    # STEP 6: FUTURE SCENARIOS
    # ================================================================
    # The battery's profitability depends on price VOLATILITY (how much prices
    # swing between cheap and expensive hours), not on the average price level.
    # More wind/solar in the grid → more volatility → better for batteries.
    #
    # This section scales the historical price data to simulate three futures:
    #   - Conservative (1.5x): modest increase in price swings
    #   - Likely (2.5x): what most energy analysts expect in 10 years
    #   - High volatility (4.0x): aggressive renewable buildout scenario
    #
    # The scaling preserves the daily average price but amplifies the spread
    # between cheap and expensive hours. The volatility increases linearly
    # over 10 years (year 1 = current, year 10 = target level).
    # ================================================================
    st.divider()
    st.header(t("step6_header"))
    st.caption(t("step6_caption"))

    def scale_vol(rows, factor):
        """Scale price volatility while keeping the daily average unchanged.

        Example with factor=2.0 and daily average 1.00 kr:
          Hour at 0.50 kr → 1.00 + (0.50 - 1.00) × 2.0 = 0.00 → clamped to 0.001
          Hour at 1.50 kr → 1.00 + (1.50 - 1.00) × 2.0 = 2.00

        The spread doubled (from 1.00 to 2.00), but the average stayed ~1.00.
        This is what happens when more wind/solar enters the grid:
        sunny/windy hours get cheaper, calm/dark hours get more expensive.
        """
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

    # Three scenarios for the recommended battery
    scenarios = [
        (t("conservative"), 1.5, t("conservative_desc")),
        (t("likely"), 2.5, t("likely_desc")),
        (t("high_volatility"), 4.0, t("high_volatility_desc")),
    ]
    vol_levels = [1.0, 1.5, 2.5]

    ref_cfg = st.session_state.get("shared_config") or all_results[0]["config"]
    ref_tariff = best["tariff"]
    bl = best["label"]
    bp = round(best["bat_cost"])
    inv = best["total_invest"]

    with st.spinner("Beräknar framtidsscenarier..."):
        scenario_results = {}
        for label, vf, desc in scenarios:
            scaled = scale_vol(price_rows, vf)
            fc_cfg = BatteryConfig(
                capacity_kwh=best["capacity"], max_charge_kw=best["max_kw"],
                max_discharge_kw=best["max_kw"],
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
            scenario_results[label] = {"arb_yr": ay, "vol": vf, "desc": desc}

    # Summary metrics
    col_s1, col_s2, col_s3 = st.columns(3)
    for col, (label, vf, desc) in zip([col_s1, col_s2, col_s3], scenarios):
        sr = scenario_results[label]
        lifetime_profit = sr["arb_yr"] * best["lifetime"] - inv
        col.metric(label, f"{sr['arb_yr']:,.0f} kr/år",
                    delta=f"Netto {lifetime_profit:+,.0f} kr under {best['lifetime']:.0f} år")
        col.caption(desc)

    # 15-year cumulative cashflow for each scenario
    st.subheader(f"15-årsprognos — {best['label']}")
    st.caption("Ackumulerat kassaflöde under batteriets livslängd i tre scenarier. "
               "Volatiliteten ökar linjärt till målnivå under de första 10 åren.")

    fig_15 = go.Figure()
    scenario_colors = {t("conservative"): "#3498db", t("likely"): "#2ecc71", t("high_volatility"): "#e74c3c"}

    # Also compute results at intermediate levels for smooth interpolation
    all_vol_levels = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
    vol_arb = {}
    with st.spinner("Beräknar 15-årskurvor..."):
        for vf in all_vol_levels:
            if vf in [s[1] for s in scenarios]:
                # Already computed
                for label, svf, _ in scenarios:
                    if svf == vf:
                        vol_arb[vf] = scenario_results[label]["arb_yr"]
            else:
                scaled = scale_vol(price_rows, vf)
                fc_cfg = BatteryConfig(
                    capacity_kwh=best["capacity"], max_charge_kw=best["max_kw"],
                    max_discharge_kw=best["max_kw"],
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
                vol_arb[vf] = r.net_profit_sek / d * 365.25 if d > 0 else 0

    for label, target_vol, desc in scenarios:
        cum = [-inv]
        for yr in range(1, 16):
            vol = 1.0 + (target_vol - 1.0) * min(yr, 10) / 10
            # Interpolate from precomputed volatility levels
            below = [v for v in all_vol_levels if v <= vol]
            above = [v for v in all_vol_levels if v > vol]
            if below and above:
                b, a = below[-1], above[0]
                _frac = (vol - b) / (a - b)
                yr_profit = vol_arb[b] * (1-_frac) + vol_arb[a] * _frac
            elif below:
                yr_profit = vol_arb[below[-1]]
            else:
                yr_profit = vol_arb[all_vol_levels[0]]
            cum.append(cum[-1] + yr_profit)

        fig_15.add_trace(go.Scatter(
            x=list(range(16)), y=cum, mode="lines",
            name=label, line=dict(width=3, color=scenario_colors[label]),
            hovertemplate=f"{label}<br>År %{{x}}: %{{y:,.0f}} kr<extra></extra>",
        ))

    fig_15.add_hline(y=0, line_color="gray", line_width=1,
                      annotation_text="Återbetald", annotation_position="bottom right")
    fig_15.update_layout(xaxis_title="År", yaxis_title="Ackumulerat kassaflöde (SEK)", height=400,
                          margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig_15, use_container_width=True)

    # Summary table
    st.dataframe(pd.DataFrame([{
        "Scenario": label,
        "Volatilitet": f"{vf:.0%}x om 10 år",
        "Besparing/år": f"{scenario_results[label]['arb_yr']:,.0f} kr",
        "Besparing/mån": f"{scenario_results[label]['arb_yr']/12:,.0f} kr",
        "Netto 15 år": f"{scenario_results[label]['arb_yr'] * best['lifetime'] - inv:+,.0f} kr",
    } for label, vf, desc in scenarios]), use_container_width=True, hide_index=True)

    # Store scenario data for PDF report
    st.session_state["scenario_results"] = {
        label: {"arb_yr": scenario_results[label]["arb_yr"],
                "vol": vf, "desc": desc,
                "lifetime_profit": scenario_results[label]["arb_yr"] * best["lifetime"] - inv}
        for label, vf, desc in scenarios
    }

    # ================================================================
    # DIY SYSTEM DESIGN — zero export, split charge/discharge
    # ================================================================
    st.divider()
    st.subheader(t("diy_header"))
    st.caption(t("diy_intro"))

    _best_cap = best["capacity"]
    _best_units = max(1, round(_best_cap / 32))
    _n_flatpacks = max(2, round(best["max_kw"] / 3))
    _flatpack_kw = _n_flatpacks * 3
    _best_fuse = best.get("fuse_amps", fuse_amps)

    # Size the discharge inverter based on household peak load (excl. EV — those charge at night)
    _house_base_kw = base_load + sum(l.power_kw for l in scheduled_loads if l.start_hour >= 7 and l.start_hour < 19)
    _inverter_kw = max(5, round(_house_base_kw / 5) * 5)  # round up to nearest 5 kW
    if _inverter_kw <= 5:
        _inverter_model = "MultiPlus-II 48/5000"
        _inverter_price = 15000
    elif _inverter_kw <= 8:
        _inverter_model = "MultiPlus-II 48/8000"
        _inverter_price = 20000
    elif _inverter_kw <= 10:
        _inverter_model = "MultiPlus-II 48/10000"
        _inverter_price = 25000
    else:
        _inverter_model = f"2× MultiPlus-II 48/5000 parallell"
        _inverter_price = 30000
        _inverter_kw = 10

    st.markdown(f"""
**Principen:** Separera laddning och urladdning i två oberoende vägar till batteriet.

**Laddväg — billig, hög effekt (grid → batteri)**
- {_n_flatpacks}× Eltek Flatpack2 HE 48V 3 kW = **{_flatpack_kw} kW laddeffekt**
- Begagnade telekomlikriktare, ~700-1 000 kr/st (Tradera/eBay)
- Monteras i standard 19" subrack (2U), spänning ställs till 54.5V
- Styrs av Shelly-relä med prisstyrning (spotpris publiceras kl 13 för nästa dygn)
- Enkel logik: sortera dygnets 24 timpriser, slå på de {max(2, int(_best_cap / _flatpack_kw) + 1)} billigaste timmarna
- Kan köras med t.ex. Home Assistant, Node-RED, eller ett Python-script på Raspberry Pi
- Alternativ: Shellys inbyggda script-motor + elprisetjustnu.se API (ingen extra hårdvara)
- BMS stänger av vid fullt batteri — ingen komplex laddlogik behövs
- Laddar {_best_cap:.0f} kWh på ~{_best_cap / _flatpack_kw:.0f} timmar

**Urladdväg — smart, nollexport (batteri → hus)**
- Victron {_inverter_model} ({_inverter_kw} kW kontinuerligt)
- Dimensionerad utifrån husets daglast (~{_house_base_kw:.0f} kW) — EV-laddning sker nattetid
- ESS-läge med **grid feed-in: OFF** → nollexport garanterat i hårdvara
- Matar husets laster under dyra timmar, kapar effekttoppar
- Cerbo GX som hjärna — läser BMS via CAN, fjärrövervakning via VRM

**Batteri**
- {_best_units}× NKON ESS Pro 32 kWh (48V, LiFePO4, Seplos 300A BMS)
- Parallellkopplade på gemensam DC-skena
- 8 000 cykler, 15 års livslängd

**Solpaneler (om monterade)**
- Befintlig nätansluten solväxelriktare behålls som den är
- MultiPlus ser solöverskott på AC-sidan och laddar batteriet automatiskt (AC-koppling)
- Ingen ombyggnad av solcellsanläggningen behövs

**Nollexport — varför?**
- Ingen mikroproducentregistrering krävs
- Inget exportavtal med elhandlare behövs
- Enklare och billigare växelriktare (behöver inte mata nätet)
- Varmvattenberedare + luft-luft VP absorberar eventuellt överskott

**Ungefärlig materialkostnad**

| Komponent | Pris |
|-----------|------|
| {_best_units}× NKON ESS Pro 32 kWh | {best['bat_cost']:,.0f} kr |
| {_n_flatpacks}× Eltek Flatpack2 + subrack | ~{_n_flatpacks * 800 + 1000:,} kr |
| Victron {_inverter_model} | ~{_inverter_price:,} kr |
| Victron Cerbo GX | ~3 000 kr |
| Shelly Pro relä | ~500 kr |
| DC-skena, kablage, brytare | ~2 000 kr |
| **Totalt material** | **~{best['bat_cost'] + _n_flatpacks * 800 + 1000 + _inverter_price + 3000 + 500 + 2000:,.0f} kr** |
""")

    st.info(
        "Detta är en principskiss — inte en installationsguide. "
        "Kontakta en behörig elektriker för inkoppling till elnätet."
    )
