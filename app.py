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
import json
import math
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
from economics import solar_direct_use, effekt_savings, baseline_export_revenue, loan_schedule
from app_state import save_state, load_state
from translations import t, set_language, get_language, STRINGS

st.set_page_config(page_title="Energikalkyl", page_icon="⚡", layout="wide")

# Language selector — placed before everything else so all text respects the choice.
# Stored in session_state so it survives Streamlit reruns.
_lang_options = {"Svenska": "sv", "English": "en"}
_lang_display = list(_lang_options.keys())
_saved_lang = st.session_state.get("app_language", "sv")
_lang_default = 0 if _saved_lang == "sv" else 1

# Choice widgets whose option LABELS are translated (format_func) store their value as the
# formatted label in the browser, so a language switch would reset them to the default.
# Re-assigning their (language-independent) values in the on_change callback keeps them.
_LANG_STABLE_KEYS = ("price_src_key", "solar_source_key", "fuse_overcurrent", "energy_class",
                     "aa_model_key", "pricing_mode_key", "finance")


def _on_language_change():
    for _k in list(st.session_state.keys()):
        if _k in _LANG_STABLE_KEYS or str(_k).startswith("heating_type_"):
            st.session_state[_k] = st.session_state[_k]
    # The battery price table's translated column labels are part of its identity, so its
    # edits would be lost: seed the editor with the last edited table instead.
    if st.session_state.get("_bt_last") is not None:
        st.session_state["_bt_seed"] = st.session_state["_bt_last"]
        st.session_state["_bt_seed_eur"] = st.session_state.get("eur_sek_rate")
        st.session_state.pop("battery_table", None)


_selected_lang = st.selectbox(t("language"), _lang_display, index=_lang_default,
                               key="lang_select", label_visibility="collapsed",
                               on_change=_on_language_change)
st.session_state["app_language"] = _lang_options[_selected_lang]
set_language(st.session_state["app_language"])

