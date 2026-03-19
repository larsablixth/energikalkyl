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
    Tidstariff, FastTariff,
    FUSE_YEARLY_FEE, get_fuse_fee_monthly, get_fuse_fee_yearly,
)

st.set_page_config(page_title="Energikalkyl", page_icon="⚡", layout="wide")
st.title("Energikalkyl — El, Sol & Batteri")
st.caption("Lönar sig ett hembatteri? Ladda dina data, konfigurera din anläggning, och få svaret.")

# ================================================================
# STEP 1: LOAD DATA
# ================================================================
st.header("1. Dina data")
col_prices, col_consumption = st.columns(2)

# --- Price data ---
with col_prices:
    st.subheader("Elpriser")
    price_source = st.radio("Källa", ["Hämta från API", "Ladda CSV"], key="price_src")

    if price_source == "Ladda CSV":
        price_file = st.file_uploader("Pris-CSV", type=["csv"], key="price_csv")
        if price_file:
            df_prices = pd.read_csv(price_file)
            st.session_state["df_prices"] = df_prices
        else:
            df_prices = st.session_state.get("df_prices")
    else:
        zone = st.selectbox("Elområde", ZONES, index=2,
                            format_func=lambda z: f"{z} — {ZONE_NAMES[z]}")
        col_d1, col_d2 = st.columns(2)
        start_date = col_d1.date_input("Från", value=date.today() - timedelta(days=365))
        end_date = col_d2.date_input("Till", value=date.today() - timedelta(days=1))
        if st.button("Hämta priser", type="primary"):
            with st.spinner("Hämtar..."):
                rows = fetch_range(start_date, end_date, zone)
                if rows:
                    df_prices = pd.DataFrame(rows)
                    st.session_state["df_prices"] = df_prices
        else:
            df_prices = st.session_state.get("df_prices")

    if df_prices is not None and len(df_prices) > 0:
        for col in ["sek_per_kwh", "ore_per_kwh"]:
            if col in df_prices.columns:
                df_prices[col] = pd.to_numeric(df_prices[col], errors="coerce")
        n_days = df_prices["date"].nunique()
        st.success(f"{n_days} dagar laddade ({df_prices['date'].min()} → {df_prices['date'].max()})")

# --- Consumption data ---
with col_consumption:
    st.subheader("Din förbrukning")
    cons_source = st.radio("Källa", ["Tibber API", "Vattenfall/CSV/Excel", "Manuell"], key="cons_src")

    hourly_load_profile = None
    seasonal_load_profile = None

    if cons_source == "Tibber API":
        if st.button("Hämta från Tibber"):
            with st.spinner("Hämtar från Tibber..."):
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
                    st.success("Profil laddad")
                except Exception as e:
                    st.error(f"Tibber-fel: {e}")

    elif cons_source == "Vattenfall/CSV/Excel":
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
                    st.success(f"{len(unique)} dagar | Snitt: {avg:.0f} kWh/dag | ~{avg*365:,.0f} kWh/år")
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
                    st.success(f"{len(all_csv)} datapunkter laddade")
            except Exception as e:
                st.error(f"Importfel: {e}")

    # Show loaded profile status
    if "seasonal_profile" in st.session_state:
        seasonal_load_profile = st.session_state["seasonal_profile"]
        all_kw = [kw for m in seasonal_load_profile.values() for kw in m.values()]
        st.info(f"Säsongsanpassad profil: {min(all_kw):.1f}–{max(all_kw):.1f} kW")
    elif "hourly_profile" in st.session_state:
        hourly_load_profile = st.session_state["hourly_profile"]
        avg = sum(hourly_load_profile.values()) / 24
        st.info(f"Timmeprofil: medel {avg:.1f} kW")
    elif cons_source == "Manuell":
        st.info("Ange grundlast och laster i steg 2")

if df_prices is None or len(df_prices) == 0:
    st.info("Ladda prisdata för att fortsätta.")
    st.stop()

# ================================================================
# SPREAD ANALYSIS (always shown)
# ================================================================
st.header("Prisspridning")
st.caption("Skillnaden mellan billigaste och dyraste timmarna — detta är vad batteriet kan tjäna på. "
           "Indikativ — se simuleringsresultat för verkligt utfall.")

df_plot = df_prices.copy()
df_plot["datetime"] = pd.to_datetime(df_plot["date"] + " " + df_plot["hour"])

cheap_hours = 4  # fixed at 4 as discussed

spread_data = []
for day, group in df_plot.groupby("date"):
    hourly = group.groupby(group["datetime"].dt.hour)["ore_per_kwh"].mean()
    sorted_p = hourly.sort_values()
    n = min(cheap_hours, len(sorted_p))
    cheap = sorted_p.iloc[:n].mean()
    rest = sorted_p.iloc[n:].mean() if len(sorted_p) > n else 0
    spread_data.append({"date": day, "cheap": round(cheap, 1), "rest": round(rest, 1),
                        "spread": round(rest - cheap, 1)})