# Restore persisted state on first load — ONLY when ENERGIKALKYL_PERSIST=1
# (single-user self-hosted/Docker). On a public deployment every visitor has
# their own st.session_state and nothing is written to or read from disk, so
# one visitor can never see another visitor's data.
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
        # The token stays in this visitor's st.session_state only and is passed explicitly
        # to every Tibber call. NEVER put it in os.environ or on disk: the process (and its
        # environment) is shared by all concurrent visitors.
        _tibber_token = _tibber_token_input.strip() or None
        # Without an entered token, tibber_source falls back to TIBBER_TOKEN /
        # .tibber_token on the server. Only allow that on a self-hosted
        # install, never on the shared public deployment.
        from app_state import persistence_enabled as _local_install
        _token_missing = _tibber_token is None and not _local_install()
        _fetch_pressed = st.button(t("fetch_data"), type="primary")
        if _fetch_pressed and _token_missing:
            st.error(t("tibber_token_required"))
        if _fetch_pressed and not _token_missing:
            with st.spinner(t("fetching_tibber")):
                try:
                    from tibber_source import (
                        fetch_consumption, consumption_to_load_profile,
                        fetch_monthly_consumption, build_seasonal_hourly_profile,
                        get_homes, fetch_production, fetch_daily_production,
                        production_to_hourly_dict, production_to_monthly_kwh,
                    )
                    # Fetch home info (address, grid company, fuse, house size, heating)
                    homes = get_homes(token=_tibber_token)
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
                            token = _tibber_token or _get_token()
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

                    nodes = fetch_consumption(hours=24*30, token=_tibber_token)
                    profile = consumption_to_load_profile(nodes)
                    st.session_state["hourly_profile"] = profile
                    monthly = fetch_monthly_consumption(months=36, token=_tibber_token)
                    if len(monthly) >= 6:
                        seasonal = build_seasonal_hourly_profile(nodes, monthly)
                        st.session_state["seasonal_profile"] = seasonal

                    # Fetch solar production data if available
                    try:
                        prod_hourly = fetch_production(hours=24*30, token=_tibber_token)
                        prod_daily = (fetch_daily_production(days=365*3, token=_tibber_token)
                                      if prod_hourly else [])
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
                        parts.append(t("tibber_grid").format(grid=home_info['grid_company']))
                    if home_info.get("fuse_size"):
                        parts.append(t("tibber_fuse").format(fuse=home_info['fuse_size']))
                    if home_info.get("house_size"):
                        parts.append(t("tibber_area").format(area=home_info['house_size']))
                    if home_info.get("heating_source"):
                        _hs_map = {"GROUND": t("heating_ground"), "AIR2AIR": t("heating_air2air"),
                                    "AIR2WATER": t("heating_air2water"), "DISTRICT": t("heating_district"),
                                    "ELECTRIC": t("heating_electric"), "OTHER": t("heating_other")}
                        parts.append(_hs_map.get(home_info["heating_source"],
                                                  home_info["heating_source"]))
                    if st.session_state.get("tibber_solar_monthly"):
                        monthly_kwh = st.session_state["tibber_solar_monthly"]
                        yearly = sum(monthly_kwh.values())
                        parts.append(t("tibber_solar_yearly").format(kwh=f"{yearly:,.0f}"))
                    st.success(" | ".join(parts))
                except Exception as e:
                    st.error(f"{t('tibber_error')}: {e}")

    # E.ON section
    with st.expander(t("eon_expander"), expanded=False):
        st.caption(t("eon_caption"))
        col_eon1, col_eon2 = st.columns(2)
        eon_install_id = col_eon1.text_input(t("installation_id"), key="eon_install",
                                              help=t("eon_install_help"))
        eon_years = col_eon2.number_input(t("years_count"), value=3, min_value=1, max_value=5, key="eon_years")
        if st.button(t("fetch_eon"), type="primary", key="eon_fetch"):
            if not eon_install_id:
                st.error(t("eon_missing_id"))
            else:
                with st.spinner(t("eon_fetching")):
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
                            st.success(t("eon_loaded").format(count=f"{len(eon_data):,}",
                                                                         days=days, kwh=f"{total:,.0f}"))
                        else:
                            st.warning(t("eon_no_data"))
                    except Exception as e:
                        st.error(t("eon_error").format(error=e))

    # File upload section — always visible (works alongside Tibber/E.ON)
    with st.expander(t("upload_expander"), expanded=not st.session_state.get("seasonal_profile")):
        st.caption(t("upload_caption"))
        cons_files = st.file_uploader(t("consumption_data"), type=["csv", "txt", "tsv", "xlsx", "xls", "json"],
                                       accept_multiple_files=True, key="cons_upload")
        # Parse each set of uploaded files only ONCE (not on every rerun): key on file ids.
        _cons_sig = tuple((getattr(f, "file_id", None) or f.name, f.size) for f in cons_files) if cons_files else None
        if not cons_files:
            st.session_state.pop("_cons_upload_sig", None)
            st.session_state.pop("_cons_upload_msgs", None)
        if cons_files and st.session_state.get("_cons_upload_sig") != _cons_sig:
            st.session_state["_cons_upload_sig"] = _cons_sig
            _cons_msgs = []  # (streamlit method, text) — shown on every rerun below
            try:
                from import_consumption import (
                    parse_any_consumption_file, ConsumptionParseError, rows_to_hourly,
                    consumption_to_hourly_profile,
                )
                from import_vattenfall import vattenfall_hourly_to_seasonal_profile
                # Clear previous *uploaded* data to avoid mixing old + new uploads.
                # Tibber data (hourly_profile / seasonal_profile from Tibber) is kept unless
                # the new upload replaces it below.
                st.session_state.pop("vattenfall_hourly", None)
                if st.session_state.pop("_seasonal_from_upload", False):
                    st.session_state.pop("seasonal_profile", None)
                all_rows = []
                seen_keys = set()
                vf_daily = []
                for f in cons_files:
                    raw = f.getvalue()
                    try:
                        rows, info = parse_any_consumption_file(f.name, raw)
                    except Exception as e:
                        # Vattenfall Excel without hourly columns: fall back to daily totals
                        if raw[:2] == b"PK":
                            import tempfile, os
                            from import_vattenfall import parse_vattenfall_excel
                            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                                tmp.write(raw)
                                tmp_path = tmp.name
                            try:
                                _daily = parse_vattenfall_excel(tmp_path)
                            except Exception:
                                _daily = []
                            finally:
                                os.unlink(tmp_path)
                            if _daily:
                                vf_daily.extend(_daily)
                                continue
                        if isinstance(e, ConsumptionParseError):
                            _reason = t(f"cons_err_{e.reason}")
                            _cols = ", ".join(e.columns[:30]) or "–"
                        else:
                            _reason, _cols = str(e), "–"
                        _cons_msgs.append(("error", t("cons_parse_failed").format(
                            name=f.name, reason=_reason, columns=_cols)))
                        continue
                    # Overlapping files: keep the first file's value for a timestamp
                    file_keys = {(r["date"], r["hour"]) for r in rows}
                    all_rows.extend(r for r in rows if (r["date"], r["hour"]) not in seen_keys)
                    seen_keys |= file_keys
                    _res = info.get("resolution_min")
                    _fmt = t(f"cons_fmt_{info['format']}") + f" ({info['container']}"
                    _fmt += f", {_res} min)" if _res else ")"
                    if info.get("detail") and info["format"].startswith("ha_"):
                        _fmt += f" — {info['detail']}"
                    _cons_msgs.append(("success", t("cons_file_loaded").format(
                        name=f.name, fmt=_fmt, start=rows[0]["date"], end=rows[-1]["date"],
                        days=len({r["date"] for r in rows}), count=f"{len(rows):,}")))

                if all_rows:
                    hourly = rows_to_hourly(all_rows)
                    profile = consumption_to_hourly_profile(all_rows)
                    st.session_state["hourly_profile"] = profile
                    months_with_data = {int(h["date"][5:7]) for h in hourly}
                    if len(months_with_data) >= 6:
                        # Real hourly series: seasonal profile + price date range sync.
                        seasonal = vattenfall_hourly_to_seasonal_profile(hourly)
                        for m in range(1, 13):
                            if m not in months_with_data:
                                seasonal[m] = {h: round(profile[h], 3) for h in range(24)}
                        st.session_state["seasonal_profile"] = seasonal
                        st.session_state["_seasonal_from_upload"] = True
                        st.session_state["vattenfall_hourly"] = hourly
                    # (summary line for the loaded series is shown by the status block below)
                elif vf_daily:
                    from import_vattenfall import vattenfall_to_seasonal_profile
                    seen = set()
                    unique = sorted([r for r in vf_daily if r["date"] not in seen and not seen.add(r["date"])],
                                    key=lambda x: x["date"])
                    hourly_shape = st.session_state.get("hourly_profile")
                    seasonal = vattenfall_to_seasonal_profile(unique, hourly_shape)
                    st.session_state["seasonal_profile"] = seasonal
                    st.session_state["_seasonal_from_upload"] = True
                    total = sum(r["consumption_kwh"] for r in unique)
                    avg = total / len(unique)
                    _cons_msgs.append(("success", t("daily_data_loaded").format(
                        days=len(unique), avg_day=avg, avg_year=f"{avg*365:,.0f}")))
            except Exception as e:
                _cons_msgs.append(("error", t("import_error").format(error=e)))
            st.session_state["_cons_upload_msgs"] = _cons_msgs
        for _kind, _msg in st.session_state.get("_cons_upload_msgs", []):
            getattr(st, _kind)(_msg)

    # Show loaded profile status
    if "seasonal_profile" in st.session_state:
        seasonal_load_profile = st.session_state["seasonal_profile"]
        all_kw = [kw for m in seasonal_load_profile.values() for kw in m.values()]
        _vf = st.session_state.get("vattenfall_hourly", [])
        if _vf:
            _vf_days = len(set(r["date"] for r in _vf))
            _vf_total = sum(r["kwh"] for r in _vf)
            _vf_avg = _vf_total / _vf_days if _vf_days > 0 else 0
            st.info(t("consumption_hourly_info").format(
                count=f"{len(_vf):,}", days=_vf_days,
                avg_day=_vf_avg, avg_year=f"{_vf_avg*365:,.0f}"))
        else:
            st.info(t("consumption_profile_range").format(
                min_kw=f"{min(all_kw):.1f}", max_kw=f"{max(all_kw):.1f}"))
    elif "hourly_profile" in st.session_state:
        hourly_load_profile = st.session_state["hourly_profile"]
        avg = sum(hourly_load_profile.values()) / 24
        st.info(t("consumption_profile_avg").format(avg=avg))
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

    # Language-independent option keys (labels via format_func) so the choice
    # survives a language switch and comparisons don't depend on translated text.
    _price_src_labels = {"api": "fetch_api", "csv": "load_csv"}
    price_source = st.radio(t("source"), list(_price_src_labels), key="price_src_key",
                             format_func=lambda k: t(_price_src_labels[k]),
                             help=t("price_source_help"))

    df_prices = st.session_state.get("df_prices")
    if price_source == "csv":
        price_file = st.file_uploader(t("price_csv_label"), type=["csv"], key="price_csv",
                                       help=t("price_csv_help"))
        if price_file:
            try:
                _df_up = pd.read_csv(price_file)
                if "sek_per_kwh" not in _df_up.columns and "ore_per_kwh" in _df_up.columns:
                    _df_up["sek_per_kwh"] = pd.to_numeric(_df_up["ore_per_kwh"], errors="coerce") / 100
                if "ore_per_kwh" not in _df_up.columns and "sek_per_kwh" in _df_up.columns:
                    _df_up["ore_per_kwh"] = pd.to_numeric(_df_up["sek_per_kwh"], errors="coerce") * 100
                _missing = [c for c in ("date", "hour", "sek_per_kwh") if c not in _df_up.columns]
                if _missing or len(_df_up) == 0:
                    raise ValueError(t("price_csv_missing_cols").format(
                        cols=", ".join(_missing) or "-"))
                _df_up["date"] = _df_up["date"].astype(str)
                _df_up["hour"] = _df_up["hour"].astype(str)
                df_prices = _df_up
                st.session_state["df_prices"] = df_prices
            except Exception as e:
                st.error(t("price_csv_error").format(error=e))
    else:
        zone = st.selectbox(t("price_zone"), ZONES, index=_default_zone_idx,
                            key=f"price_zone_{_default_zone_idx}",
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
        start_date = col_d1.date_input(t("from_date"), value=_default_start,
                                        key=f"price_start_{_default_start}")
        end_date = col_d2.date_input(t("to_date"), value=_default_end,
                                      key=f"price_end_{_default_end}")
        if _vf_hourly:
            st.caption(t("date_range_synced").format(start=_vf_dates[0], end=_vf_dates[-1]))
        if st.button(t("fetch_prices"), type="primary"):
            # Day-ahead prices exist at most for tomorrow
            _latest = date.today() + timedelta(days=1)
            if start_date > end_date:
                st.error(t("price_range_invalid"))
            elif start_date > _latest:
                st.error(t("price_range_future"))
            else:
                with st.spinner(t("fetching_prices")):
                    try:
                        rows = fetch_range(start_date, min(end_date, _latest), zone)
                    except Exception as e:
                        rows = []
                        st.error(f"{t('no_prices_found')} ({e})")
                    if rows:
                        df_prices = pd.DataFrame(rows)
                        st.session_state["df_prices"] = df_prices
                    else:
                        st.error(t("no_prices_found"))

    if df_prices is not None and len(df_prices) > 0:
        for col in ["sek_per_kwh", "ore_per_kwh"]:
            if col in df_prices.columns:
                df_prices[col] = pd.to_numeric(df_prices[col], errors="coerce")
        n_days = df_prices["date"].nunique()
        st.success(t("price_data_loaded").format(days=n_days,
                    start=df_prices['date'].min(), end=df_prices['date'].max()))
    else:
        st.warning(t("load_prices_warning"))

# --- Data status summary ---
# Persist loaded data to local disk ONLY when ENERGIKALKYL_PERSIST=1 (single-user
# self-hosted). Off by default: on shared/public servers state lives in the session only.
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
                st.warning(t("price_date_mismatch").format(
                    p_start=_price_min, p_end=_price_max,
                    c_start=_cons_min, c_end=_cons_max))
            else:
                st.success(t("data_synced"))
        else:
            st.success(t("data_loaded"))
    else:
        st.info(t("prices_loaded_no_consumption"))

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
                help=t("cheapest_hour_help"))
    col2.metric(t("most_expensive_hour"), f"{df_spread['max'].mean():.0f} öre/kWh",
                help=t("most_expensive_hour_help"))
    col3.metric(t("typical_spread"), f"{_median_range:.0f} öre/kWh",
                help=t("typical_spread_help"))
    col4.metric(t("good_days"), f"{_pct80_range:.0f} öre/kWh",
                help=t("good_days_help"))
    st.caption(t("spread_explanation"))
    fig_sp = go.Figure()
    fig_sp.add_trace(go.Scatter(x=df_spread["datetime"], y=df_spread["range"],
                                 mode="lines", name=t("daily_spread_trace"),
                                 line=dict(width=1, color="#f39c12")))
    monthly_range = df_spread.groupby("month")["range"].median().reset_index()
    monthly_range["datetime"] = pd.to_datetime(monthly_range["month"])
    fig_sp.add_hline(y=20, line_dash="dash", line_color="gray",
                      annotation_text=t("min_spread_annotation"))
    fig_sp.update_layout(yaxis_title=t("spread_yaxis"), height=300,
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
    efficiency = st.slider(t("efficiency"), 70, 100, 93, key="efficiency", help=t("efficiency_help")) / 100
    cycle_life = st.number_input(t("cycle_life"), value=8000, min_value=100, step=500,
                                  key="cycle_life", help=t("cycle_life_help"))

with col_sys2:
    st.subheader(t("solar_panels"))
    use_solar = st.checkbox(t("solar_panels"), value=True, key="use_solar")
    if use_solar:
        solar_kwp = st.number_input(t("system_kwp"), value=15.0, min_value=0.0, step=0.5, key="solar_kwp")
        _zero_export = st.checkbox(t("zero_export_label"), value=True, key="zero_export",
                                    help=t("zero_export_help"))
        if _zero_export:
            export_factor = 0.0
            export_fee = 0.0
            _export_arb_kwh = 0.0
        else:
            export_factor = st.number_input(t("export_price"), value=1.0, min_value=0.0, max_value=1.5, step=0.05,
                                            key="export_factor", help=t("export_price_help"))
            export_fee = st.number_input(t("export_fee"), value=5.0, min_value=0.0, step=1.0,
                                          key="export_fee", help=t("export_fee_help"))
            _export_arb_kwh = st.number_input(
                t("export_arb_label"), value=0.0, min_value=0.0, step=10.0, key="export_arb_kwh",
                help=t("export_arb_help"))
        # --- Solar production data sources ---
        _solar_src_labels = {"model": "solar_model", "pvgis": "solar_pvgis", "csv": "solar_csv"}
        _solar_source = st.radio(t("solar_data"), list(_solar_src_labels),
                                  format_func=lambda k: t(_solar_src_labels[k]),
                                  index=1 if not st.session_state.get("tibber_solar_monthly") else 0,
                                  horizontal=True, key="solar_source_key",
                                  help=t("solar_data_help"))
        _pvgis_tilt, _pvgis_aspect = None, None

        if _solar_source == "pvgis":
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
                            st.success(t("pvgis_success").format(
                                count=f"{len(records):,}", years=years, yearly=f"{yearly:,.0f}"))
                        else:
                            st.warning(t("pvgis_no_data"))
                    except Exception as e:
                        st.error(t("pvgis_error").format(error=e))

        elif _solar_source == "csv":
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
                        st.success(t("solar_csv_loaded").format(
                            count=f"{len(records):,}", days=days, total=f"{total:,.0f}"))
                    else:
                        st.warning(t("solar_csv_parse_error"))
                except Exception as e:
                    st.error(t("solar_import_error").format(error=e))

        _has_real_solar = bool(st.session_state.get("tibber_solar_monthly"))
        _use_real_solar = _has_real_solar and _solar_source != "model"
        if solar_kwp > 0:
            solar_config = SolarConfig(capacity_kwp=solar_kwp)
            if _use_real_solar:
                solar_config.real_production = st.session_state.get("tibber_solar_hourly")
                solar_config.real_monthly_kwh = st.session_state.get("tibber_solar_monthly")
                monthly_kwh = solar_config.real_monthly_kwh
                yearly = sum(monthly_kwh.values())
                _src_label = {"pvgis": "PVGIS", "csv": "CSV"}.get(_solar_source, "Tibber")
                st.caption(t("solar_source_comparison").format(
                    src=_src_label, yearly=f"{yearly:,.0f}",
                    model=f"{sum(MONTHLY_KWH_PER_KWP.values()) * solar_kwp * 0.85:,.0f}"))
        else:
            solar_config = None
    else:
        solar_config = None
        solar_kwp = 0
        _solar_source = None
        _pvgis_tilt, _pvgis_aspect = None, None
        export_factor = 0.0
        export_fee = 0.0
        _export_arb_kwh = 0.0

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
                                  key=f"grid_operator_{_op_default}", help=t("grid_operator_help"))
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
                              key=f"fuse_amps_{grid_operator}_{_fuse_default}", help=t("fuse_help"))
    phases = st.selectbox(t("phases"), [3, 1], index=0, key="phases")
    with st.expander(t("fuse_overcurrent_header"), expanded=False):
        st.caption(t("fuse_overcurrent_caption"))
        _overcurrent_options = {
            "fuse_oc_nominal": 0.0,
            "fuse_oc_safe": 0.25,
            "fuse_oc_aggressive": 0.60,
        }
        _oc_label = st.radio(
            t("fuse_overcurrent_label"),
            list(_overcurrent_options.keys()),
            format_func=t,
            index=0, key="fuse_overcurrent",
            help=t("fuse_overcurrent_help"),
        )
        fuse_overcurrent_factor = _overcurrent_options[_oc_label]
        if fuse_overcurrent_factor > 0:
            _eff_amps = fuse_amps * (1.0 + fuse_overcurrent_factor)
            st.warning(t("fuse_overcurrent_warning").format(
                fuse=fuse_amps, factor=1.0 + fuse_overcurrent_factor, effective=_eff_amps))
    energy_tax = st.number_input(t("energy_tax"), value=45.0, step=0.1, key="energy_tax",
                                  help=t("energy_tax_help"))
    available_tariffs = op_info["tariffs"]
    has_effekt = "Effekttariff" in available_tariffs and op_info.get("effekttariff")
    _fuse_fee_yr = op_fuse_fees.get(fuse_amps, 0)
    _fuse_list = ", ".join(f"{f:.0f}A" for f in fuse_options)
    if has_effekt:
        eff = op_info["effekttariff"]
        st.info(t("operator_info_effekt").format(operator=grid_operator, tariffs=", ".join(available_tariffs), rate=eff["effekt_rate"], fuses=_fuse_list))
    else:
        st.info(t("operator_info_basic").format(operator=grid_operator, tariffs=", ".join(available_tariffs), fuses=_fuse_list))
    with st.expander(t("tariff_details"), expanded=False):
        if "tidstariff" in op_info:
            _tid = op_info["tidstariff"]
            st.markdown(t("tidstariff_label"))
            st.caption(t("tidstariff_caption"))
            peak_rate = st.number_input(t("peak_rate_label"), value=_tid["peak"], step=0.5,
                                        key=f"peak_rate_{grid_operator}")
            offpeak_rate = st.number_input(t("offpeak_rate_label"), value=_tid["offpeak"], step=0.5,
                                           key=f"offpeak_rate_{grid_operator}")
        else:
            peak_rate = 76.5
            offpeak_rate = 30.5
        if "enkeltariff" in op_info:
            _enkel = op_info["enkeltariff"]
            st.markdown(t("enkeltariff_label"))
            st.caption(t("enkeltariff_caption"))
            flat_rate = st.number_input(t("flat_rate_label"), value=_enkel["flat_rate"], step=0.5,
                                        key=f"flat_rate_{grid_operator}")
        else:
            flat_rate = 44.5
        if has_effekt:
            eff = op_info["effekttariff"]
            st.markdown(t("effekttariff_label"))
            _peak_desc = t("effekt_peak_all_hours") if not eff.get("peak_months") else (
                t("effekt_peak_weekday").format(start=f"{eff.get('peak_hour_start', 0):02d}", end=f"{eff.get('peak_hour_end', 24):02d}")
                if eff.get("peak_weekday_only") else t("effekt_peak_alldays"))
            _night_desc = t("effekt_night_discount").format(pct=eff.get('night_discount', 1)*100) if eff.get("night_discount", 1) < 1 else ""
            st.caption(t("effekt_caption").format(top_n=eff['top_n_peaks'], peak_desc=_peak_desc, night_desc=_night_desc))
            effekt_rate = st.number_input(t("effekt_rate_label"), value=eff["effekt_rate"], step=1.0,
                                          key=f"effekt_rate_{grid_operator}")
            effekt_energy = st.number_input(t("effekt_energy_label"), value=eff["energy_rate"], step=0.5,
                                            key=f"effekt_energy_{grid_operator}")
            effekt_top_n = st.number_input(t("effekt_top_n_label"), value=eff["top_n_peaks"], min_value=1, max_value=10,
                                           key=f"effekt_top_n_{grid_operator}")
        st.markdown("---")
        monthly_fee = op_fuse_fees.get(fuse_amps, 0) / 12
        st.caption(t("tariff_summary").format(tax=energy_tax, fuse=f"{fuse_amps:.0f}", monthly=f"{monthly_fee:,.0f}", yearly=f"{op_fuse_fees.get(fuse_amps, 0):,.0f}"))

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
        base_load = st.number_input(t("base_load"), value=1.5, min_value=0.0, step=0.5, key="base_load",
                                    help=t("base_load_help"))
    else:
        base_load = 1.5  # overridden by profile or heating model

    if "scheduled_loads" not in st.session_state:
        st.session_state["scheduled_loads"] = [{"name": "Elbil", "power": 11.0, "start": 18, "end": 7,
                                                 "daily_kwh": 30.0, "smart": True}]

    st.markdown(t("scheduled_loads"))
    st.caption(t("scheduled_caption"))
    for i, load in enumerate(st.session_state["scheduled_loads"]):
        c = st.columns([3, 1.5, 1.5, 1.5, 1.5, 1])
        load["name"] = c[0].text_input("", value=load["name"], key=f"ln_{i}", label_visibility="collapsed")
        load["power"] = c[1].number_input("kW", value=load["power"], min_value=0.0, step=0.5, key=f"lp_{i}")
        load["start"] = c[2].number_input(t("load_from_hour"), value=load["start"], min_value=0, max_value=23, key=f"ls_{i}")
        load["end"] = c[3].number_input(t("load_to_hour"), value=load["end"], min_value=0, max_value=23, key=f"le_{i}")
        load["daily_kwh"] = c[4].number_input(t("load_kwh_day"), value=load.get("daily_kwh", 0.0), min_value=0.0, step=5.0, key=f"lk_{i}",
                                               help=t("load_kwh_day_help"))
        _smart_default = load.get("smart", False)
        load["smart"] = c[5].checkbox(t("load_smart"), value=_smart_default, key=f"lsm_{i}",
                                       help=t("load_smart_help"))
        if st.button(t("load_remove"), key=f"lx_{i}"):
            st.session_state["scheduled_loads"].pop(i)
            st.rerun()

    if st.button(t("add_load")):
        st.session_state["scheduled_loads"].append({"name": "Ny", "power": 1.0, "start": 0, "end": 6,
                                                     "daily_kwh": 0.0, "smart": False})
        st.rerun()

with col_l2:
    if "flexible_loads" not in st.session_state:
        st.session_state["flexible_loads"] = [
            {"name": "Poolpump", "power": 3.0, "daily": 20.0, "sm": 5, "em": 9},
            {"name": "Varmvatten", "power": 3.0, "daily": 99.0, "sm": 1, "em": 12},
        ]

    _month_names = t("month_names")
    _month_opts = list(range(1, 13))

    st.markdown(t("flexible_loads"))
    st.caption(t("flexible_caption"))
    for i, fl in enumerate(st.session_state["flexible_loads"]):
        c = st.columns([3, 2, 2, 2, 2, 1])
        fl["name"] = c[0].text_input("", value=fl["name"], key=f"fn_{i}", label_visibility="collapsed")
        fl["power"] = c[1].number_input("kW", value=fl["power"], min_value=0.0, step=0.5, key=f"fp_{i}")
        fl["daily"] = c[2].number_input(t("flex_max_kwh_day"), value=fl["daily"], min_value=0.0, step=1.0, key=f"fd_{i}",
                                       help=t("flex_max_kwh_help").format(power=fl["power"], hours=f"{fl['daily']/fl['power']:.0f}", total=f"{fl['daily']:.0f}") if fl["power"] > 0 else "")
        fl["sm"] = c[3].selectbox(t("flex_active_from"), _month_opts, index=fl["sm"]-1,
                                   format_func=lambda m: _month_names[m-1], key=f"fs_{i}")
        fl["em"] = c[4].selectbox(t("flex_active_to"), _month_opts, index=fl["em"]-1,
                                   format_func=lambda m: _month_names[m-1], key=f"fe_{i}")
        if c[5].button("X", key=f"fx_{i}"):
            st.session_state["flexible_loads"].pop(i)
            st.rerun()

    if st.button(t("add_flex_load")):
        st.session_state["flexible_loads"].append({"name": "Ny", "power": 2.0, "daily": 10.0, "sm": 1, "em": 12})
        st.rerun()

scheduled_loads = [LoadSchedule(l["name"], l["power"], l["start"], l["end"],
                                daily_kwh=l.get("daily_kwh", 0.0), smart=l.get("smart", False))
                   for l in st.session_state["scheduled_loads"] if l["power"] > 0]
flexible_loads = [FlexibleLoad(f["name"], f["power"], f["daily"], f["sm"], f["em"])
                  for f in st.session_state["flexible_loads"] if f["power"] > 0]

# Add luft-luft as flexible load when enabled (absorbs solar surplus)
if st.session_state.get("use_aa", False):
    _aa_kw = st.session_state.get("aa_heat_kw", 3.2)
    _aa_cool = st.session_state.get("aa_cool_kw", 2.5)
    # Summer: pre-cool house on solar surplus (thermal storage)
    flexible_loads.append(FlexibleLoad(t("aa_flex_cool"), _aa_cool, daily_kwh=8.0,
                                        start_month=6, end_month=8))
    # Spring/autumn: pre-heat on solar surplus
    flexible_loads.append(FlexibleLoad(t("aa_flex_heat"), _aa_kw, daily_kwh=8.0,
                                        start_month=3, end_month=5))
    flexible_loads.append(FlexibleLoad(t("aa_flex_heat"), _aa_kw, daily_kwh=8.0,
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
st.subheader(t("heating_header"))
use_heating_model = st.checkbox(t("heating_checkbox"), value=True, key="use_heating_model",
                                 help=t("heating_checkbox_help"))
daily_load_override = None
heating_config = None

if use_heating_model:
    st.caption(t("heating_caption"))
    # --- Location selection ---
    st.markdown(t("heating_location"))
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
        selected_city = st.selectbox(t("city_label"), city_names, index=_city_default,
                                      key=f"city_{_city_default}", help=t("city_help"))

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
        _loc_source = t("loc_source_tibber") if (_tibber_lat and _tibber_lon and selected_city.lower() == _tibber_city.lower()) else t("loc_source_city")
        st.caption(t("nearest_station").format(name=station_name, dist=station_dist, source=_loc_source))
        # Allow manual override
        with st.expander(t("choose_other_station"), expanded=False):
            station_list = sorted(stations.items(), key=lambda x: x[1][0])
            station_options = {f"{name} ({sid})": sid for sid, (name, _, _) in station_list}
            default_key = f"{station_name} ({station_id})"
            selected_station = st.selectbox(t("station_label"), list(station_options.keys()),
                                             index=list(station_options.keys()).index(default_key)
                                             if default_key in station_options else 0,
                                             key=f"station_{default_key}")
            station_id = station_options[selected_station]
            station_name = selected_station.split(" (")[0]

    # Load or fetch temperature data
    temps_data = load_temperatures(station_id=station_id)
    if not temps_data:
        with st.spinner(t("fetching_weather").format(name=station_name)):
            try:
                fetch_station_data(station_id)
                temps_data = load_temperatures(station_id=station_id)
            except Exception as e:
                st.warning(t("weather_fetch_error").format(error=e))

    if temps_data:
        # --- House calibration ---
        st.markdown(t("your_house"))
        st.caption(t("house_calibration_help"))

        # Energy class → h_loss lookup (for ground-source heat pump, COP_avg ~3.2)
        # Computed from: h_loss = (energy_class × area - DHW_elec - vent_elec) × COP / degree_hours
        # Stockholm degree-hours ~123,000 °C·h/year, DHW ~2190 kWh/yr, vent ~750 kWh/yr
        _DEGREE_HOURS = 123000
        _COP_AVG = 3.2
        _DHW_ANNUAL = 2190
        _VENT_ANNUAL = 750

        # Keys are language-independent energy class letters; labels via format_func
        _ENERGY_CLASSES = {"A": 50, "B": 63, "C": 88, "D": 115, "E": 145, "F": 175, "G": 220}

        col_house1, col_house2 = st.columns(2)
        with col_house1:
            energy_class = st.selectbox(t("energy_class_label"),
                                         list(_ENERGY_CLASSES.keys()), index=2,
                                         format_func=lambda k: t(f"eclass_{k.lower()}"),
                                         key="energy_class", help=t("energy_class_help"))
            _tibber_size = st.session_state.get("tibber_home", {}).get("house_size", 0)
            _area_default = _tibber_size if _tibber_size > 0 else 150
            house_area = st.number_input(t("house_area_label"), value=_area_default, min_value=30, max_value=500, step=10,
                                          key=f"house_area_{_area_default}", help=t("house_area_help"))

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
            # Language-independent option keys (translation keys), labels via format_func
            _heating_options = ["heating_ground", "heating_airsource", "heating_district", "heating_electric"]
            _tibber_heat = st.session_state.get("tibber_home", {}).get("heating_source", "")
            _heat_map = {"GROUND": 0, "AIR2AIR": 1, "AIR2WATER": 1,
                          "DISTRICT": 2, "ELECTRIC": 3}
            _heat_default = _heat_map.get(_tibber_heat, 0)
            heating_type = st.selectbox(t("heating_label"), _heating_options, index=_heat_default,
                                         format_func=t, key=f"heating_type_{_heat_default}",
                                         help=t("heating_type_help"))

            if heating_type == "heating_ground":
                cop_info = t("cop_ground")
            elif heating_type == "heating_airsource":
                cop_info = t("cop_airsource")
            elif heating_type == "heating_district":
                cop_info = t("cop_district")
            else:
                cop_info = t("cop_electric")
            st.caption(cop_info)

            # Air-to-air supplement (works with any primary heating)
            use_aa = st.checkbox(t("aa_checkbox"), value=False,
                                  key="use_aa",
                                  help=t("aa_help"))
            if use_aa:
                # Preset models
                _AA_PRESETS = {
                    "hero": {
                        "label": "Mitsubishi Hero 2.0 LN25 (SCOP 5.2, A+++)",
                        "heat_kw": 3.2, "cool_kw": 2.5, "price": 30000,
                        "info": t("aa_preset_hero_info"),
                    },
                    "custom": {
                        "label": t("aa_preset_custom"),
                        "heat_kw": 3.0, "cool_kw": 2.5, "price": 25000,
                        "info": t("aa_preset_custom_info"),
                    },
                }
                aa_model = st.selectbox(t("aa_model_label"), list(_AA_PRESETS.keys()), index=0,
                                        format_func=lambda k: _AA_PRESETS[k]["label"], key="aa_model_key")
                _aa_preset = _AA_PRESETS[aa_model]
                _aa_custom = aa_model == "custom"

                col_aa1, col_aa2, col_aa3 = st.columns(3)
                with col_aa1:
                    aa_heat_kw = st.number_input(t("aa_heat_kw_label"),
                                                  value=_aa_preset["heat_kw"],
                                                  min_value=0.5, max_value=10.0, step=0.5,
                                                  key="aa_heat_kw", disabled=not _aa_custom,
                                                  help=t("aa_heat_kw_help"))
                    aa_min_temp = st.number_input(t("aa_min_temp_label"), value=1.0,
                                                   min_value=-20.0, max_value=10.0, step=1.0,
                                                   key="aa_min_temp",
                                                   help=t("aa_min_temp_help"))
                with col_aa2:
                    aa_cool_kw = st.number_input(t("aa_cool_kw_label"),
                                                  value=_aa_preset["cool_kw"],
                                                  min_value=0.5, max_value=10.0, step=0.5,
                                                  key="aa_cool_kw", disabled=not _aa_custom,
                                                  help=t("aa_cool_kw_help"))
                    aa_cool_threshold = st.number_input(t("aa_cool_threshold_label"), value=24.0,
                                                         min_value=18.0, max_value=35.0, step=1.0,
                                                         key="aa_cool_threshold",
                                                         help=t("aa_cool_threshold_help"))
                with col_aa3:
                    aa_price = st.number_input(t("aa_price_label"),
                                                value=_aa_preset["price"],
                                                min_value=0, step=1000, key="aa_price",
                                                disabled=not _aa_custom,
                                                help=_aa_preset["info"])
                    aa_lifetime = st.number_input(t("aa_lifetime_label"), value=15,
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
        with st.expander(t("detailed_hp_settings"), expanded=False):
            col_h1, col_h2, col_h3 = st.columns(3)
            with col_h1:
                _hloss_help = (t("hloss_calibrated").format(value=h_loss_default)
                               if _calibrated else
                               t("hloss_estimated").format(value=h_loss_default))
                # Default in the key: a new calibration must still override the widget
                # (see CLAUDE.md "Calibrated h_loss must override energy class")
                h_loss = st.number_input(t("hloss_label"), value=h_loss_default,
                                          min_value=0.01, max_value=1.5, step=0.001, format="%.3f",
                                          key=f"h_loss_{h_loss_default}", help=_hloss_help)
                if _calibrated:
                    st.caption(t("calibration_note"))
                hp_max = st.number_input(t("hp_max_label"), value=_hp_max_default, min_value=1.0, step=0.5,
                                          key=f"hp_max_{_hp_max_default}", help=t("hp_max_help").format(hp_max=_hp_max_default, area=house_area))
            with col_h2:
                elpatron_kw = st.number_input(t("elpatron_label"), value=3.0, min_value=0.0, step=0.5,
                                               key="elpatron_kw", help=t("elpatron_help"))
                dhw_kwh = st.number_input(t("dhw_label"), value=_dhw_default, min_value=0.0, step=1.0,
                                           key=f"dhw_kwh_{_dhw_default}", help=t("dhw_help").format(dhw=_dhw_default, area=house_area))
            with col_h3:
                non_heat_base = st.number_input(t("base_no_heat_label"), value=_base_default, min_value=0.0,
                                                 step=0.01, format="%.2f", key=f"non_heat_base_{_base_default}",
                                                 help=t("base_no_heat_help").format(base=_base_default, area=house_area))

        st.caption(t("heating_summary_caption").format(
            eclass=energy_class, area=house_area, hloss=f"{h_loss:.3f}",
            days=len(temps_data), start=min(temps_data.keys()), end=max(temps_data.keys())))

        # Adjust COP model for heating type
        if heating_type == "heating_airsource":
            cop_base, cop_slope = 2.8, 0.08  # worse at cold temps
        elif heating_type == "heating_district":
            cop_base, cop_slope = 99.0, 0.0  # essentially free heating (no compressor)
        elif heating_type == "heating_electric":
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

            with st.expander(t("aa_investment_header"), expanded=False):
                col_roi1, col_roi2 = st.columns(2)
                with col_roi1:
                    st.metric(t("aa_heat_saving"), f"{_aa_saving_kwh:,.0f} {t('kwh_yr')}",
                              help=t("aa_heat_saving_help"))
                    st.metric(t("aa_ac_consumption"), f"{_aa_cooling_kwh_yr:,.0f} {t('kwh_yr')}",
                              help=t("aa_ac_consumption_help"))
                with col_roi2:
                    st.metric(t("aa_net_saving"), f"{_aa_net_kr:,.0f} {t('kr_yr')}",
                              help=t("aa_net_saving_help"))
                    if _aa_net_kr > 0:
                        st.metric(t("aa_payback"), f"{_aa_payback:.1f} {t('yr_unit')}")
                    else:
                        st.metric(t("aa_payback"), "—",
                                  help=t("aa_payback_na_help"))
                if _aa_net_kr > 0:
                    st.info(t("aa_invest_positive").format(
                        price=f"{aa_price:,}", profit=f"{_aa_profit:+,.0f}",
                        years=aa_lifetime, monthly=f"{_aa_net_kr/12:,.0f}"))
                else:
                    st.info(t("aa_invest_comfort").format(
                        saving_kwh=f"{_aa_saving_kwh:,.0f}",
                        cooling_kwh=f"{_aa_cooling_kwh_yr:,.0f}"))

        # --- Manual calibration from Tibber Insights ---
        with st.expander(t("cal_expander"), expanded=True):
            st.caption(t("cal_caption"))
            col_cal1, col_cal2 = st.columns(2)
            with col_cal1:
                cal_year = st.selectbox(t("cal_year_label"), [2025, 2024, 2023], index=0,
                                         key="cal_year")
                cal_total = st.number_input(t("cal_total_label"), value=0, min_value=0,
                                             step=100, key="cal_total",
                                             help=t("cal_total_help"))
                cal_heating = st.number_input(t("cal_heating_label"), value=0, min_value=0,
                                               step=100, key="cal_heating",
                                               help=t("cal_heating_help"))
            with col_cal2:
                cal_ev = st.number_input(t("cal_ev_label"), value=0, min_value=0,
                                          step=100, key="cal_ev",
                                          help=t("cal_ev_help"))
                cal_active = st.number_input(t("cal_active_label"), value=0, min_value=0,
                                              step=100, key="cal_active",
                                              help=t("cal_active_help"))
                cal_always = st.number_input(t("cal_always_label"), value=0, min_value=0,
                                              step=100, key="cal_always",
                                              help=t("cal_always_help"))

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
                            t("cal_success").format(
                            year=cal_year, hloss=f"{cal_h_loss:.3f}",
                            base=f"{cal_base:.2f}", heating=f"{cal_heating:,}",
                            ev=f"{cal_ev:,}", other=f"{cal_active + cal_always:,}")
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

                        # Auto-update EV scheduled load from real data
                        if cal_ev > 0 and st.session_state.get("scheduled_loads"):
                            _ev_daily = round(cal_ev / 365, 1)
                            for _sl in st.session_state["scheduled_loads"]:
                                if "bil" in _sl["name"].lower() or "ev" in _sl["name"].lower():
                                    _sl["daily_kwh"] = _ev_daily
                            st.caption(t("cal_ev_updated").format(
                                daily=_ev_daily, annual=f"{cal_ev:,}"))
                else:
                    st.warning(t("cal_insufficient_weather").format(
                        year=cal_year, days=len(year_temps)))

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
            st.info(t("house_consumption_summary").format(
                    annual=f"{annual_house:,.0f}",
                    winter=f"{statistics.mean(winter_days.values()):.0f}",
                    summer=f"{statistics.mean(summer_days.values()):.0f}"))
    else:
        st.warning(t("no_weather_data").format(station=station_name))
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
_pricing_mode_labels = {"table": "specific_batteries", "sek_kwh": "sek_per_kwh_mode"}
_pricing_mode = st.radio(t("pricing_mode"), list(_pricing_mode_labels),
                          format_func=lambda k: t(_pricing_mode_labels[k]),
                          key="pricing_mode_key", horizontal=True)

if _pricing_mode == "sek_kwh":
    st.caption(t("sek_kwh_caption"))
    col_sek1, col_sek2, col_sek3 = st.columns(3)
    with col_sek1:
        sek_per_kwh = st.number_input(t("battery_price_kwh"), value=1000, min_value=100, max_value=5000,
                                       step=50, key="sek_per_kwh",
                                       help=t("sek_kwh_typical_help"))
    with col_sek2:
        max_charge_kw = st.number_input(t("max_charge_kw"), value=11.0, min_value=1.0, max_value=30.0,
                                         step=0.5, key="max_charge_kw_auto",
                                         help=t("max_kw_help"))
    with col_sek3:
        _step_kwh = st.number_input(t("step_kwh"), value=5, min_value=1, max_value=20, step=1,
                                     key="auto_step_kwh",
                                     help=t("step_kwh_help"))

    # Generate battery table from SEK/kWh
    _sizes = list(range(_step_kwh, 101, _step_kwh))
    battery_table = pd.DataFrame([
        {"Namn": f"{s} kWh", "Kapacitet_kWh": float(s),
         "Max_kW": min(max_charge_kw, s * 0.5),  # C-rate max ~0.5C
         "Pris_SEK": round(s * sek_per_kwh)}
        for s in _sizes
    ])
    st.caption(t("testing_sizes").format(count=len(_sizes), first=_sizes[0], last=_sizes[-1], price=sek_per_kwh))

else:
    st.caption(t("edit_table_caption"))
    st.caption(t("nkon_vat_note"))

    EUR_SEK = st.number_input(t("eur_sek_rate"), value=11.5, min_value=5.0, max_value=20.0, step=0.1,
                               key="eur_sek_rate")

    # NKON list prices are in EUR excl. Swedish VAT; a private buyer pays 25% on top
    BATTERY_VAT = 1.25
    default_batteries = pd.DataFrame([
        {"Namn": "5 kWh",       "Kapacitet_kWh": 5.12,   "Max_kW": 3.8,  "Pris_SEK": round(600 * EUR_SEK * BATTERY_VAT)},
        {"Namn": "10 kWh",      "Kapacitet_kWh": 10.24,  "Max_kW": 7.5,  "Pris_SEK": round(1177 * EUR_SEK * BATTERY_VAT)},
        {"Namn": "16 kWh",      "Kapacitet_kWh": 16.10,  "Max_kW": 11.0, "Pris_SEK": round(1512 * EUR_SEK * BATTERY_VAT)},
        {"Namn": "32 kWh",      "Kapacitet_kWh": 32.15,  "Max_kW": 15.0, "Pris_SEK": round(2857 * EUR_SEK * BATTERY_VAT)},
        {"Namn": "32+16 kWh",   "Kapacitet_kWh": 48.25,  "Max_kW": 15.0, "Pris_SEK": round((2857+1512) * EUR_SEK * BATTERY_VAT)},
        {"Namn": "2x32 kWh",    "Kapacitet_kWh": 64.30,  "Max_kW": 15.0, "Pris_SEK": round(2857 * 2 * EUR_SEK * BATTERY_VAT)},
        {"Namn": "2x32+16 kWh", "Kapacitet_kWh": 80.40,  "Max_kW": 15.0, "Pris_SEK": round((2857*2+1512) * EUR_SEK * BATTERY_VAT)},
        {"Namn": "3x32 kWh",    "Kapacitet_kWh": 96.45,  "Max_kW": 15.0, "Pris_SEK": round(2857 * 3 * EUR_SEK * BATTERY_VAT)},
    ])

    if (st.session_state.get("_bt_seed") is not None
            and st.session_state.get("_bt_seed_eur") == EUR_SEK):
        default_batteries = st.session_state["_bt_seed"]  # edits kept across a language switch

    battery_table = st.data_editor(
        default_batteries,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Namn": st.column_config.TextColumn(t("bt_col_name")),
            "Kapacitet_kWh": st.column_config.NumberColumn(t("bt_col_capacity"), min_value=0.1, format="%.2f"),
            "Max_kW": st.column_config.NumberColumn(t("bt_col_max_kw"), min_value=0.1, format="%.1f"),
            "Pris_SEK": st.column_config.NumberColumn(t("bt_col_price"), min_value=0, format="%d"),
        },
        key="battery_table",
    )
    st.session_state["_bt_last"] = battery_table[["Namn", "Kapacitet_kWh", "Max_kW", "Pris_SEK"]].copy()

    # Show kr/kWh for each row
    if len(battery_table) > 0:
        battery_table["kr_per_kWh"] = (battery_table["Pris_SEK"] / battery_table["Kapacitet_kWh"]).round(0)
        st.caption(t("price_per_kwh_caption") + " " + " | ".join(
            f"{r['Namn']}: {r['kr_per_kWh']:.0f} kr/kWh" for _, r in battery_table.iterrows()
            if r["Kapacitet_kWh"] > 0))

# Other costs
col_i1, col_i2, col_i3 = st.columns(3)
with col_i1:
    bat_install = st.number_input(t("battery_install"), value=10000, min_value=0, step=1000,
                                   key="bat_install", help=t("install_same_cost_help"))
with col_i2:
    if use_solar:
        sol_price = st.number_input(t("solar_material"), value=48000, min_value=0, step=5000,
                                    key="sol_price", help=t("solar_material_help"))
        sol_install = st.number_input(t("solar_install"), value=0, min_value=0, step=5000,
                                      key="sol_install", help=t("solar_install_help"))
    else:
        sol_price = 0
        sol_install = 0
with col_i3:
    # Option keys are translation keys (language-independent); labels via format_func
    finance = st.radio(t("financing"), ["own_capital", "mortgage", "other_loan"],
                       format_func=t, key="finance")
    if finance == "mortgage":
        loan_rate = st.number_input(t("mortgage_rate"), value=3.0, min_value=0.0, max_value=10.0, step=0.25,
                                    key="mortgage_rate")
        loan_years = st.number_input(t("loan_term"), value=50, min_value=1, max_value=100, step=5,
                                     key="mortgage_years")
        st.caption(t("mortgage_caption"))
    elif finance == "other_loan":
        loan_rate = st.number_input(t("interest_rate"), value=5.0, min_value=0.0, step=0.5, key="loan_rate")
        loan_years = st.number_input(t("loan_years"), value=10, min_value=1, step=1, key="loan_years")
        st.caption(t("loan_caption"))
    else:
        loan_rate = 0
        loan_years = 0

sol_invest_total = sol_price + sol_install

# --- Grön teknik tax deduction (skattereduktion för grön teknik, 2026 rates) ---
# 50% of labour+material for storage of self-produced electricity (battery),
# 15% for solar panels (20% for installs in 2025, 15% from 2026).
# Cap: 50,000 kr per person and year; max 2 persons can share (100,000 kr).
# Requires installation by a company with F-skatt (not DIY) and, for the battery,
# that it stores self-produced (solar) electricity.
GREEN_RATE_BATTERY = 0.50
GREEN_RATE_SOLAR = 0.15
GREEN_CAP_PER_PERSON = 50000
SOLAR_LIFETIME_YEARS = 25  # solar investment is prorated to the battery-lifetime horizon

col_g1, col_g2 = st.columns([3, 1])
with col_g1:
    use_green_deduction = st.checkbox(t("green_deduction_label"), value=True, key="green_deduction",
                                      help=t("green_deduction_help"))
with col_g2:
    green_owners = st.selectbox(t("green_owners_label"), [1, 2], index=0, key="green_owners",
                                disabled=not use_green_deduction, help=t("green_owners_help"))


def _green_deduction(bat_gross, sol_gross):
    """Return (battery_deduction, solar_deduction) in SEK, capped per owner.

    The battery part only applies when it stores self-produced (solar) electricity.
    """
    if not use_green_deduction:
        return 0.0, 0.0
    bat_d = GREEN_RATE_BATTERY * bat_gross if use_solar and solar_kwp > 0 else 0.0
    sol_d = GREEN_RATE_SOLAR * sol_gross
    cap = GREEN_CAP_PER_PERSON * green_owners
    raw = bat_d + sol_d
    if raw > cap > 0:
        bat_d, sol_d = bat_d * cap / raw, sol_d * cap / raw
    return bat_d, sol_d


def _profit_over_life(benefit_yr, lifetime, bat_invest_net, sol_invest_net):
    """Net result over the battery lifetime (the horizon used everywhere).

    The battery investment is written off over its own lifetime; the solar investment
    lives SOLAR_LIFETIME_YEARS, so only the share belonging to this horizon is charged.
    """
    return (benefit_yr * lifetime - bat_invest_net
            - sol_invest_net * min(1.0, lifetime / SOLAR_LIFETIME_YEARS))

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


def _inputs_signature():
    """Fingerprint of every input that affects the simulation results (language-independent).

    Used to detect when shown results are stale (inputs changed after the last run).
    """
    import hashlib
    _hc = heating_config
    _parts = [
        efficiency, cycle_life, use_solar, solar_kwp, export_factor, export_fee, _export_arb_kwh,
        _solar_source, sorted((solar_config.real_monthly_kwh or {}).items()) if solar_config else None,
        grid_operator, fuse_amps, phases, fuse_overcurrent_factor, energy_tax,
        peak_rate, offpeak_rate, flat_rate,
        (effekt_rate, effekt_energy, effekt_top_n) if has_effekt else None,
        base_load, st.session_state.get("scheduled_loads"), st.session_state.get("flexible_loads"),
        st.session_state.get("use_aa", False),
        use_heating_model, (_hc.h_loss, _hc.hp_max_heat_kw, _hc.elpatron_kw, _hc.dhw_kwh_per_day,
                            _hc.cop_base, _hc.cop_slope, _hc.aa_enabled) if _hc else None,
        non_heat_base if daily_load_override else None,
        (len(daily_load_override), round(sum(sum(p.values()) for p in daily_load_override.values()), 3))
        if daily_load_override else None,
        sorted(hourly_load_profile.items()) if hourly_load_profile else None,
        repr(seasonal_load_profile) if seasonal_load_profile else None,
        battery_table[["Namn", "Kapacitet_kWh", "Max_kW", "Pris_SEK"]].to_csv(index=False),
        bat_install, sol_price, sol_install, finance, loan_rate, loan_years,
        use_green_deduction, green_owners,
        len(df_prices), str(df_prices["date"].min()), str(df_prices["date"].max()),
        float(pd.to_numeric(df_prices["sek_per_kwh"], errors="coerce").sum()),
    ]
    return hashlib.md5(repr(_parts).encode()).hexdigest()


_current_sig = _inputs_signature()

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


# Future-scenario volatility levels (target factors + intermediate points for interpolation)
FUTURE_SCENARIOS = [("conservative", 1.5), ("likely", 2.5), ("high_volatility", 4.0)]
ALL_VOL_LEVELS = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]


def _compute_vol_benefits(best, price_rows, solar_cfg):
    """Simulate the recommended battery at each volatility level (once, after a simulation).

    Returns {factor: yearly benefit} with the SAME benefit definition as the main
    recommendation: arbitrage + effekt savings + solar self-consumption − fuse fee delta
    (and, for existing panels with export, minus the export they earn without a battery).
    Factor 1.0 is the main result itself (no re-simulation).
    """
    ref_cfg = best["config"]
    _extra = (best["total_benefit_yr"] - best["arb_yr"]) - best["fuse_fee_delta_yr"]
    out = {1.0: best["net_benefit_yr"]}
    for vf in ALL_VOL_LEVELS:
        if vf == 1.0:
            continue
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
            export_arbitrage_kwh=ref_cfg.export_arbitrage_kwh,
            purchase_price=round(best["bat_cost"]), installation_cost=ref_cfg.installation_cost,
            cycle_life=ref_cfg.cycle_life, calendar_life_years=15,
            fuse_overcurrent_factor=ref_cfg.fuse_overcurrent_factor,
        )
        r = simulate(scaled, fc_cfg, tariff=best["tariff"], solar=solar_cfg)
        d = len(set(s.date for s in r.slots))
        ay = r.net_profit_sek / d * 365.25 if d > 0 else 0
        if d > 0 and isinstance(best["tariff"], EffektTariff):
            ay += effekt_savings(r, best["tariff"], fc_cfg, d,
                                 solar_in_baseline=bool(solar_cfg) and sol_invest_total == 0)
        if d > 0 and solar_cfg and sol_invest_total == 0 and fc_cfg.export_price_factor > 0:
            # Existing panels: their export without a battery (at these prices) isn't battery value
            ay -= baseline_export_revenue(scaled, fc_cfg, best["tariff"], solar_cfg) / d * 365.25
        out[vf] = ay + _extra
    return out