df_spread = pd.DataFrame(spread_data)
df_spread["datetime"] = pd.to_datetime(df_spread["date"])
df_spread["month"] = pd.to_datetime(df_spread["date"]).dt.to_period("M").astype(str)

col1, col2, col3 = st.columns(3)
col1.metric("Snitt billigaste 4h", f"{df_spread['cheap'].mean():.0f} öre/kWh")
col2.metric("Snitt övriga 20h", f"{df_spread['rest'].mean():.0f} öre/kWh")
col3.metric("Snitt spread", f"{df_spread['spread'].mean():.0f} öre/kWh")

fig_sp = go.Figure()
fig_sp.add_trace(go.Scatter(x=df_spread["datetime"], y=df_spread["spread"],
                             mode="lines", name="Daglig spread", line=dict(width=1, color="#f39c12")))
# Monthly average
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

col_sys1, col_sys2, col_sys3 = st.columns(3)

with col_sys1:
    st.subheader("Batteri")
    capacity = st.number_input("Kapacitet (kWh)", value=32.15, min_value=1.0, step=0.5)
    charge_kw = st.number_input("Max laddeffekt (kW)", value=15.0, min_value=0.5, step=0.5)
    discharge_kw = st.number_input("Max urladdeffekt (kW)", value=15.0, min_value=0.5, step=0.5)
    efficiency = st.slider("Verkningsgrad (%)", 70, 100, 93) / 100
    cycle_life = st.number_input("Cykellivslängd", value=8000, min_value=100, step=500)

with col_sys2:
    st.subheader("Solceller")
    use_solar = st.checkbox("Solceller", value=True)
    if use_solar:
        solar_kwp = st.number_input("System (kWp)", value=15.0, min_value=0.5, step=0.5)
        export_factor = st.number_input("Exportpris (andel av spot)", value=1.0, min_value=0.0, max_value=1.5, step=0.05)
        export_fee = st.number_input("Exportavgift (öre/kWh)", value=5.0, min_value=0.0, step=1.0)
        solar_config = SolarConfig(capacity_kwp=solar_kwp)
    else:
        solar_config = None
        export_factor = 1.0
        export_fee = 5.0

with col_sys3:
    st.subheader("Elnät")
    fuse_options = sorted(FUSE_YEARLY_FEE.keys())
    fuse_amps = st.selectbox("Säkring (A)", fuse_options, index=fuse_options.index(25))
    phases = st.selectbox("Faser", [3, 1], index=0)
    st.caption("Nätavgift (Vattenfall 2026)")
    with st.expander("Tariffpriser", expanded=False):
        peak_rate = st.number_input("Tidstariff höglast (öre/kWh)", value=76.50, step=0.5)
        offpeak_rate = st.number_input("Tidstariff övrig (öre/kWh)", value=30.50, step=0.5)
        flat_rate = st.number_input("Enkeltariff (öre/kWh)", value=44.50, step=0.5)
        energy_tax = st.number_input("Energiskatt (öre/kWh)", value=54.88, step=0.1)
    st.info(f"Båda tarifferna simuleras — bästa väljs automatiskt")

# Loads
st.subheader("Laster")
col_l1, col_l2 = st.columns(2)

with col_l1:
    base_load = st.number_input("Grundlast (kW)", value=1.5, min_value=0.0, step=0.5,
                                help="Används om ingen profil laddats") if not (seasonal_load_profile or hourly_load_profile) else 1.5

    if "scheduled_loads" not in st.session_state:
        st.session_state["scheduled_loads"] = [{"name": "Elbil", "power": 11.0, "start": 23, "end": 6}]

    st.markdown("**Schemalagda laster**")
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

    st.markdown("**Flexibla laster (solöverskott)**")
    for i, fl in enumerate(st.session_state["flexible_loads"]):
        c = st.columns([3, 2, 2, 2, 2, 1])
        fl["name"] = c[0].text_input("", value=fl["name"], key=f"fn_{i}", label_visibility="collapsed")
        fl["power"] = c[1].number_input("kW", value=fl["power"], min_value=0.0, step=0.5, key=f"fp_{i}")
        fl["daily"] = c[2].number_input("kWh/dag", value=fl["daily"], min_value=0.0, step=1.0, key=f"fd_{i}")
        fl["sm"] = c[3].number_input("Från mån", value=fl["sm"], min_value=1, max_value=12, key=f"fs_{i}")
        fl["em"] = c[4].number_input("Till mån", value=fl["em"], min_value=1, max_value=12, key=f"fe_{i}")
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