if st.button(t("run_simulation"), type="primary", use_container_width=True):
    # Clear old results
    for key in ["all_results", "solar_cfg", "price_rows", "shared_config", "fuse_variants",
                "scenario_results", "vol_arb", "sim_inputs", "sim_sig", "export_cmp", "_pdf_cache"]:
        st.session_state.pop(key, None)

    # Validate battery table
    valid_rows = battery_table.dropna(subset=["Kapacitet_kWh", "Max_kW", "Pris_SEK"])
    valid_rows = valid_rows[valid_rows["Kapacitet_kWh"] > 0]
    if len(valid_rows) == 0:
        st.error(t("no_battery_rows"))
        st.stop()

    if solar_config:
        solar_config.purchase_price = sol_price
        solar_config.installation_cost = sol_install

    # Determine fuse sizes to sweep (down + user's selection + larger)
    # Minimum fuse: must handle household peak load (base + all scheduled loads running)
    # Derate for phase imbalance: loads aren't balanced across 3 phases
    _phase_balance = 0.7 if phases == 3 else 1.0
    _peak_load_kw = base_load + sum(l.power_kw for l in scheduled_loads)
    _min_fuse_amps = _peak_load_kw / (0.23 * phases * _phase_balance) if phases > 0 else 16
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
    # Panels the household already has (solar enabled, no solar investment)
    _existing_solar = bool(solar_config) and sol_invest_total == 0
    _baseline_export_cache = {}  # (fuse, tariff name) -> export SEK/yr without battery

    # Simulate ALL battery sizes × tariffs × fuse sizes
    _all_raw_results = []
    _n_tariffs = len(_build_tariffs_for_fuse(fuse_amps))
    with st.spinner(t("simulation_spinner").format(batteries=len(valid_rows), tariffs=_n_tariffs, fuses=len(_fuses_to_sweep))):
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
                export_arbitrage_kwh=_export_arb_kwh,
                fuse_overcurrent_factor=fuse_overcurrent_factor,
            )

            # Simulate all tariffs, pick best
            best_profit = -999999
            result = None
            tariff = None
            best_tariff = ""
            num_days = 0
            effekt_saving_yr = 0
            solar_self_yr = 0
            baseline_export_yr = 0

            for _tf in _fuse_tariffs:
                r = simulate(price_rows, cfg, tariff=_tf, solar=solar_config)
                d = len(set(s.date for s in r.slots))
                if d == 0:
                    continue
                p = r.net_profit_sek / d * 365.25

                # For effekttariff: demand charge change caused by the investment (can be negative).
                # Computed right after simulate(): cfg's smart-load schedule belongs to this tariff.
                eff_save = 0
                if isinstance(_tf, EffektTariff):
                    eff_save = effekt_savings(r, _tf, cfg, d, solar_in_baseline=_existing_solar)
                    p += eff_save

                # Existing panels + export: the export they earn without any battery is not
                # battery value (doesn't depend on battery size → cached per fuse and tariff)
                base_exp = 0
                if _existing_solar and export_factor > 0:
                    _bk = (_fuse, _tf.name)
                    if _bk not in _baseline_export_cache:
                        _baseline_export_cache[_bk] = baseline_export_revenue(
                            price_rows, cfg, _tf, solar_config) / d * 365.25
                    base_exp = _baseline_export_cache[_bk]
                    p -= base_exp

                # Solar used directly by the house (also needs this tariff's schedule in cfg)
                sol_self = 0
                if solar_config:
                    sol_self = solar_direct_use(r, cfg)[1] / d * 365.25

                if p > best_profit:
                    best_profit = p
                    result = r
                    tariff = _tf
                    best_tariff = _tf.name
                    num_days = d
                    effekt_saving_yr = eff_save
                    solar_self_yr = sol_self
                    baseline_export_yr = base_exp

            if result is None:
                continue

            arb_yr = (result.net_profit_sek / num_days * 365.25 + effekt_saving_yr
                      - baseline_export_yr) if num_days > 0 else 0

            total_benefit_yr = arb_yr + (solar_self_yr if sol_invest_total > 0 else 0)
            net_benefit_yr = total_benefit_yr - _fuse_fee_delta_yr
            # Investments are net of the grön teknik deduction (when enabled)
            _bat_ded, _sol_ded = _green_deduction(bat_cost + bat_install, sol_invest_total)
            invest = bat_cost + bat_install - _bat_ded
            sol_invest_net = sol_invest_total - _sol_ded
            total_invest = invest + sol_invest_net
            cycles_yr = result.num_cycles / (num_days / 365.25) if num_days > 0 else 0
            lifetime = min(cycle_life / cycles_yr if cycles_yr > 0 else 15, 15)
            payback = total_invest / net_benefit_yr if net_benefit_yr > 0 else None
            profit_life = _profit_over_life(net_benefit_yr, lifetime, invest, sol_invest_net)

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
                "sol_invest_net": sol_invest_net,
                "green_bat": _bat_ded, "green_sol": _sol_ded,
                "gross_invest": bat_cost + bat_install + sol_invest_total,
                "effekt_saving_yr": effekt_saving_yr,
                "baseline_export_yr": baseline_export_yr,
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
    st.session_state["sim_sig"] = _current_sig

    # Snapshot of the inputs these results were computed with (PDF + result texts use it,
    # so changing a widget afterwards can't make the report mix old results with new inputs)
    _th_snap = st.session_state.get("tibber_home", {})
    if _th_snap.get("address") and _th_snap.get("city"):
        _addr_snap = f"{_th_snap['address']}, {_th_snap['city']}"
    else:
        _addr_snap = selected_city if use_heating_model else ""
    st.session_state["sim_inputs"] = {
        "grid_operator": grid_operator, "fuse_amps": fuse_amps, "phases": phases,
        "fuse_overcurrent_factor": fuse_overcurrent_factor,
        "use_solar": use_solar, "solar_kwp": solar_kwp if use_solar else 0,
        "solar_source": _solar_source, "solar_tilt": _pvgis_tilt, "solar_aspect": _pvgis_aspect,
        "bat_install": bat_install, "sol_price": sol_price if use_solar else 0,
        "sol_install": sol_install if use_solar else 0, "sol_invest_total": sol_invest_total,
        "finance": finance, "loan_rate": loan_rate, "loan_years": loan_years,
        "efficiency": efficiency, "cycle_life": cycle_life, "energy_tax": energy_tax,
        "green_deduction": use_green_deduction, "green_owners": green_owners,
        "price_range": f"{df_prices['date'].min()} — {df_prices['date'].max()}",
        "price_days": int(df_prices["date"].nunique()),
        "address": _addr_snap,
        "weather_station": station_name if (use_heating_model and temps_data) else "",
    }

    # Future scenarios: computed ONCE here (not on every widget interaction)
    if all_results:
        _best_sim = max(all_results, key=lambda r: r["profit_life"])
        with st.spinner(t("computing_scenarios")):
            st.session_state["vol_arb"] = _compute_vol_benefits(_best_sim, price_rows, solar_config)

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
def _payback_text(payback):
    """Payback phrase; None (never pays back) gets its own text instead of '999 år'."""
    return t("payback_never") if payback is None else t("payback_text").format(years=payback)


def _fmt_payback(payback):
    return "—" if payback is None else f"{payback:.1f} {t('yr')}"


def _annual_cost(res):
    """Annualized investment cost: battery over its lifetime, solar over SOLAR_LIFETIME_YEARS.

    net_benefit_yr − _annual_cost(res), times the lifetime, equals profit_life.
    """
    sol_net = res.get("sol_invest_net", res["total_invest"] - res["invest"])
    life = max(res["lifetime"], 1e-9)
    return (res["invest"] + sol_net * min(1.0, life / SOLAR_LIFETIME_YEARS)) / life


def _vol_benefit_at(vol_arb, vol):
    """Yearly benefit at a volatility factor, interpolated between simulated levels."""
    levels = sorted(vol_arb)
    below = [v for v in levels if v <= vol]
    above = [v for v in levels if v > vol]
    if below and above:
        b, a = below[-1], above[0]
        frac = (vol - b) / (a - b)
        return vol_arb[b] * (1 - frac) + vol_arb[a] * frac
    return vol_arb[below[-1]] if below else vol_arb[levels[0]]


def _scenario_year_benefit(vol_arb, target_vol, yr):
    """Benefit in year `yr`: volatility ramps linearly from today to target over 10 years."""
    return _vol_benefit_at(vol_arb, 1.0 + (target_vol - 1.0) * min(yr, 10) / 10)


def _scenario_net(vol_arb, target_vol, res):
    """Net over the battery lifetime for a scenario — same accounting as profit_life."""
    life = res["lifetime"]
    total = 0.0
    yr = 1
    while yr - 1 < life:
        total += _scenario_year_benefit(vol_arb, target_vol, yr) * min(1.0, life - (yr - 1))
        yr += 1
    sol_net = res.get("sol_invest_net", res["total_invest"] - res["invest"])
    return _profit_over_life(0, life, res["invest"], sol_net) + total