# ================================================================
# STEP 3: INVESTMENT
# ================================================================
st.header("3. Investering")
col_i1, col_i2, col_i3 = st.columns(3)
with col_i1:
    bat_price = st.number_input("Batteripris (SEK)", value=25000, min_value=0, step=1000)
    bat_install = st.number_input("Installation (SEK)", value=10000, min_value=0, step=1000)
with col_i2:
    if use_solar:
        sol_price = st.number_input("Solcellspris (SEK)", value=0, min_value=0, step=5000,
                                    help="0 om redan installerat")
        sol_install = st.number_input("Sol-installation (SEK)", value=0, min_value=0, step=5000)
    else:
        sol_price = 0
        sol_install = 0
with col_i3:
    finance = st.radio("Finansiering", ["Eget kapital", "Lån"])
    if finance == "Lån":
        loan_rate = st.number_input("Ränta (%)", value=5.0, min_value=0.0, step=0.5)
        loan_years = st.number_input("Lånetid (år)", value=10, min_value=1, step=1)
    else:
        loan_rate = 0
        loan_years = 0

total_invest = bat_price + bat_install + sol_price + sol_install
st.info(f"Total investering: **{total_invest:,.0f} SEK**")

# ================================================================
# STEP 4: SIMULATE
# ================================================================
st.divider()
st.header("4. Resultat")

if st.button("KÖR SIMULERING", type="primary", use_container_width=True):
    config = BatteryConfig(
        capacity_kwh=capacity, max_charge_kw=charge_kw, max_discharge_kw=discharge_kw,
        efficiency=efficiency, fuse_amps=fuse_amps, phases=phases,
        base_load_kw=base_load,
        scheduled_loads=scheduled_loads if not (hourly_load_profile or seasonal_load_profile) else [],
        hourly_load_profile=hourly_load_profile if not seasonal_load_profile else None,
        seasonal_load_profile=seasonal_load_profile,
        flexible_loads=flexible_loads,
        purchase_price=bat_price, installation_cost=bat_install,
        cycle_life=cycle_life, calendar_life_years=15,
        export_price_factor=export_factor, export_fee_ore=export_fee,
    )

    tariff_tid = Tidstariff(peak=peak_rate, offpeak=offpeak_rate, energy_tax=energy_tax, fuse_amps=fuse_amps)
    tariff_enkel = FastTariff(flat_rate=flat_rate, energy_tax=energy_tax, fuse_amps=fuse_amps)

    price_rows = df_prices.to_dict("records")

    # Fuse warnings
    fuse_warnings = config.fuse_analysis()
    errors = [w for w in fuse_warnings if w["severity"] == "error"]
    no_charge = [w for w in fuse_warnings if w["severity"] == "warning"]
    if errors:
        st.error(f"**Säkringen räcker inte!** Last överskrider {config.grid_max_kw:.1f} kW vid "
                 f"{len(errors)} tillfällen. Överväg större säkring.")
    if no_charge:
        hrs = sorted(set(w["hour"] for w in no_charge))
        st.warning(f"Ingen batteriladdning möjlig kl {', '.join(f'{h:02d}' for h in hrs)} — "
                   f"hushållslasten tar all kapacitet.")

    with st.spinner("Simulerar båda tarifferna..."):
        result_tid = simulate(price_rows, config, tariff=tariff_tid, solar=solar_config)
        result_enkel = simulate(price_rows, config, tariff=tariff_enkel, solar=solar_config)

    days_tid = len(set(s.date for s in result_tid.slots))
    days_enkel = len(set(s.date for s in result_enkel.slots))
    profit_tid = result_tid.net_profit_sek / days_tid * 365.25 if days_tid > 0 else 0
    profit_enkel = result_enkel.net_profit_sek / days_enkel * 365.25 if days_enkel > 0 else 0

    if profit_tid >= profit_enkel:
        result, tariff, best_tariff = result_tid, tariff_tid, "Tidstariff"
    else:
        result, tariff, best_tariff = result_enkel, tariff_enkel, "Enkeltariff"

    st.session_state["result"] = result
    st.session_state["config"] = config
    st.session_state["tariff"] = tariff
    st.session_state["solar_cfg"] = solar_config
    st.session_state["price_rows"] = price_rows
    st.session_state["tariff_comparison"] = {
        "best": best_tariff,
        "tid_profit": profit_tid,
        "tid_fee": get_fuse_fee_yearly(fuse_amps),
        "enkel_profit": profit_enkel,
        "enkel_fee": get_fuse_fee_yearly(fuse_amps),
    }