if "all_results" in st.session_state:
    all_results = st.session_state["all_results"]
    solar_cfg = st.session_state.get("solar_cfg")
    price_rows = st.session_state.get("price_rows", [])

    if not all_results:
        st.warning(t("no_results"))
        st.stop()

    # Results were computed with the inputs snapshotted at simulation time. Use those
    # here (and in the PDF) so the shown numbers and the stated assumptions match.
    _si = st.session_state.get("sim_inputs", {})
    grid_operator = _si.get("grid_operator", grid_operator)
    fuse_amps = _si.get("fuse_amps", fuse_amps)
    phases = _si.get("phases", phases)
    fuse_overcurrent_factor = _si.get("fuse_overcurrent_factor", fuse_overcurrent_factor)
    use_solar = _si.get("use_solar", use_solar)
    solar_kwp = _si.get("solar_kwp", solar_kwp)
    bat_install = _si.get("bat_install", bat_install)
    sol_price = _si.get("sol_price", sol_price)
    sol_install = _si.get("sol_install", sol_install)
    sol_invest_total = _si.get("sol_invest_total", sol_invest_total)
    finance = _si.get("finance", finance)
    loan_rate = _si.get("loan_rate", loan_rate)
    loan_years = _si.get("loan_years", loan_years)
    if st.session_state.get("sim_sig") != _current_sig:
        st.warning(t("results_outdated"))

    # === RECOMMENDATION ===
    best_idx = max(range(len(all_results)), key=lambda i: all_results[i]["profit_life"])
    best = all_results[best_idx]

    _rec_fuse = best.get("fuse_amps", fuse_amps)
    if _rec_fuse > fuse_amps:
        _rec_fuse_label = t("rec_upgrade_fuse").format(fuse=_rec_fuse)
    elif _rec_fuse < fuse_amps:
        _rec_fuse_label = t("rec_downgrade_fuse").format(fuse=_rec_fuse)
    else:
        _rec_fuse_label = ""
    _rec_benefit = best["net_benefit_yr"]
    st.success(
        t("rec_success").format(
            label=best['label'], fuse_label=_rec_fuse_label,
            benefit=_rec_benefit, benefit_mo=_rec_benefit / 12,
            invest=best['total_invest'], payback_text=_payback_text(best['payback']),
            profit=best['profit_life'], lifetime=best['lifetime'],
        )
    )
    if best["profit_life"] <= 0:
        st.warning(t("rec_not_profitable"))
    if _si.get("green_deduction"):
        _gd_total = best.get("green_bat", 0) + best.get("green_sol", 0)
        if _gd_total > 0:
            st.info(t("green_deduction_info").format(
                total=f"{_gd_total:,.0f}", bat=f"{best.get('green_bat', 0):,.0f}",
                sol=f"{best.get('green_sol', 0):,.0f}", net=f"{best['total_invest']:,.0f}",
                gross=f"{best.get('gross_invest', best['total_invest']):,.0f}"))
        if not (use_solar and solar_kwp > 0):
            st.caption(t("green_no_battery_without_solar"))
    st.caption(t("horizon_note").format(solar_life=SOLAR_LIFETIME_YEARS))
    if _rec_fuse != fuse_amps:
        _fv = st.session_state.get("fuse_variants", {}).get(best["label"], [])
        _current_fuse_result = next((r for r in _fv if r["fuse_amps"] == fuse_amps), None)
        _extra_benefit = best["net_benefit_yr"] - _current_fuse_result["net_benefit_yr"] if _current_fuse_result else best["fuse_fee_delta_yr"]
        _change_word = t("fuse_upgrade_word") if _rec_fuse > fuse_amps else t("fuse_downgrade_word")
        st.info(
            t("fuse_change_info").format(
                change_word=_change_word, from_fuse=fuse_amps, to_fuse=_rec_fuse,
                fee_delta=best['fuse_fee_delta_yr'], extra=_extra_benefit,
            )
        )

    if fuse_overcurrent_factor > 0 and _rec_fuse == fuse_amps:
        _eff_a = fuse_amps * (1.0 + fuse_overcurrent_factor)
        _pb = 0.7 if phases == 3 else 1.0
        _extra_kw = fuse_amps * fuse_overcurrent_factor * 0.23 * phases * _pb
        st.info(t("fuse_overcurrent_no_upgrade").format(
            fuse=fuse_amps, effective=_eff_a, extra_kw=_extra_kw,
            factor=1.0 + fuse_overcurrent_factor))

    # Tariff recommendation (from best size)
    st.info(t("best_tariff_info").format(tariff=best['best_tariff']))

    # === EXPORT COMPARISON ===
    # Show what happens with vs without export for the recommended battery
    _current_export = best["config"].export_price_factor
    _alt_export = 1.0 if _current_export == 0 else 0.0
    _alt_label = t("export_compare_with") if _alt_export > 0 else t("export_compare_without")
    _alt_fee = 5.0 if _alt_export > 0 else 0.0

    def _run_export_comparison():
        """Simulate the recommended battery with the opposite export setting."""
        from batteri import BatteryConfig as _BC
        _alt_cfg = _BC(
            capacity_kwh=best["config"].capacity_kwh,
            max_charge_kw=best["config"].max_charge_kw,
            max_discharge_kw=best["config"].max_discharge_kw,
            efficiency=best["config"].efficiency,
            fuse_amps=best["config"].fuse_amps,
            phases=best["config"].phases,
            base_load_kw=best["config"].base_load_kw,
            scheduled_loads=best["config"].scheduled_loads,
            hourly_load_profile=best["config"].hourly_load_profile,
            seasonal_load_profile=best["config"].seasonal_load_profile,
            daily_load_override=best["config"].daily_load_override,
            flexible_loads=best["config"].flexible_loads,
            purchase_price=best["config"].purchase_price,
            installation_cost=best["config"].installation_cost,
            cycle_life=best["config"].cycle_life,
            calendar_life_years=best["config"].calendar_life_years,
            export_price_factor=_alt_export,
            export_fee_ore=_alt_fee,
            fuse_overcurrent_factor=best["config"].fuse_overcurrent_factor,
        )
        _alt_result = simulate(price_rows, _alt_cfg, tariff=best["tariff"],
                                solar=solar_cfg)
        _alt_d = len(set(s.date for s in _alt_result.slots))
        _alt_yrs = _alt_d / 365.25
        _alt_arb = _alt_result.net_profit_sek / _alt_d * 365.25 if _alt_d > 0 else 0
        _alt_existing_solar = bool(solar_cfg) and sol_invest_total == 0
        if _alt_d > 0 and isinstance(best["tariff"], EffektTariff):
            _alt_arb += effekt_savings(_alt_result, best["tariff"], _alt_cfg, _alt_d,
                                       solar_in_baseline=_alt_existing_solar)
        _alt_cycles = _alt_result.num_cycles / _alt_yrs if _alt_yrs > 0 else 0

        # Solar self-consumption for alt (counted only when solar is part of the investment,
        # exactly like the main recommendation)
        _alt_solar_self = 0
        if solar_cfg and _alt_d > 0 and sol_invest_total > 0:
            _alt_solar_self = solar_direct_use(_alt_result, _alt_cfg)[1] / _alt_yrs
        # Existing panels + export: export they'd earn without a battery isn't battery value
        if _alt_d > 0 and _alt_existing_solar and _alt_export > 0:
            _alt_arb -= baseline_export_revenue(price_rows, _alt_cfg, best["tariff"],
                                                solar_cfg) / _alt_yrs
        _alt_life = min(best["config"].cycle_life / _alt_cycles if _alt_cycles > 0 else 15, 15)
        _alt_benefit = _alt_arb + _alt_solar_self - best["fuse_fee_delta_yr"]
        return {
            "benefit": _alt_benefit,
            "cycles": _alt_cycles,
            "life": _alt_life,
            "profit": _profit_over_life(_alt_benefit, _alt_life, best["invest"],
                                        best.get("sol_invest_net", best["total_invest"] - best["invest"])),
            "export_kwh": _alt_result.total_grid_export_kwh / _alt_yrs if _alt_yrs > 0 else 0,
            "export_rev": _alt_result.total_export_revenue / _alt_yrs if _alt_yrs > 0 else 0,
        }

    with st.expander(t("export_compare_expander").format(label=_alt_label)):
        # Only simulated on request (and cached until the next simulation run) —
        # not re-run on every widget interaction.
        _ec = st.session_state.get("export_cmp")
        if _ec is None and st.button(t("export_compare_button"), key="export_cmp_btn"):
            with st.spinner(t("export_simulating")):
                _ec = _run_export_comparison()
            st.session_state["export_cmp"] = _ec
        if _ec is not None:
            _alt_benefit, _alt_cycles, _alt_life = _ec["benefit"], _ec["cycles"], _ec["life"]
            _alt_profit = _ec["profit"]
            _cur_label = t("export_mode_zero") if _current_export == 0 else t("export_mode_with")
            _alt_mode_label = t("export_mode_with") if _alt_export > 0 else t("export_mode_zero")

            st.dataframe(pd.DataFrame([
                {
                    t("export_col_mode"): _cur_label + t("export_col_selected"),
                    t("export_col_savings_yr"): f"{best['net_benefit_yr']:,.0f} kr",
                    t("export_col_cycles_yr"): f"{best['cycles_yr']:.0f}",
                    t("export_col_lifetime"): f"{best['lifetime']:.0f} {t('yr')}",
                    t("export_col_net"): f"{best['profit_life']:+,.0f} kr",
                },
                {
                    t("export_col_mode"): _alt_mode_label,
                    t("export_col_savings_yr"): f"{_alt_benefit:,.0f} kr",
                    t("export_col_cycles_yr"): f"{_alt_cycles:.0f}",
                    t("export_col_lifetime"): f"{_alt_life:.0f} {t('yr')}",
                    t("export_col_net"): f"{_alt_profit:+,.0f} kr",
                },
            ]), use_container_width=True, hide_index=True)

            if _alt_export > 0:
                st.caption(t("export_revenue_caption").format(
                    kwh=_ec["export_kwh"], rev=_ec["export_rev"]))
            _diff = _alt_profit - best["profit_life"]
            if _diff > 0:
                st.success(t("export_better").format(label=_alt_mode_label, diff=_diff))
            else:
                st.info(t("export_worse").format(label=_cur_label, diff=-_diff))

        # Tipping point analysis
        _eff = best["config"].efficiency
        _fee = 5.0  # öre export fee
        _tax_grid = 50.0  # öre (energiskatt + nätavgift, approximate)
        # Break-even: buy_spot + tax_grid = (sell_spot - fee) × efficiency
        # buy_spot + tax_grid = sell_spot × eff - fee × eff
        # For arbitrage export to break even: sell/buy ratio must exceed threshold
        # buy at (spot_low + tax_grid), sell at (spot_high × factor - fee)
        # break-even when: (spot_high - fee) × eff > spot_low + tax_grid
        # minimum spread: spot_high - spot_low > (spot_low + tax_grid) / eff - spot_low + fee
        _typical_low = 30  # öre, typical night price
        _min_high = (_typical_low + _tax_grid) / _eff + _fee
        _min_spread = _min_high - _typical_low
        st.caption(
            t("tipping_point_caption").format(
                low_kr=_typical_low / 100, min_high_kr=_min_high / 100,
                eff=_eff, spread_kr=_min_spread / 100,
            )
        )

    # Self-consumption optimization (when using SEK/kWh mode)
    if _pricing_mode == "sek_kwh":
        # Find smallest battery where grid export is near zero
        _sorted_by_cap = sorted(all_results, key=lambda r: r["capacity"])
        _zero_export = None
        for r in _sorted_by_cap:
            if r["grid_export_yr"] < 10:  # less than 10 kWh/yr = effectively zero
                _zero_export = r
                break
        if _zero_export:
            st.success(
                t("self_consumption_zero").format(
                    label=_zero_export['label'],
                    export=_zero_export['grid_export_yr'],
                    invest=_zero_export['total_invest'],
                    benefit=_zero_export['net_benefit_yr'],
                )
            )
        else:
            _min_export = min(all_results, key=lambda r: r["grid_export_yr"])
            st.info(
                t("self_consumption_lowest").format(
                    label=_min_export['label'],
                    export=_min_export['grid_export_yr'],
                    invest=_min_export['total_invest'],
                )
            )

        # Show export vs battery size chart
        _cap_list = [r["capacity"] for r in _sorted_by_cap]
        _export_list = [r["grid_export_yr"] for r in _sorted_by_cap]
        _benefit_list = [r["net_benefit_yr"] for r in _sorted_by_cap]
        fig_self = go.Figure()
        fig_self.add_trace(go.Bar(x=_cap_list, y=_export_list, name=t("self_consumption_export_bar"),
                                   marker_color="indianred"))
        fig_self.add_trace(go.Scatter(x=_cap_list, y=_benefit_list, name=t("self_consumption_savings_line"),
                                       yaxis="y2", mode="lines+markers", marker_color="seagreen"))
        fig_self.update_layout(
            title=t("self_consumption_title"),
            xaxis_title=t("self_consumption_xaxis"),
            yaxis_title=t("self_consumption_yaxis"),
            yaxis2=dict(title=t("self_consumption_yaxis2"), overlaying="y", side="right"),
            height=400,
        )
        st.plotly_chart(fig_self, use_container_width=True)

    # === LUFT-LUFT CONTRIBUTION (separate from main investment) ===
    if st.session_state.get("use_aa", False) and best.get("aa_flex_kwh_yr", 0) > 0:
        with st.expander(t("aa_expander"), expanded=False):
            _aa_flex = best["aa_flex_kwh_yr"]
            _total_flex = best["total_flex_kwh_yr"]
            _other_flex = _total_flex - _aa_flex
            _avg_ore = 60  # approximate average price
            _aa_value_kr = _aa_flex * _avg_ore / 100

            col_aaf1, col_aaf2, col_aaf3 = st.columns(3)
            with col_aaf1:
                st.metric(t("aa_solar_surplus"), f"{_aa_flex:,.0f} kWh/{t('yr')}",
                          help=t("aa_solar_surplus_help"))
            with col_aaf2:
                st.metric(t("aa_avoided_export"), f"{_aa_value_kr:,.0f} kr/{t('yr')}",
                          help=t("aa_avoided_export_help"))
            with col_aaf3:
                st.metric(t("aa_other_flex"), f"{_other_flex:,.0f} kWh/{t('yr')}",
                          help=t("aa_other_flex_help"))

            st.caption(
                t("aa_caption").format(aa_flex=_aa_flex, total_flex=_total_flex)
            )

    # === PDF REPORT ===
    # Calculate financing for report
    _report_loan_cost = 0
    _report_net = best["net_benefit_yr"] / 12
    _report_debt_left = None
    _report_net_life_fin = None
    if loan_rate > 0 and loan_years > 0:
        _ls_rep = loan_schedule(best["total_invest"], loan_rate, loan_years, best["lifetime"])
        _report_loan_cost = _ls_rep["monthly_payment"]
        _report_net = best["net_benefit_yr"] / 12 - _report_loan_cost
        _report_debt_left = _ls_rep["balance_at_horizon"]
        _report_net_life_fin = best["profit_life"] - _ls_rep["interest_in_horizon"]

    # Future scenarios (simulated once at simulation time, see _compute_vol_benefits)
    _vol_arb = st.session_state.get("vol_arb") or {1.0: best["net_benefit_yr"]}
    scenario_results = {}
    for _sk, _svf in FUTURE_SCENARIOS:
        scenario_results[t(_sk)] = {
            "arb_yr": _vol_benefit_at(_vol_arb, _svf), "vol": _svf, "desc": t(f"{_sk}_desc"),
            "lifetime_profit": _scenario_net(_vol_arb, _svf, best),
        }

    # PDF is generated once per simulation (cached), with the inputs snapshotted at
    # simulation time (_si) — not with whatever the widgets show now.
    _pdf_bytes = st.session_state.get("_pdf_cache")
    if _pdf_bytes is None:
        try:
            # The PDF report is always in Swedish (bank document): use Swedish scenario labels
            _pdf_scen = {STRINGS[_sk]["sv"]: dict(scenario_results[t(_sk)], desc=STRINGS[f"{_sk}_desc"]["sv"])
                         for _sk, _svf in FUTURE_SCENARIOS}
            _pdf_bytes = bytes(generate_report(
                address=_si.get("address", ""),
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
                debt_at_battery_end=_report_debt_left,
                financed_lifetime_net=_report_net_life_fin,
                price_data_range=_si.get("price_range", ""),
                price_data_days=_si.get("price_days", 0),
                weather_station=_si.get("weather_station", ""),
                all_results=[{"label": r["label"], "total_benefit_yr": r["net_benefit_yr"],
                               "total_invest": r["total_invest"], "payback": r["payback"],
                               "profit_life": r["profit_life"]} for r in all_results],
                future_scenarios=_pdf_scen,
                phases=phases,
                efficiency=_si.get("efficiency"),
                cycle_life=_si.get("cycle_life", 8000),
                energy_tax=_si.get("energy_tax", 45.0),
                solar_source=_si.get("solar_source") or "",
                solar_tilt=_si.get("solar_tilt"),
                solar_aspect=_si.get("solar_aspect"),
                location=_si.get("address", ""),
                green_deduction_battery=best.get("green_bat", 0),
                green_deduction_solar=best.get("green_sol", 0),
                solar_lifetime_years=SOLAR_LIFETIME_YEARS,
            ))
            st.session_state["_pdf_cache"] = _pdf_bytes
        except Exception as e:
            st.warning(t("pdf_error").format(error=e))
    if _pdf_bytes is not None:
        st.download_button(
            t("download_pdf"),
            data=_pdf_bytes,
            file_name=f"energikalkyl_{date.today().isoformat()}.pdf",
            mime="application/pdf",
        )

    # === EXPORT FOR SIMULATOR ===
    # Snapshot session values now (in the script thread): the export is built lazily by
    # the download button in a separate thread, where st.session_state isn't available.
    _exp_ss = {k: st.session_state.get(k) for k in (
        "vattenfall_hourly", "df_prices", "tibber_solar_hourly", "scheduled_loads",
        "flexible_loads", "tibber_home", "price_rows", "solar_cfg")}

    def _build_simulator_export():
        """Build JSON export dict for energy-scheduler-sim."""
        export = {"source": "energikalkyl", "exported": date.today().isoformat()}

        # Consumption: hourly data grouped by date
        vf_hourly = (_exp_ss["vattenfall_hourly"] or [])
        if vf_hourly:
            cons = {}
            for rec in vf_hourly:
                d = rec["date"]
                if d not in cons:
                    cons[d] = [0.0] * 24
                h = int(rec["hour"].split(":")[0]) if isinstance(rec["hour"], str) else int(rec["hour"])
                cons[d][h] = round(rec["kwh"], 4)
            export["consumption"] = dict(sorted(cons.items()))

        # Prices: hourly SEK/kWh (excl. VAT) grouped by date. Quarter-hour rows
        # (since 2025-10-01) are averaged per hour, like simulate()'s to_hourly
        # (previously the last quarter of each hour overwrote the others).
        _df = _exp_ss["df_prices"]
        if _df is not None and len(_df) > 0:
            _psum, _pcnt = {}, {}
            for _, row in _df.iterrows():
                d = str(row["date"])
                if d not in _psum:
                    _psum[d], _pcnt[d] = [0.0] * 24, [0] * 24
                h = int(str(row["hour"]).split(":")[0])
                _psum[d][h] += float(row["sek_per_kwh"])
                _pcnt[d][h] += 1
            prices = {d: [round(_psum[d][h] / _pcnt[d][h], 4) if _pcnt[d][h] else 0.0 for h in range(24)]
                      for d in _psum}
            export["prices"] = dict(sorted(prices.items()))
            # Zone from price data
            if "zone" in _df.columns:
                export["zone"] = str(_df["zone"].iloc[0])

        # Weather: hourly °C grouped by date
        try:
            _temps = temps_data
        except NameError:
            _temps = {}
        if _temps:
            weather = {}
            for d, hourly in _temps.items():
                weather[d] = [0.0] * 24
                for h, temp_c in hourly:
                    weather[d][h] = round(temp_c, 1)
            export["weather"] = dict(sorted(weather.items()))

        # Solar: hourly kW grouped by date
        solar_hourly = (_exp_ss["tibber_solar_hourly"] or {})
        if solar_hourly:
            solar = {}
            for key, kw in solar_hourly.items():
                # key format: "YYYY-MM-DD HH:00"
                parts = key.split(" ")
                if len(parts) == 2:
                    d = parts[0]
                    h = int(parts[1].split(":")[0])
                    if d not in solar:
                        solar[d] = [0.0] * 24
                    solar[d][h] = round(kw, 4)
            export["solar"] = dict(sorted(solar.items()))

        # Battery (from recommended config)
        _bcfg = best.get("config")
        if _bcfg:
            export["battery"] = {
                "capacity_kwh": _bcfg.capacity_kwh,
                "max_charge_kw": _bcfg.max_charge_kw,
                "max_discharge_kw": _bcfg.max_discharge_kw,
                "efficiency": _bcfg.efficiency,
                "min_soc": round(_bcfg.min_soc * 100),
                "max_soc": round(_bcfg.max_soc * 100),
            }
            export["grid"] = {
                "fuse_amps": _bcfg.fuse_amps,
                "phases": _bcfg.phases,
                "phase_balance_factor": _bcfg.phase_balance_factor,
            }

        # EV (from scheduled loads)
        for _sl in (_exp_ss["scheduled_loads"] or []):
            if _sl.get("power", 0) > 0 and ("bil" in _sl["name"].lower() or "ev" in _sl["name"].lower()):
                _start_h, _end_h = _sl["start"], _sl["end"]
                if _start_h > _end_h:  # wraps midnight: e.g. 18→7 means home 18-24 + 0-7
                    _home_hrs = f"0-{_end_h},{_start_h}-24"
                else:
                    _home_hrs = f"{_start_h}-{_end_h}"
                export["ev"] = {
                    "capacity_kwh": 77,
                    "target_soc": 80,
                    "daily_kwh": _sl.get("daily_kwh", 30.0),
                    "home_hours": _home_hrs,
                }
                break

        # Calibration
        try:
            _hc = heating_config
            _ev_annual = sum(sl.daily_kwh * 365 for sl in scheduled_loads
                            if "bil" in sl.name.lower() or "ev" in sl.name.lower()) if scheduled_loads else 0
            export["calibration"] = {
                "h_loss": round(_hc.h_loss, 4),
                "base_load_kw": round(non_heat_base, 2),
                "dhw_kwh_per_day": round(_hc.dhw_kwh_per_day, 1),
                "cop_base": round(_hc.cop_base, 3),
                "cop_slope": round(_hc.cop_slope, 4),
                "hp_max_heat_kw": round(_hc.hp_max_heat_kw, 1),
                "ev_annual_kwh": round(_ev_annual),
            }
        except (NameError, AttributeError):
            pass  # heating model not used

        # Flexible loads
        _fl_raw = (_exp_ss["flexible_loads"] or [])
        if _fl_raw:
            export["flex_loads"] = [
                {
                    "name": fl["name"],
                    "power_kw": fl["power"],
                    "daily_kwh": fl["daily"],
                    "start_month": fl["sm"],
                    "end_month": fl["em"],
                }
                for fl in _fl_raw if fl.get("power", 0) > 0
            ]

        # Location
        home = (_exp_ss["tibber_home"] or {})
        if home.get("latitude") and home.get("longitude"):
            export["location"] = {
                "lat": round(home["latitude"], 2),
                "lon": round(home["longitude"], 2),
                "city": home.get("city", ""),
            }
        elif home.get("city"):
            _city_coords = SWEDISH_CITIES.get(home["city"])
            if _city_coords:
                export["location"] = {
                    "lat": round(_city_coords[0], 2),
                    "lon": round(_city_coords[1], 2),
                    "city": home["city"],
                }

        # Calculator result + the exact hourly inputs it was computed from, for
        # the simulator's "Validate calculator" panel (energy-scheduler-sim runs
        # the same hours through the controller firmware). One simulate() call:
        # it refreshes the config's smart-load (EV) schedule for the chosen
        # tariff — the tariff sweep leaves the last tariff's schedule behind.
        _price_rows = _exp_ss.get("price_rows")
        if _bcfg is not None and _price_rows:
            _tf = best.get("tariff")
            _r = simulate(_price_rows, _bcfg, tariff=_tf, solar=_exp_ss.get("solar_cfg"))
            _keys = ("hour", "spot", "buy_ore", "load_kw", "ev_kw", "solar_kw", "room_kw",
                     "in_kwh", "out_kwh", "solar_in_kwh", "export_kwh", "net_sek")
            _hourly = {}
            for _s in _r.slots:
                _h = int(_s.hour.split(":")[0])
                _m = int(_s.date.split("-")[1])
                _ev = sum(_bcfg._scheduled_kw(_i, _sl, _h, _s.date)
                          for _i, _sl in enumerate(_bcfg.scheduled_loads))
                _row = (_h, round(_s.sek_per_kwh, 5), round(_s.total_cost_ore, 3),
                        round(_bcfg.total_load_kw(_h, _m, _s.date), 4), round(_ev, 4),
                        round(_s.solar_kw, 4), round(_bcfg.available_charge_kw(_h, _m, _s.date), 4),
                        round(_s.energy_kwh, 4) if _s.action == "charge" else 0.0,
                        round(_s.energy_kwh, 4) if _s.action == "discharge" else 0.0,
                        round(_s.solar_charge_kwh, 4), round(_s.grid_export_kwh, 4),
                        round(_s.saving_sek - _s.cost_sek + _s.export_revenue_sek, 4))
                _d = _hourly.setdefault(_s.date, {k: [] for k in _keys})
                for _k, _v in zip(_keys, _row):
                    _d[_k].append(_v)
            _days = len(_hourly)
            if _days:
                _dates = sorted(_hourly)
                export["calculator"] = {
                    "version": 1,
                    "label": best.get("label"),
                    "tariff": best.get("best_tariff"),
                    "fuse_amps": _bcfg.fuse_amps,
                    "phases": _bcfg.phases,
                    "phase_balance_factor": _bcfg.phase_balance_factor,
                    "grid_max_kw": round(_bcfg.grid_max_kw, 4),
                    "battery": {
                        "capacity_kwh": _bcfg.capacity_kwh,
                        "max_charge_kw": _bcfg.max_charge_kw,
                        "max_discharge_kw": _bcfg.max_discharge_kw,
                        "efficiency": _bcfg.efficiency,
                        "min_soc": round(_bcfg.min_soc * 100, 2),
                        "max_soc": round(_bcfg.max_soc * 100, 2),
                    },
                    "export": {
                        "enabled": _bcfg.export_price_factor > 0,
                        "price_factor": _bcfg.export_price_factor,
                        "fee_ore": _bcfg.export_fee_ore,
                    },
                    "spot_vat_factor": _bcfg.spot_vat_factor,
                    # EV/scheduled loads are inside load_kw (ev_kw = their part);
                    # with a measured hourly/seasonal profile they are part of
                    # the profile and ev_kw is 0.
                    "ev_in_profile": not _bcfg.scheduled_loads,
                    "period": {"first": _dates[0], "last": _dates[-1], "days": _days},
                    "result": {
                        "net_sek": round(_r.net_profit_sek, 2),
                        "net_sek_per_year": round(_r.net_profit_sek / _days * 365.25, 2),
                        "charged_kwh": round(_r.total_charged_kwh, 2),
                        "discharged_kwh": round(_r.total_discharged_kwh, 2),
                        "charge_cost_sek": round(_r.total_charge_cost, 2),
                        "discharge_value_sek": round(_r.total_discharge_value, 2),
                        "export_revenue_sek": round(_r.total_export_revenue, 2),
                        "solar_charge_kwh": round(_r.total_solar_charge_kwh, 2),
                        "grid_export_kwh": round(_r.total_grid_export_kwh, 2),
                        "cycles": round(_r.num_cycles, 1),
                        "arb_yr": round(best.get("arb_yr", 0), 2),
                        "effekt_saving_yr": round(best.get("effekt_saving_yr", 0), 2),
                        "solar_self_yr": round(best.get("solar_self_yr", 0), 2),
                        "net_benefit_yr": round(best.get("net_benefit_yr", 0), 2),
                    },
                    "hourly": _hourly,
                }

        return export

    st.download_button(
        t("export_simulator_json"),
        # Built only when clicked (callable), not on every rerun
        data=lambda: json.dumps(_build_simulator_export(), ensure_ascii=False, indent=2),
        file_name=f"energikalkyl-export-{date.today().isoformat()}.json",
        mime="application/json",
    )

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
                comp = {t("scenario_battery"): sd["label"]}
                if normal_years:
                    vals = [sd[y] for y in normal_years if y in sd]
                    if vals:
                        avg_normal = sum(vals) / len(vals)
                        comp[t("scenario_normal").format(years=', '.join(normal_years))] = f"{avg_normal:,.0f} {t('kr_yr')}"
                        comp[t("scenario_normal_monthly")] = f"{avg_normal/12:,.0f}"
                if high_years:
                    vals = [sd[y] for y in high_years if y in sd]
                    if vals:
                        avg_high = sum(vals) / len(vals)
                        comp[t("scenario_high").format(years=', '.join(high_years))] = f"{avg_high:,.0f} {t('kr_yr')}"
                        comp[t("scenario_high_monthly")] = f"{avg_high/12:,.0f}"
                comp[t("scenario_avg_all")] = f"{sd['all']:,.0f} {t('kr_yr')}"
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
                    name=f"{y}" + (f" {t('scenario_partial')}" if y in partial_years else ""),
                    marker_color=colors_yr.get(y, "#9b59b6"),
                    hovertemplate="%{x}<br>" + y + ": %{y:,.0f} " + t("kr_yr") + "<extra></extra>",
                ))
            fig_scen.update_layout(
                barmode="group", yaxis_title=t("scenario_yaxis"), height=400,
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
                    t("scenario_info").format(
                        label=best['label'],
                        normal_years=', '.join(normal_years),
                        avg_n=f"{avg_n:,.0f}", avg_n_mo=f"{avg_n/12:,.0f}",
                        high_years=', '.join(high_years),
                        avg_h=f"{avg_h:,.0f}", avg_h_mo=f"{avg_h/12:,.0f}",
                    )
                )

    # === COMPARISON: annualized cost vs annualized savings ===
    labels = [r["label"] for r in all_results]
    st.subheader(t("compare_all_header"))
    st.caption(t("compare_all_caption"))

    fig_annual = go.Figure()
    fig_annual.add_trace(go.Bar(
        x=labels,
        y=[_annual_cost(r) for r in all_results],
        name=t("invest_cost_trace"),
        marker_color="#e74c3c",
        hovertemplate="%{x}<br>" + t("cost_hover") + ": %{y:,.0f} " + t("kr_yr") + "<extra></extra>",
    ))
    fig_annual.add_trace(go.Bar(
        x=labels,
        y=[r["net_benefit_yr"] for r in all_results],
        name=t("savings_trace"),
        marker_color="#2ecc71",
        hovertemplate="%{x}<br>" + t("saving_hover") + ": %{y:,.0f} " + t("kr_yr") + "<extra></extra>",
    ))
    fig_annual.update_layout(barmode="group", yaxis_title=t("kr_yr"), height=350,
                              margin=dict(l=0, r=0, t=30, b=0),
                              legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig_annual, use_container_width=True)

    # === COMPARISON TABLE ===
    def _fuse_label(r):
        f = r.get("fuse_amps", fuse_amps)
        return f" ({f:.0f}A)" if f != fuse_amps else ""
    st.dataframe(pd.DataFrame([{
        t("col_battery"): r["label"] + _fuse_label(r),
        t("col_savings_yr"): f"{r['net_benefit_yr']:,.0f} kr",
        t("col_cost_yr"): f"{_annual_cost(r):,.0f} kr",
        t("col_net_yr"): f"{r['net_benefit_yr'] - _annual_cost(r):,.0f} kr",
        t("col_net_mo"): f"{(r['net_benefit_yr'] - _annual_cost(r)) / 12:,.0f} kr",
        t("col_investment"): f"{r['total_invest']:,.0f} kr",
        t("col_lifetime"): f"{r['lifetime']:.0f} {t('yr')}",
        t("col_tariff"): r["best_tariff"],
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

    # LFP degradation: ~1%/year capacity fade (well-established in literature)
    LFP_FADE_PER_YEAR = 0.01

    fig_life = go.Figure()
    colors = ["#3498db", "#2ecc71", "#e74c3c"]
    years = list(range(0, 16))
    for i, r in enumerate(_show):
        # Solid line: degradation-adjusted cashflow
        cum = [-r["total_invest"]]
        for yr in range(1, 16):
            soh = 1 - LFP_FADE_PER_YEAR * yr
            cum.append(cum[-1] + r["net_benefit_yr"] * soh)
        is_best = r["label"] == best["label"]
        fig_life.add_trace(go.Scatter(
            x=years, y=cum, mode="lines+markers", name=r["label"],
            line=dict(width=4 if is_best else 2, color=colors[i % len(colors)]),
            hovertemplate=(
                f"{r['label']}<br>"
                f"{t('xaxis_year')} %{{x}}: %{{y:,.0f}} kr<br>"
                "SoH: %{customdata:.0f}%<extra></extra>"
            ),
            customdata=[100 - yr * LFP_FADE_PER_YEAR * 100 for yr in years],
        ))
    fig_life.add_hline(y=0, line_color="gray", line_width=1,
                        annotation_text=t("repaid_annotation"), annotation_position="bottom right")
    fig_life.update_layout(
        xaxis_title=t("xaxis_year"), yaxis_title=t("yaxis_cum_cashflow"), height=400,
        margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02),
    )
    st.plotly_chart(fig_life, use_container_width=True)
    st.caption(t("degradation_caption"))

    # === FINANCING PERSPECTIVE ===
    st.divider()
    st.subheader(t("financing_header"))

    if finance in ("mortgage", "other_loan") and loan_rate > 0 and loan_years > 0:
        loan_label = t("mortgage") if finance == "mortgage" else t("fin_loan_label")
        st.caption(t("fin_caption").format(loan=loan_label.lower(), rate=loan_rate, years=loan_years))

        fin_data = []
        for r in all_results:
            total = r["total_invest"]
            lifetime = r["lifetime"]
            _ls = loan_schedule(total, loan_rate, loan_years, lifetime)
            m_cost = _ls["monthly_payment"]
            m_saving = r["net_benefit_yr"] / 12
            net = m_saving - m_cost
            # Net over the battery lifetime: profit_life already charges the whole investment
            # (solar pro rata), so financing only adds the interest paid in that period. The
            # debt still owed when the battery is worn out is part of that investment.
            net_lifetime = r["profit_life"] - _ls["interest_in_horizon"]
            fin_data.append({"label": r["label"], "total": total,
                             "monthly_cost": m_cost, "monthly_saving": m_saving,
                             "net": net, "net_lifetime": net_lifetime,
                             "lifetime": lifetime,
                             "debt_left": _ls["balance_at_horizon"]})

        # Chart
        fig_fin = go.Figure()
        fig_fin.add_trace(go.Bar(
            x=[d["label"] for d in fin_data],
            y=[d["monthly_saving"] for d in fin_data],
            name=t("fin_lower_cost_trace"), marker_color="#2ecc71",
            hovertemplate="%{x}<br>" + t("fin_saving_hover") + ": %{y:,.0f} " + t("kr_month") + "<extra></extra>",
        ))
        fig_fin.add_trace(go.Bar(
            x=[d["label"] for d in fin_data],
            y=[-d["monthly_cost"] for d in fin_data],
            name=t("fin_loan_cost_trace").format(loan=loan_label), marker_color="#e74c3c",
            hovertemplate="%{x}<br>" + loan_label + ": %{y:,.0f} " + t("kr_month") + "<extra></extra>",
        ))
        fig_fin.add_trace(go.Scatter(
            x=[d["label"] for d in fin_data],
            y=[d["net"] for d in fin_data],
            mode="markers+text", name=t("fin_net_trace"),
            marker=dict(size=14, color="#3498db", symbol="diamond"),
            text=[f"+{d['net']:,.0f}" if d["net"] >= 0 else f"{d['net']:,.0f}" for d in fin_data],
            textposition="top center",
            hovertemplate="%{x}<br><b>" + t("fin_net_hover") + ": %{y:,.0f} " + t("kr_month") + "</b><extra></extra>",
        ))
        fig_fin.update_layout(barmode="relative", yaxis_title=t("yaxis_kr_month"), height=400,
                               margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02))
        st.plotly_chart(fig_fin, use_container_width=True)

        st.dataframe(pd.DataFrame([{
            t("col_battery"): d["label"],
            t("col_investment"): f"{d['total']:,.0f} kr",
            t("col_loan_per_mo").format(loan=loan_label): f"{d['monthly_cost']:,.0f} kr",
            t("col_savings_mo"): f"{d['monthly_saving']:,.0f} kr",
            t("col_cashflow_mo"): f"{d['net']:+,.0f} kr",
            t("col_lifetime"): f"{d['lifetime']:.0f} {t('yr')}",
            t("col_debt_left"): f"{d['debt_left']:,.0f} kr",
            t("col_net_lifetime"): f"{d['net_lifetime']:+,.0f} kr",
        } for d in fin_data]), use_container_width=True, hide_index=True)
        if loan_years > min(d["lifetime"] for d in fin_data):
            st.caption(t("fin_debt_caption").format(years=loan_years))

        best_fin = max(fin_data, key=lambda d: d["net_lifetime"])
        profitable = [d for d in fin_data if d["net_lifetime"] > 0]
        if len(profitable) == len(fin_data):
            st.success(t("fin_all_profitable").format(
                label=best_fin['label'],
                net_mo=f"{best_fin['net']:,.0f}",
                net_life=f"{best_fin['net_lifetime']:,.0f}",
                lifetime=f"{best_fin['lifetime']:.0f}"))
        elif profitable:
            st.info(t("fin_best_result").format(
                label=best_fin['label'],
                net_mo=f"{best_fin['net']:,.0f}",
                net_life=f"{best_fin['net_lifetime']:,.0f}",
                lifetime=f"{best_fin['lifetime']:.0f}"))
        else:
            st.warning(t("fin_none_profitable"))
    else:
        # Eget kapital — show simple cashflow over time for recommended battery
        st.caption(t("fin_cash_caption"))

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
                hovertemplate=f"{r['label']}<br>{t('xaxis_year')} %{{x}}: %{{y:,.0f}} kr<extra></extra>",
            ))
        fig_cf.add_hline(y=0, line_color="gray", line_width=1)
        fig_cf.update_layout(xaxis_title=t("xaxis_year"), yaxis_title=t("yaxis_cum_sek"), height=400,
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
        st.caption(t("fuse_caption").format(
                       fuse=f"{fuse_amps:.0f}",
                       fee=f"{_base_fee:,.0f}",
                       label=best['label']))
        if fuse_overcurrent_factor > 0:
            _eff_amps_info = fuse_amps * (1.0 + fuse_overcurrent_factor)
            _phase_bal = 0.7 if phases == 3 else 1.0
            _eff_kw = _eff_amps_info * 0.23 * phases * _phase_bal
            _nom_kw = fuse_amps * 0.23 * phases * _phase_bal
            st.info(t("fuse_overcurrent_sim_note").format(
                fuse=fuse_amps, effective=_eff_amps_info, nom_kw=_nom_kw, eff_kw=_eff_kw,
                extra_kw=_eff_kw - _nom_kw, factor=1.0 + fuse_overcurrent_factor))

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
        fuse_labels = [f"{fc['fuse']:.0f}A" + (f" {t('fuse_current')}" if fc["current"] else "") + (" ★" if fc["optimal"] and not fc["current"] else "") for fc in fuse_comparison]
        fig_fuse.add_trace(go.Bar(
            x=fuse_labels,
            y=[fc["net_yr"] for fc in fuse_comparison],
            name=t("fuse_net_savings"),
            marker_color=["#2ecc71" if fc["optimal"] else "#3498db" for fc in fuse_comparison],
            hovertemplate="%{x}<br>" + t("fuse_col_net") + ": %{y:,.0f} " + t("kr_yr") + "<extra></extra>",
        ))
        fig_fuse.add_trace(go.Bar(
            x=fuse_labels,
            y=[-fc.get("extra_fee_yr", 0) for fc in fuse_comparison],
            name=t("fuse_extra_cost"),
            marker_color="#e74c3c",
            hovertemplate="%{x}<br>" + t("fuse_col_extra_sub") + ": %{y:,.0f} " + t("kr_yr") + "<extra></extra>",
        ))
        fig_fuse.update_layout(barmode="relative", yaxis_title=t("kr_yr"), height=350,
                                margin=dict(l=0, r=0, t=30, b=0),
                                legend=dict(orientation="h", y=1.02))
        st.plotly_chart(fig_fuse, use_container_width=True)

        # Table
        _current_net = next((fc["net_yr"] for fc in fuse_comparison if fc["current"]), 0)
        st.dataframe(pd.DataFrame([{
            t("fuse_col_fuse"): f"{fc['fuse']:.0f}A" + (f" {t('fuse_col_current')}" if fc["current"] else "") + (f" {t('fuse_col_optimal')}" if fc["optimal"] and not fc["current"] else ""),
            t("fuse_col_subscription"): f"{fc['fee_yr']:,.0f} {t('kr_yr')}",
            t("fuse_col_gross_savings"): f"{fc['benefit_yr']:,.0f} {t('kr_yr')}",
            t("fuse_col_extra_sub"): f"{fc.get('extra_fee_yr', 0):+,.0f} {t('kr_yr')}" if not fc["current"] else "\u2014",
            t("fuse_col_net"): f"{fc['net_yr']:,.0f} {t('kr_yr')} ({fc['net_yr']/12:,.0f} {t('kr_month')})",
            t("fuse_col_vs_current"): f"{fc['net_yr'] - _current_net:+,.0f} {t('kr_yr')}" if not fc["current"] else "\u2014",
        } for fc in fuse_comparison]), use_container_width=True, hide_index=True)

        # Recommendation
        best_fuse = max(fuse_comparison, key=lambda fc: fc["net_yr"])
        if not best_fuse["current"]:
            extra = best_fuse["net_yr"] - _current_net
            st.success(t("fuse_best_net").format(
                fuse=f"{best_fuse['fuse']:.0f}",
                extra=f"{extra:+,.0f}",
                current=f"{fuse_amps:.0f}",
                fee=f"{best_fuse.get('extra_fee_yr', 0):+,.0f}"))
        else:
            upgrades = [fc for fc in fuse_comparison if not fc["current"]]
            if upgrades:
                next_up = upgrades[0]
                st.info(t("fuse_current_best").format(
                    fuse=f"{fuse_amps:.0f}",
                    next_fuse=f"{next_up['fuse']:.0f}",
                    fee=f"{next_up.get('extra_fee_yr', 0):,.0f}"))

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
    col_d1.metric(t("lower_cost"), f"{per_year/12:,.0f} {t('kr_month')}")
    col_d2.metric(t("per_year"), f"{per_year:,.0f} {t('kr_yr')}")
    col_d3.metric(t("payback"), _fmt_payback(sel['payback']))
    col_d4.metric(t("cycles_yr"), f"{sel['cycles_yr']:.0f}")

    with st.expander(t("detail_expander")):
        _w = 25  # label width for alignment
        _lbl = lambda key: (t(key) + ":").ljust(_w)
        st.text(f"{_lbl('detail_battery')} {sel['label']} ({sel['capacity']:.1f} kWh)")
        st.text(f"{_lbl('detail_battery_price')} {sel['bat_cost']:>10,.0f} kr")
        st.text(f"{_lbl('detail_total_invest')} {sel['total_invest']:>10,.0f} kr")
        st.text(f"{_lbl('detail_lower_cost')} {per_year:>10,.0f} {t('kr_yr')} ({per_year/12:,.0f} {t('kr_month')})")
        if sel["arb_yr"] > 0:
            st.text(f"{_lbl('detail_of_which_battery')} {sel['arb_yr']:>10,.0f} {t('kr_yr')}")
        if sel["solar_self_yr"] > 0:
            st.text(f"{_lbl('detail_of_which_solar')} {sel['solar_self_yr']:>10,.0f} {t('kr_yr')}")
        if sel.get("green_bat", 0) + sel.get("green_sol", 0) > 0:
            st.text(f"{_lbl('detail_green_deduction')} {-(sel['green_bat'] + sel['green_sol']):>10,.0f} kr")
        st.text(f"{_lbl('detail_payback')} {_fmt_payback(sel['payback']):>13}")
        _net_lbl = (t('detail_net_over').format(lifetime=f"{sel['lifetime']:.0f}") + ":").ljust(_w)
        st.text(f"{_net_lbl} {sel['profit_life']:>10,.0f} kr")
        _life_lbl = (t('detail_battery_life') + ":").ljust(_w)
        st.text(f"{_life_lbl} {sel['lifetime']:>10.1f} {t('yr')} ({sel['cycles_yr']:.0f} {t('cycles_yr')})")
        st.text(f"{_lbl('detail_tariff')} {sel['best_tariff']}")

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

    months_sv = t("months")
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
    col_w1.metric(t("detail_lower_cost_metric"), f"{per_year/12:,.0f} {t('kr_month')}",
                   delta=f"{per_year:,.0f} {t('kr_yr')}")
    op_fees = get_operator_fuse_fees(grid_operator)
    fuse_monthly = op_fees.get(fuse_amps, 0) / 12
    col_w2.metric(t("detail_fixed_costs"), f"{49 + fuse_monthly:,.0f} {t('kr_month')}",
                   help=f"Tibber 49 kr + {grid_operator} {fuse_monthly:,.0f} kr ({fuse_amps}A)")

    fig_stack = go.Figure()
    fig_stack.add_trace(go.Bar(
        x=df_md["month"], y=df_md["discharge_value"],
        name=t("monthly_discharge"), marker_color="#2ecc71",
        hovertemplate="%{x}<br>%{y:,.0f} kr<extra>" + t("monthly_discharge_extra") + "</extra>",
    ))
    if df_md["export_rev"].sum() > 0:
        fig_stack.add_trace(go.Bar(
            x=df_md["month"], y=df_md["export_rev"],
            name=t("monthly_sold_grid"), marker_color="#3498db",
            hovertemplate="%{x}<br>%{y:,.0f} kr<extra>" + t("monthly_sold_extra") + "</extra>",
        ))
    fig_stack.add_trace(go.Bar(
        x=df_md["month"], y=-df_md["charge_cost"],
        name=t("monthly_charge_cost"), marker_color="#e74c3c",
        hovertemplate="%{x}<br>%{y:,.0f} kr<extra>" + t("monthly_charge_extra") + "</extra>",
    ))
    # Net per month as line
    fig_stack.add_trace(go.Scatter(
        x=df_md["month"], y=df_md["net"],
        mode="lines+markers", name=t("monthly_net_savings"),
        line=dict(width=3, color="#2c3e50"),
        hovertemplate="%{x}<br>" + t("monthly_net_savings") + ": %{y:,.0f} " + t("kr_month") + "<extra></extra>",
    ))
    fig_stack.add_hline(y=sel["arb_yr"]/12, line_dash="dash", line_color="gray",
                         annotation_text=t("monthly_avg_annotation").format(value=f"{sel['arb_yr']/12:,.0f}"))
    fig_stack.update_layout(barmode="relative", yaxis_title=t("yaxis_kr_month_typical"), height=400,
                             margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig_stack, use_container_width=True)

    with st.expander(t("monthly_details_expander")):
        st.dataframe(pd.DataFrame([{
            t("monthly_col_month"): r["month"],
            t("monthly_col_discharged"): f"{r['discharge_value']:,.0f}",
            t("monthly_col_charge_cost"): f"{r['charge_cost']:,.0f}",
            t("monthly_col_sold"): f"{r['export_rev']:,.0f}",
            t("monthly_col_solar_bat"): f"{r['solar_charged']:,.0f}",
            t("monthly_col_net"): f"{r['net']:,.0f}",
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


    # Three scenarios for the recommended battery. Simulated ONCE right after the main
    # simulation (_compute_vol_benefits); here we only read the cached numbers.
    # Benefit and net use the same definitions as the main recommendation.
    scenarios = [(t(_sk), _svf, t(f"{_sk}_desc")) for _sk, _svf in FUTURE_SCENARIOS]
    inv = best["total_invest"]
    _horizon = best["lifetime"]

    # Summary metrics
    col_s1, col_s2, col_s3 = st.columns(3)
    for col, (label, vf, desc) in zip([col_s1, col_s2, col_s3], scenarios):
        sr = scenario_results[label]
        col.metric(label, f"{sr['arb_yr']:,.0f} {t('kr_yr')}",
                    delta=t("net_lifetime_delta").format(value=f"{sr['lifetime_profit']:+,.0f}",
                                                         lifetime=f"{_horizon:.0f}"))
        col.caption(desc)

    # Cumulative cashflow over the battery lifetime for each scenario
    st.subheader(t("forecast_15yr_header").format(label=best['label']))
    st.caption(t("forecast_15yr_caption"))

    fig_15 = go.Figure()
    scenario_colors = {t("conservative"): "#3498db", t("likely"): "#2ecc71", t("high_volatility"): "#e74c3c"}
    _n_years = int(math.ceil(_horizon))
    for label, target_vol, desc in scenarios:
        cum = [-inv]
        for yr in range(1, _n_years + 1):
            cum.append(cum[-1] + _scenario_year_benefit(_vol_arb, target_vol, yr))
        fig_15.add_trace(go.Scatter(
            x=list(range(_n_years + 1)), y=cum, mode="lines",
            name=label, line=dict(width=3, color=scenario_colors[label]),
            hovertemplate=f"{label}<br>{t('xaxis_year')} %{{x}}: %{{y:,.0f}} kr<extra></extra>",
        ))

    fig_15.add_hline(y=0, line_color="gray", line_width=1,
                      annotation_text=t("repaid_annotation"), annotation_position="bottom right")
    fig_15.update_layout(xaxis_title=t("xaxis_year"), yaxis_title=t("yaxis_cum_cashflow"), height=400,
                          margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig_15, use_container_width=True)

    # Summary table
    st.dataframe(pd.DataFrame([{
        t("scenario_col_scenario"): label,
        t("scenario_col_volatility"): t("scenario_vol_desc").format(vf=vf),
        t("scenario_col_savings_yr"): f"{scenario_results[label]['arb_yr']:,.0f} kr",
        t("scenario_col_savings_mo"): f"{scenario_results[label]['arb_yr']/12:,.0f} kr",
        t("scenario_col_net_15yr").format(lifetime=f"{_horizon:.0f}"):
            f"{scenario_results[label]['lifetime_profit']:+,.0f} kr",
    } for label, vf, desc in scenarios]), use_container_width=True, hide_index=True)