# ================================================================
# RESULTS
# ================================================================
if "result" in st.session_state:
    result = st.session_state["result"]
    config = st.session_state["config"]
    tariff = st.session_state["tariff"]
    solar_cfg = st.session_state.get("solar_cfg")
    price_rows = st.session_state.get("price_rows", [])

    num_days = len(set(s.date for s in result.slots))
    per_year = result.net_profit_sek / num_days * 365.25 if num_days > 0 else 0

    # === TARIFF RECOMMENDATION ===
    if "tariff_comparison" in st.session_state:
        tc = st.session_state["tariff_comparison"]
        diff = abs(tc["tid_profit"] - tc["enkel_profit"])
        col_t1, col_t2, col_t3 = st.columns(3)
        col_t1.metric("Tidstariff", f"{tc['tid_profit']:,.0f} kr/år",
                       delta="Rekommenderas" if tc["best"] == "Tidstariff" else None)
        col_t2.metric("Enkeltariff", f"{tc['enkel_profit']:,.0f} kr/år",
                       delta="Rekommenderas" if tc["best"] == "Enkeltariff" else None)
        col_t3.metric("Skillnad", f"{diff:,.0f} kr/år")
        st.success(f"**{tc['best']}** ger bäst resultat — **{diff:,.0f} kr/år** mer än alternativet")

    # === THE ANSWER ===
    st.subheader("Lönar det sig?")

    bat_inv = config.purchase_price + config.installation_cost
    sol_inv = (solar_cfg.purchase_price + solar_cfg.installation_cost) if solar_cfg else 0
    total_investment = bat_inv + sol_inv

    if total_investment > 0 and per_year > 0:
        payback = total_investment / per_year
        cycles_yr = result.num_cycles / (num_days / 365.25) if num_days > 0 else 0
        bat_lifetime = min(config.cycle_life / cycles_yr if cycles_yr > 0 else 15, 15)
        total_profit_15yr = per_year * bat_lifetime - total_investment

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Vinst per år", f"{per_year:,.0f} kr")
        col2.metric("Återbetalningstid", f"{payback:.1f} år")
        col3.metric("Vinst under livslängd", f"{total_profit_15yr:,.0f} kr")
        col4.metric("ROI", f"{total_profit_15yr/total_investment*100:.0f}%")

        if payback < bat_lifetime:
            st.success(f"**Ja, det lönar sig.** Investering {total_investment:,.0f} kr återbetald på {payback:.1f} år "
                       f"(livslängd {bat_lifetime:.0f} år). Total vinst: {total_profit_15yr:,.0f} kr.")
        else:
            st.warning(f"**Osäkert.** Återbetalningstid {payback:.1f} år överstiger livslängden {bat_lifetime:.0f} år.")
    elif per_year > 0:
        st.success(f"**Vinst: {per_year:,.0f} kr/år** (ingen investering angiven)")
    else:
        st.error("Simuleringen visar ingen vinst med dessa inställningar.")

    # === MONTHLY CASHFLOW BREAKDOWN ===
    st.subheader("Typiskt år — vad pengarna kommer ifrån")

    df_slots = pd.DataFrame([{
        "date": s.date, "month": s.date[:7], "action": s.action,
        "hour": s.hour,
        "sek_per_kwh": s.sek_per_kwh,
        "total_cost_ore": s.total_cost_ore,
        "energy_kwh": s.energy_kwh, "cost_sek": s.cost_sek,
        "saving_sek": s.saving_sek, "solar_charge_kwh": s.solar_charge_kwh,
        "grid_export_kwh": s.grid_export_kwh, "export_revenue_sek": s.export_revenue_sek,
        "flex_consumed_kwh": s.flex_consumed_kwh,
        "solar_kw": s.solar_kw,
    } for s in result.slots])

    # Detect slot duration
    slots_per_day = df_slots.groupby("date").size().median()
    slot_h = 24 / slots_per_day if slots_per_day > 0 else 1

    # Build detailed breakdown by calendar month (Jan-Dec), averaged across years
    months_sv = ["", "Jan", "Feb", "Mar", "Apr", "Maj", "Jun",
                 "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]
    df_slots["cal_month"] = pd.to_datetime(df_slots["date"]).dt.month
    years_in_data = num_days / 365.25

    monthly_detail = []
    for m_num, grp in df_slots.groupby("cal_month"):
        n_d = grp["date"].nunique()

        # Household consumption — average per year for this calendar month
        if config.seasonal_load_profile:
            daily_kwh = sum(config.seasonal_load_profile.get(m_num, {}).values())
        elif config.hourly_load_profile:
            daily_kwh = sum(config.hourly_load_profile.values())
        else:
            daily_kwh = sum(config.total_load_kw(h) for h in range(24))
        avg_days_in_month = n_d / years_in_data
        consumption_kwh = daily_kwh * avg_days_in_month

        avg_total_ore = grp["total_cost_ore"].mean()
        cost_no_solar_no_bat = consumption_kwh * avg_total_ore / 100

        # All values averaged per year
        solar_produced = grp["solar_kw"].sum() * slot_h / years_in_data
        solar_to_battery = grp["solar_charge_kwh"].sum() / years_in_data
        solar_to_flex = grp["flex_consumed_kwh"].sum() / years_in_data
        solar_exported = grp["grid_export_kwh"].sum() / years_in_data
        solar_self_use = max(0, solar_produced - solar_to_battery - solar_to_flex - solar_exported)
        solar_self_use = min(solar_self_use, consumption_kwh)
        solar_self_saving = solar_self_use * avg_total_ore / 100

        bat_charge_cost = grp[grp["action"] == "charge"]["cost_sek"].sum() / years_in_data
        bat_discharge_value = grp[grp["action"] == "discharge"]["saving_sek"].sum() / years_in_data
        bat_arbitrage = bat_discharge_value - bat_charge_cost

        export_rev = grp["export_revenue_sek"].sum() / years_in_data
        flex_saving = solar_to_flex * avg_total_ore / 100

        total_saving = solar_self_saving + bat_arbitrage + export_rev + flex_saving

        monthly_detail.append({
            "month": months_sv[m_num],
            "month_num": m_num,
            "consumption": consumption_kwh,
            "cost_without": cost_no_solar_no_bat,
            "solar_self_saving": solar_self_saving,
            "bat_arbitrage": bat_arbitrage,
            "export_rev": export_rev,
            "flex_saving": flex_saving,
            "total_saving": total_saving,
            "cost_with": cost_no_solar_no_bat - total_saving,
        })

    df_md = pd.DataFrame(monthly_detail).sort_values("month_num")

    # Stacked bar: what each source contributes in a typical year
    fig_stack = go.Figure()
    if solar_cfg:
        fig_stack.add_trace(go.Bar(
            x=df_md["month"], y=df_md["solar_self_saving"],
            name="Sol → hushåll",
            marker_color="#f1c40f",
            hovertemplate="%{x}<br>%{y:,.0f} kr/mån<extra>Undviken elkostnad</extra>",
        ))
    fig_stack.add_trace(go.Bar(
        x=df_md["month"], y=df_md["bat_arbitrage"],
        name="Batteri arbitrage",
        marker_color="#2ecc71",
        hovertemplate="%{x}<br>%{y:,.0f} kr/mån<extra>Köp billigt → urladda dyrt</extra>",
    ))
    if solar_cfg and df_md["export_rev"].sum() > 0:
        fig_stack.add_trace(go.Bar(
            x=df_md["month"], y=df_md["export_rev"],
            name="Sålt till nät",
            marker_color="#3498db",
            hovertemplate="%{x}<br>%{y:,.0f} kr/mån<extra>Överskott sålt</extra>",
        ))
    if df_md["flex_saving"].sum() > 0:
        fig_stack.add_trace(go.Bar(
            x=df_md["month"], y=df_md["flex_saving"],
            name="Sol → pool/flex",
            marker_color="#e67e22",
            hovertemplate="%{x}<br>%{y:,.0f} kr/mån<extra>Undviken elkostnad</extra>",
        ))

    fig_stack.add_hline(y=per_year/12, line_dash="dash", line_color="gray",
                         annotation_text=f"Snitt {per_year/12:,.0f} kr/mån")
    fig_stack.update_layout(
        barmode="stack", yaxis_title="Besparing (kr/månad, typiskt år)", height=400,
        margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02),
    )
    st.plotly_chart(fig_stack, use_container_width=True)

    # Summary
    avg_saving = df_md["total_saving"].mean()
    avg_without = df_md["cost_without"].mean()
    avg_with = df_md["cost_with"].mean()

    col1, col2, col3 = st.columns(3)
    col1.metric("Elkostnad utan sol/batteri", f"{avg_without:,.0f} kr/mån")
    col2.metric("Elkostnad med sol/batteri", f"{max(0, avg_with):,.0f} kr/mån")
    col3.metric("Total besparing", f"{avg_saving:,.0f} kr/mån", delta=f"{avg_saving*12:,.0f} kr/år")

    # Itemized yearly breakdown
    st.markdown("**Var kommer pengarna ifrån?**")
    breakdown_items = []
    if solar_cfg:
        breakdown_items.append(("Sol → eget hushåll", df_md["solar_self_saving"].sum(),
                                "Solel du använder direkt istället för att köpa från nätet"))
    breakdown_items.append(("Batteri arbitrage", df_md["bat_arbitrage"].sum(),
                            "Ladda billigt (natt/middag) → urladda dyrt (morgon/kväll)"))
    if solar_cfg and df_md["export_rev"].sum() > 0:
        breakdown_items.append(("Sålt överskott", df_md["export_rev"].sum(),
                                "Solöverskott som säljs till nätet"))
    if df_md["flex_saving"].sum() > 0:
        breakdown_items.append(("Sol → pool/flex", df_md["flex_saving"].sum(),
                                "Solel driver poolpump etc. gratis"))

    for label, amount, desc in breakdown_items:
        st.text(f"  {label:.<40} {amount:>8,.0f} kr/år  ({desc})")
    total_yr = sum(a for _, a, _ in breakdown_items)
    st.text(f"  {'TOTALT':.<40} {total_yr:>8,.0f} kr/år")

    # Monthly table
    with st.expander("Detaljer per månad"):
        st.dataframe(pd.DataFrame([{
            "Månad": r["month"],
            "Förbrukning": f"{r['consumption']:,.0f} kWh",
            "Utan (kr)": f"{r['cost_without']:,.0f}",
            "Sol→hushåll": f"{r['solar_self_saving']:,.0f}",
            "Arbitrage": f"{r['bat_arbitrage']:,.0f}",
            "Export": f"{r['export_rev']:,.0f}",
            "Pool/flex": f"{r['flex_saving']:,.0f}",
            "Besparing": f"{r['total_saving']:,.0f}",
            "Med sol/bat": f"{max(0, r['cost_with']):,.0f}",
        } for r in monthly_detail]), use_container_width=True, hide_index=True)

    # === CASHFLOW ===
    if total_investment > 0:
        st.subheader("Kassaflöde")
        years = list(range(0, 16))
        cf = [-total_investment]
        for y in range(1, 16):
            cf.append(cf[-1] + per_year)

        fig_cf = go.Figure()
        fig_cf.add_trace(go.Scatter(x=years, y=cf, mode="lines+markers", name="Eget kapital",
                                     line=dict(width=2, color="#2ecc71"), fill="tozeroy"))

        if loan_rate > 0 and loan_years > 0:
            mr = loan_rate / 100 / 12
            n_p = loan_years * 12
            mp = total_investment * mr / (1 - (1 + mr) ** -n_p) if mr > 0 else total_investment / n_p
            yp = mp * 12
            cf_loan = [0]
            for y in range(1, 16):
                prev = cf_loan[-1] + per_year - (yp if y <= loan_years else 0)
                cf_loan.append(prev)
            fig_cf.add_trace(go.Scatter(x=years, y=cf_loan, mode="lines+markers",
                                         name=f"Lån {loan_rate}%/{loan_years}år",
                                         line=dict(width=2, color="#e74c3c", dash="dash")))

        fig_cf.add_hline(y=0, line_color="gray", line_width=1)
        fig_cf.update_layout(xaxis_title="År", yaxis_title="SEK", height=400,
                              margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02))
        st.plotly_chart(fig_cf, use_container_width=True)

    # === BATTERY SIZE OPTIMIZER ===
    st.divider()
    st.header("5. Optimal batteristorlek")
    st.caption("Baserat på NKON ESS Pro prislista. Visar vilken storlek som ger "
               "mest pengar tillbaka under livslängden.")

    # NKON ESS Pro price list (EUR excl. VAT, approx Q1 2025)
    EUR_SEK = 11.5  # approximate
    nkon_options = [
        ("5 kWh",      5.12,   3.8,    600 * EUR_SEK),
        ("10 kWh",    10.24,   7.5,   1177 * EUR_SEK),
        ("16 kWh",    16.10,  11.0,   1512 * EUR_SEK),
        ("32 kWh",    32.15,  15.0,   2857 * EUR_SEK),
        ("32+16 kWh", 48.25,  15.0,  (2857+1512) * EUR_SEK),
        ("2×32 kWh",  64.30,  15.0,  (2857*2) * EUR_SEK),
    ]

    with st.spinner("Optimerar batteristorlek..."):
        opt_results = []
        for label, cap, max_chg, bat_cost in nkon_options:
            # Limit charge to fuse headroom
            opt_cfg = BatteryConfig(
                capacity_kwh=cap, max_charge_kw=max_chg, max_discharge_kw=max_chg,
                efficiency=config.efficiency, fuse_amps=config.fuse_amps, phases=config.phases,
                base_load_kw=config.base_load_kw, scheduled_loads=config.scheduled_loads,
                hourly_load_profile=config.hourly_load_profile,
                seasonal_load_profile=config.seasonal_load_profile,
                flexible_loads=config.flexible_loads,
                export_price_factor=config.export_price_factor, export_fee_ore=config.export_fee_ore,
                purchase_price=bat_cost, installation_cost=config.installation_cost,
                cycle_life=config.cycle_life, calendar_life_years=15,
            )
            opt_r = simulate(price_rows, opt_cfg, tariff=tariff, solar=solar_cfg)
            opt_days = len(set(s.date for s in opt_r.slots))
            opt_arb_yr = opt_r.net_profit_sek / opt_days * 365.25 if opt_days > 0 else 0
            opt_invest = bat_cost + config.installation_cost
            opt_payback = opt_invest / opt_arb_yr if opt_arb_yr > 0 else 999
            opt_cycles_yr = opt_r.num_cycles / (opt_days / 365.25) if opt_days > 0 else 0
            opt_lifetime = min(config.cycle_life / opt_cycles_yr if opt_cycles_yr > 0 else 15, 15)
            opt_profit_life = opt_arb_yr * opt_lifetime - opt_invest
            opt_roi = opt_profit_life / opt_invest * 100 if opt_invest > 0 else 0

            opt_results.append({
                "label": label,
                "capacity": cap,
                "bat_cost": bat_cost,
                "invest": opt_invest,
                "arb_yr": opt_arb_yr,
                "payback": opt_payback,
                "profit_life": opt_profit_life,
                "roi": opt_roi,
                "cost_per_kwh_bat": bat_cost / cap,
                "cycles_yr": opt_cycles_yr,
            })

    df_opt = pd.DataFrame(opt_results)

    # Find best by total profit (what matters is money in your pocket)
    best = df_opt.loc[df_opt["profit_life"].idxmax()]
    st.success(f"**Mest lönsam: {best['label']}** — **{best['arb_yr']:,.0f} kr/år**, "
               f"**{best['profit_life']:,.0f} kr total vinst** under livslängden, "
               f"{best['payback']:.1f} års återbetalningstid")

    # Main chart: yearly income + total lifetime profit
    fig_opt = go.Figure()
    fig_opt.add_trace(go.Bar(
        x=df_opt["label"], y=df_opt["arb_yr"],
        name="Vinst per år (kr)", marker_color="#2ecc71",
        hovertemplate="%{x}<br><b>%{y:,.0f} kr/år</b><extra></extra>",
    ))
    fig_opt.update_layout(yaxis_title="SEK per år", height=350,
                           margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig_opt, use_container_width=True)

    # Lifetime profit chart
    fig_life = go.Figure()
    fig_life.add_trace(go.Bar(
        x=df_opt["label"], y=df_opt["profit_life"],
        name="Total vinst under livslängd",
        marker_color=["#2ecc71" if p > 0 else "#e74c3c" for p in df_opt["profit_life"]],
        hovertemplate="%{x}<br><b>%{y:,.0f} kr</b> total vinst<extra></extra>",
    ))
    fig_life.add_trace(go.Scatter(
        x=df_opt["label"], y=-df_opt["invest"],
        mode="markers", name="Investering (negativt)",
        marker=dict(size=12, color="#e74c3c", symbol="diamond"),
        hovertemplate="%{x}<br>Investering: %{y:,.0f} kr<extra></extra>",
    ))
    fig_life.update_layout(yaxis_title="SEK", height=350,
                           margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig_life, use_container_width=True)

    # Detailed table — money first
    st.dataframe(pd.DataFrame([{
        "Batteri": r["label"],
        "Vinst/år": f"{r['arb_yr']:,.0f} kr",
        "Vinst/mån": f"{r['arb_yr']/12:,.0f} kr",
        "Total vinst (livslängd)": f"{r['profit_life']:,.0f} kr",
        "Investering": f"{r['invest']:,.0f} kr",
        "Payback": f"{r['payback']:.1f} år",
        "Kapacitet": f"{r['capacity']:.0f} kWh",
        "Batteripris": f"{r['bat_cost']:,.0f} kr",
    } for r in opt_results]), use_container_width=True, hide_index=True)

    # Marginal value: what does each step UP give you in extra kr/year?
    st.subheader("Vad ger varje uppgradering?")
    st.caption("Extra kronor per år om du väljer nästa storlek")

    marginal_data = []
    for i in range(1, len(opt_results)):
        prev = opt_results[i-1]
        curr = opt_results[i]
        extra_cost = curr["bat_cost"] - prev["bat_cost"]
        extra_arb = curr["arb_yr"] - prev["arb_yr"]
        extra_life = curr["profit_life"] - prev["profit_life"]
        marginal_payback = extra_cost / extra_arb if extra_arb > 0 else 999
        marginal_data.append({
            "step": f"{prev['label']} → {curr['label']}",
            "extra_cost": extra_cost,
            "extra_arb": extra_arb,
            "extra_life": extra_life,
            "payback": marginal_payback,
        })

    fig_marginal = go.Figure()
    fig_marginal.add_trace(go.Bar(
        x=[m["step"] for m in marginal_data],
        y=[m["extra_arb"] for m in marginal_data],
        name="Extra kr/år",
        marker_color=["#2ecc71" if m["extra_arb"] > 0 else "#e74c3c" for m in marginal_data],
        hovertemplate="%{x}<br>+%{y:,.0f} kr/år<extra></extra>",
    ))
    fig_marginal.update_layout(yaxis_title="Extra SEK/år", height=300,
                                margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig_marginal, use_container_width=True)

    st.dataframe(pd.DataFrame([{
        "Uppgradering": m["step"],
        "Extra kostnad": f"{m['extra_cost']:,.0f} kr",
        "Extra vinst/år": f"{m['extra_arb']:,.0f} kr",
        "Extra vinst (livslängd)": f"{m['extra_life']:,.0f} kr",
        "Marginal payback": f"{m['payback']:.1f} år",
        "Värt det?": "Ja" if m["payback"] < 6 else "Tveksamt",
    } for m in marginal_data]), use_container_width=True, hide_index=True)

    # === FUTURE VOLATILITY ===
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

    bat_configs = [
        ("32 kWh", 32.15, 15, round(2857 * EUR_SEK)),
        ("32 + 16 kWh", 48.25, 15, round((2857+1512) * EUR_SEK)),
        ("2 × 32 kWh", 64.3, 15, round(2857 * 2 * EUR_SEK)),
    ]
    vol_levels = [1.0, 1.2, 1.5, 2.0, 2.5]
    colors_bat = {"32 kWh": "#3498db", "32 + 16 kWh": "#2ecc71", "2 × 32 kWh": "#e74c3c"}

    with st.spinner("Beräknar scenarier..."):
        fc_data = []
        for vf in vol_levels:
            scaled = scale_vol(price_rows, vf)
            for bl, cap, chg, bp in bat_configs:
                fc_cfg = BatteryConfig(
                    capacity_kwh=cap, max_charge_kw=chg, max_discharge_kw=chg,
                    efficiency=config.efficiency, fuse_amps=config.fuse_amps, phases=config.phases,
                    base_load_kw=config.base_load_kw, scheduled_loads=config.scheduled_loads,
                    hourly_load_profile=config.hourly_load_profile,
                    seasonal_load_profile=config.seasonal_load_profile,
                    flexible_loads=config.flexible_loads,
                    export_price_factor=config.export_price_factor, export_fee_ore=config.export_fee_ore,
                    purchase_price=bp, installation_cost=config.installation_cost,
                    cycle_life=config.cycle_life, calendar_life_years=15,
                )
                r = simulate(scaled, fc_cfg, tariff=tariff, solar=solar_cfg)
                d = len(set(s.date for s in r.slots))
                ay = r.net_profit_sek / d * 365.25 if d > 0 else 0
                inv = bp + config.installation_cost
                fc_data.append({"vol": vf, "bat": bl, "arb_yr": ay, "invest": inv,
                                "payback": inv/ay if ay > 0 else 999})

    df_fc = pd.DataFrame(fc_data)

    # Arbitrage vs volatility chart
    fig_fc = go.Figure()
    for bl in [b[0] for b in bat_configs]:
        d = df_fc[df_fc["bat"] == bl]
        fig_fc.add_trace(go.Scatter(
            x=[f"{v:.0%}" for v in d["vol"]], y=d["arb_yr"],
            mode="lines+markers", name=bl, line=dict(width=2, color=colors_bat.get(bl)),
        ))
    fig_fc.update_layout(xaxis_title="Volatilitet", yaxis_title="Arbitrage (SEK/år)", height=350,
                          margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig_fc, use_container_width=True)

    # 15-year projection with ramping volatility
    st.subheader("15-årsprognos")
    st.caption(f"Volatiliteten ökar linjärt till {target_vol:.1f}x över 10 år, sedan konstant")

    fig_15 = go.Figure()
    for bl, cap, chg, bp in bat_configs:
        inv = bp + config.installation_cost
        cum = [-inv]
        for yr in range(1, 16):
            vol = 1.0 + (target_vol - 1.0) * min(yr, 10) / 10
            # Interpolate from precomputed scenarios
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

    # Summary table
    summary = []
    for bl in [b[0] for b in bat_configs]:
        for vl in vol_levels:
            r = df_fc[(df_fc["bat"]==bl) & (df_fc["vol"]==vl)].iloc[0]
            summary.append({"Batteri": bl, "Volatilitet": f"{vl:.0%}",
                            "Vinst/år": f"{r['arb_yr']:,.0f} kr",
                            "Payback": f"{r['payback']:.1f} år"})
    st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)
