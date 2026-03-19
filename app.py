"""
Energikalkyl — El, Sol & Batteri (Web GUI)

Analysverktyg för elpriser, solceller, hembatteri och förbrukningsoptimering.
Start with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from elpriser import fetch_range, load_csv, save_csv, ZONES, ZONE_NAMES
from batteri import BatteryConfig, LoadSchedule, FlexibleLoad, simulate, SimResult
from solar import SolarConfig, estimate_yearly_production, estimate_lifetime_production
from tariff import (
    Tidstariff, FastTariff, is_peak_hour,
    FUSE_YEARLY_FEE, get_fuse_fee_monthly, get_fuse_fee_yearly,
)

st.set_page_config(page_title="Energikalkyl", page_icon="⚡", layout="wide")
st.title("Energikalkyl — El, Sol & Batteri")

# ================================================================
# SIDEBAR: Consumption data
# ================================================================
st.sidebar.header("1. Förbrukningsdata")
cons_source = st.sidebar.radio("Förbrukningskälla", [
    "Manuell (ange i simulering)",
    "Tibber API",
    "CSV (Vattenfall, Ellevio, E.ON m.fl.)",
])

if cons_source == "Tibber API":
    st.sidebar.caption("Hämtar timdata + månadsdata från Tibber för säsongsanpassad profil")
    if st.sidebar.button("Hämta förbrukningsprofil", key="fetch_tibber_cons"):
        with st.spinner("Hämtar från Tibber..."):
            try:
                from tibber_source import (
                    fetch_consumption, consumption_to_load_profile,
                    fetch_monthly_consumption, build_seasonal_hourly_profile,
                )
                nodes = fetch_consumption(hours=24*30)
                profile = consumption_to_load_profile(nodes)
                st.session_state["tibber_nodes"] = nodes
                st.session_state["tibber_hourly_profile"] = profile

                monthly = fetch_monthly_consumption(months=36)
                st.session_state["tibber_monthly"] = monthly
                if len(monthly) >= 6:
                    seasonal = build_seasonal_hourly_profile(nodes, monthly)
                    st.session_state["tibber_seasonal"] = seasonal
                    st.sidebar.success(f"Säsongsanpassad profil laddad ({len(monthly)} mån)")
                else:
                    st.sidebar.success(f"Timmeprofil laddad ({len(nodes)} timmar)")
            except Exception as e:
                st.sidebar.error(f"Tibber-fel: {e}")

    if "tibber_hourly_profile" in st.session_state:
        p = st.session_state["tibber_hourly_profile"]
        avg = sum(p.values()) / 24
        st.sidebar.caption(f"Medel: {avg:.1f} kW | Dygn: {sum(p.values()):.0f} kWh")
        with st.sidebar.expander("Timmeprofil"):
            for h in range(24):
                bar = "█" * int(p.get(h, 0) * 3)
                st.text(f"{h:02d}:00  {p.get(h,0):.2f} kW {bar}")

elif cons_source.startswith("CSV"):
    st.sidebar.caption(
        "Ladda ner data från din elnätsägare (Mina sidor, BankID) och ladda upp här"
    )
    cons_files = st.sidebar.file_uploader(
        "Förbrukningsdata (CSV eller Excel)",
        type=["csv", "txt", "xlsx", "xls"],
        key="sidebar_cons_csv",
        accept_multiple_files=True,
        help="Du kan ladda upp flera filer samtidigt (t.ex. ett Excel per år från Vattenfall)",
    )
    if cons_files:
        try:
            import tempfile, os
            all_vf_data = []
            all_csv_data = []

            for cons_file in cons_files:
                filename = cons_file.name.lower()
                is_excel = filename.endswith(".xlsx") or filename.endswith(".xls")

                if is_excel:
                    from import_vattenfall import parse_vattenfall_excel
                    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                        tmp.write(cons_file.getvalue())
                        tmp_path = tmp.name
                    try:
                        vf_data = parse_vattenfall_excel(tmp_path)
                        all_vf_data.extend(vf_data)
                    finally:
                        os.unlink(tmp_path)
                else:
                    from import_consumption import parse_consumption_csv
                    raw = cons_file.getvalue()
                    for enc in ["utf-8", "utf-8-sig", "iso-8859-1", "cp1252"]:
                        try:
                            content = raw.decode(enc)
                            csv_data = parse_consumption_csv(content, cons_file.name)
                            all_csv_data.extend(csv_data)
                            break
                        except (UnicodeDecodeError, ValueError):
                            continue

            if all_vf_data:
                from import_vattenfall import vattenfall_to_seasonal_profile, vattenfall_to_monthly_profile
                # Deduplicate and sort
                seen = set()
                unique = []
                for r in sorted(all_vf_data, key=lambda x: x["date"]):
                    if r["date"] not in seen:
                        seen.add(r["date"])
                        unique.append(r)
                all_vf_data = unique

                hourly_shape = st.session_state.get("tibber_hourly_profile")
                seasonal = vattenfall_to_seasonal_profile(all_vf_data, hourly_shape)
                st.session_state["imported_seasonal"] = seasonal

                total_kwh = sum(r["consumption_kwh"] for r in all_vf_data)
                num_d = len(all_vf_data)
                avg_d = total_kwh / num_d if num_d > 0 else 0
                monthly = vattenfall_to_monthly_profile(all_vf_data)

                st.session_state["cons_import_status"] = {
                    "ok": True,
                    "source": "Vattenfall Excel",
                    "files": len(cons_files),
                    "days": num_d,
                    "first": all_vf_data[0]["date"],
                    "last": all_vf_data[-1]["date"],
                    "total_kwh": total_kwh,
                    "avg_daily": avg_d,
                    "monthly": monthly,
                }
                st.sidebar.success(f"Vattenfall: {num_d} dagar laddade")

            elif all_csv_data:
                from import_consumption import consumption_to_hourly_profile, consumption_to_monthly_daily
                profile = consumption_to_hourly_profile(all_csv_data)
                st.session_state["imported_hourly_profile"] = profile

                monthly_daily = consumption_to_monthly_daily(all_csv_data)
                months_with_data = sum(1 for v in monthly_daily.values() if v > 0)
                if months_with_data >= 6:
                    base_daily = sum(profile.values())
                    seasonal = {}
                    for m in range(1, 13):
                        scale = monthly_daily[m] / base_daily if monthly_daily[m] > 0 and base_daily > 0 else 1.0
                        seasonal[m] = {h: profile[h] * scale for h in range(24)}
                    st.session_state["imported_seasonal"] = seasonal

                total_kwh = sum(r["consumption_kwh"] for r in all_csv_data)
                num_d = len(set(r["date"] for r in all_csv_data))
                avg_d = total_kwh / num_d if num_d > 0 else 0

                st.session_state["cons_import_status"] = {
                    "ok": True,
                    "source": "CSV",
                    "files": len(cons_files),
                    "days": num_d,
                    "total_kwh": total_kwh,
                    "avg_daily": avg_d,
                }
                st.sidebar.success(f"CSV: {len(all_csv_data)} datapunkter laddade")
            else:
                st.session_state["cons_import_status"] = {"ok": False, "error": "Kunde inte tolka filerna"}
                st.sidebar.error("Kunde inte tolka filerna")
        except Exception as e:
            st.session_state["cons_import_status"] = {"ok": False, "error": str(e)}
            st.sidebar.error(f"Importfel: {e}")

st.sidebar.divider()

# ================================================================
# SIDEBAR: Price data
# ================================================================
st.sidebar.header("2. Prisdata")
data_source = st.sidebar.radio("Priskälla", ["Hämta från API", "Ladda CSV-fil", "Tibber priser"])

if data_source == "Ladda CSV-fil":
    uploaded = st.sidebar.file_uploader("Välj CSV-fil", type="csv")
    if uploaded:
        df_prices = pd.DataFrame(pd.read_csv(uploaded))
        st.session_state["df_prices"] = df_prices
        st.sidebar.success(f"Läste {len(df_prices)} rader")
    else:
        df_prices = st.session_state.get("df_prices")

elif data_source == "Tibber priser":
    tibber_hours = st.sidebar.number_input("Antal timmar prisdata", value=24*30, min_value=24, step=24*7)

    if st.sidebar.button("Hämta Tibber-priser", type="primary"):
        with st.spinner("Hämtar prisdata från Tibber..."):
            try:
                from tibber_source import fetch_consumption, consumption_to_rows
                nodes = fetch_consumption(hours=tibber_hours)
                rows = consumption_to_rows(nodes)
                df_prices = pd.DataFrame(rows)
                st.session_state["df_prices"] = df_prices
                st.sidebar.success(f"Hämtade {len(rows)} datapunkter")
            except Exception as e:
                st.error(f"Tibber-fel: {e}")
    else:
        df_prices = st.session_state.get("df_prices")

else:
    zone = st.sidebar.selectbox("Elområde", ZONES, index=2,
                                format_func=lambda z: f"{z} — {ZONE_NAMES[z]}")
    col1, col2 = st.sidebar.columns(2)
    start_date = col1.date_input("Från", value=date.today() - timedelta(days=30))
    end_date = col2.date_input("Till", value=date.today() - timedelta(days=1))
    use_entsoe = st.sidebar.checkbox("Använd ENTSO-E (kräver API-nyckel)")

    if st.sidebar.button("Hämta priser", type="primary"):
        with st.spinner("Hämtar prisdata..."):
            if use_entsoe:
                try:
                    from entsoe_source import fetch_entsoe
                    rows = fetch_entsoe(start_date, end_date, zone)
                except Exception as e:
                    st.error(f"ENTSO-E fel: {e}")
                    rows = []
            else:
                rows = fetch_range(start_date, end_date, zone)
            if rows:
                df_prices = pd.DataFrame(rows)
                st.session_state["df_prices"] = df_prices
                st.sidebar.success(f"Hämtade {len(df_prices)} datapunkter")
    else:
        df_prices = st.session_state.get("df_prices")

# ================================================================
# STATUS: Show import results prominently
# ================================================================
if "cons_import_status" in st.session_state:
    status = st.session_state["cons_import_status"]
    if status["ok"]:
        months_sv = ["", "Jan", "Feb", "Mar", "Apr", "Maj", "Jun",
                     "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]
        msg = (
            f"**Förbrukningsdata laddad** ({status['source']}, {status['files']} filer)  \n"
            f"{status['days']} dagar"
        )
        if "first" in status:
            msg += f" ({status['first']} → {status['last']})"
        msg += (
            f"  \n"
            f"Total: **{status['total_kwh']:,.0f} kWh** | "
            f"Snitt: **{status['avg_daily']:.0f} kWh/dag** | "
            f"~**{status['avg_daily']*365.25:,.0f} kWh/år**"
        )
        st.success(msg)

        # Show monthly breakdown if available
        if "monthly" in status:
            monthly = status["monthly"]
            with st.expander("Månadsvis förbrukning"):
                month_data = []
                for m in range(1, 13):
                    kwh_day = monthly.get(m, 0)
                    month_data.append({"Månad": months_sv[m], "kWh/dag": round(kwh_day, 1),
                                       "kWh/mån": round(kwh_day * 30.44)})
                st.dataframe(pd.DataFrame(month_data), use_container_width=True, hide_index=True)
    else:
        st.error(f"Förbrukningsdata kunde inte laddas: {status.get('error', 'okänt fel')}")

if df_prices is None or len(df_prices) == 0:
    st.info("Välj priskälla i sidopanelen och hämta data för att börja.")
    st.stop()

# Ensure numeric types
for col in ["sek_per_kwh", "eur_per_kwh", "ore_per_kwh"]:
    if col in df_prices.columns:
        df_prices[col] = pd.to_numeric(df_prices[col], errors="coerce")

# ================================================================
# PRICE OVERVIEW
# ================================================================
st.header("Prisöversikt")

tab_chart, tab_spread, tab_table, tab_stats = st.tabs(["Diagram", "Prisspridning", "Tabell", "Statistik"])

with tab_chart:
    df_plot = df_prices.copy()
    df_plot["datetime"] = pd.to_datetime(df_plot["date"] + " " + df_plot["hour"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_plot["datetime"], y=df_plot["ore_per_kwh"],
        mode="lines", name="Spotpris", line=dict(width=1),
        hovertemplate="%{x}<br>%{y:.1f} öre/kWh<extra></extra>",
    ))
    daily_avg = df_plot.groupby("date")["ore_per_kwh"].mean().reset_index()
    daily_avg["datetime"] = pd.to_datetime(daily_avg["date"])
    fig.add_trace(go.Scatter(
        x=daily_avg["datetime"], y=daily_avg["ore_per_kwh"],
        mode="lines", name="Dagsmedel", line=dict(width=2, dash="dash"),
    ))
    fig.update_layout(yaxis_title="öre/kWh", height=400,
                      margin=dict(l=0, r=0, t=30, b=0),
                      legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig, use_container_width=True)

with tab_spread:
    st.caption(
        "Visar genomsnittlig prisskillnad per dag mellan billigaste timmarna och övrig tid. "
        "**OBS:** Detta är en förenklad indikator för att visualisera prisspridningen — "
        "den faktiska simuleringen använder en mer detaljerad modell med nätavgifter, "
        "solproduktion, förbrukningsprofil och batteriförluster."
    )
    cheap_hours = st.slider("Antal billiga timmar (laddning)", 1, 12, 4)

    # Calculate daily spread
    spread_data = []
    for day, group in df_plot.groupby("date"):
        # Get hourly prices (aggregate 15-min to hourly if needed)
        hourly = group.groupby(group["datetime"].dt.hour)["ore_per_kwh"].mean()
        sorted_prices = hourly.sort_values()
        n = min(cheap_hours, len(sorted_prices))
        cheap_avg = sorted_prices.iloc[:n].mean()
        rest_avg = sorted_prices.iloc[n:].mean() if len(sorted_prices) > n else 0
        spread = rest_avg - cheap_avg
        spread_data.append({
            "date": day,
            "Billigast (öre/kWh)": round(cheap_avg, 1),
            "Övriga (öre/kWh)": round(rest_avg, 1),
            "Spread (öre/kWh)": round(spread, 1),
        })

    df_spread = pd.DataFrame(spread_data)
    df_spread["datetime"] = pd.to_datetime(df_spread["date"])

    # Key metrics
    avg_spread = df_spread["Spread (öre/kWh)"].mean()
    avg_cheap = df_spread["Billigast (öre/kWh)"].mean()
    avg_rest = df_spread["Övriga (öre/kWh)"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Snitt billigaste {cheap_hours}h", f"{avg_cheap:.1f} öre/kWh")
    c2.metric(f"Snitt övriga {24-cheap_hours}h", f"{avg_rest:.1f} öre/kWh")
    c3.metric("Snitt spread", f"{avg_spread:.1f} öre/kWh")
    c4.metric("Indikativ spread/dag (32 kWh)", f"{avg_spread * 32 / 100:.1f} SEK",
              help="Förenklad uppskattning — se simuleringsresultaten för verkligt utfall")

    # Spread chart
    fig_spread = go.Figure()
    fig_spread.add_trace(go.Scatter(
        x=df_spread["datetime"], y=df_spread["Billigast (öre/kWh)"],
        mode="lines", name=f"Billigaste {cheap_hours}h",
        fill="tozeroy", line=dict(width=1, color="#2ecc71"),
        hovertemplate="%{x}<br>%{y:.1f} öre/kWh<extra></extra>",
    ))
    fig_spread.add_trace(go.Scatter(
        x=df_spread["datetime"], y=df_spread["Övriga (öre/kWh)"],
        mode="lines", name=f"Övriga {24-cheap_hours}h",
        line=dict(width=1, color="#e74c3c"),
        hovertemplate="%{x}<br>%{y:.1f} öre/kWh<extra></extra>",
    ))
    fig_spread.add_trace(go.Scatter(
        x=df_spread["datetime"], y=df_spread["Spread (öre/kWh)"],
        mode="lines", name="Spread",
        line=dict(width=2, color="#f39c12", dash="dash"),
        hovertemplate="%{x}<br>Spread: %{y:.1f} öre/kWh<extra></extra>",
    ))
    fig_spread.update_layout(yaxis_title="öre/kWh", height=400,
                             margin=dict(l=0, r=0, t=30, b=0),
                             legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig_spread, use_container_width=True)

    # Monthly spread breakdown
    df_spread["month"] = pd.to_datetime(df_spread["date"]).dt.to_period("M").astype(str)
    monthly_spread = df_spread.groupby("month").agg({
        "Billigast (öre/kWh)": "mean",
        "Övriga (öre/kWh)": "mean",
        "Spread (öre/kWh)": "mean",
    }).round(1)
    monthly_spread["Indikativ 32kWh (SEK/mån)"] = (monthly_spread["Spread (öre/kWh)"] * 32 / 100 * 30.44).round(0).astype(int)
    st.subheader("Månadsvis prisspridning (indikativ)")
    st.dataframe(monthly_spread, use_container_width=True)

with tab_table:
    st.dataframe(df_prices, use_container_width=True, height=400)

with tab_stats:
    num_days_data = df_prices["date"].nunique()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Antal dagar", num_days_data)
    c2.metric("Medel", f"{df_prices['ore_per_kwh'].mean():.1f} öre/kWh")
    c3.metric("Min", f"{df_prices['ore_per_kwh'].min():.1f} öre/kWh")
    c4.metric("Max", f"{df_prices['ore_per_kwh'].max():.1f} öre/kWh")
    df_monthly = df_prices.copy()
    df_monthly["month"] = pd.to_datetime(df_monthly["date"]).dt.to_period("M").astype(str)
    monthly_avg = df_monthly.groupby("month")["ore_per_kwh"].mean().reset_index()
    monthly_avg.columns = ["Månad", "Medelpris (öre/kWh)"]
    st.subheader("Månadsmedel")
    st.bar_chart(monthly_avg.set_index("Månad"))

csv_data = df_prices.to_csv(index=False)
st.download_button("Ladda ner prisdata som CSV", csv_data, "elpriser.csv", "text/csv")

# ================================================================
# SIMULATION CONFIGURATION
# ================================================================
st.header("Anläggning & Parametrar")

tab_bat, tab_solar, tab_grid, tab_loads, tab_invest = st.tabs([
    "Batteri", "Solceller", "Elnät & Nätavgift", "Förbrukning & Laster", "Investering"
])

# --- Battery ---
with tab_bat:
    col1, col2 = st.columns(2)
    with col1:
        capacity = st.number_input("Kapacitet (kWh)", value=32.15, min_value=1.0, step=0.5)
        charge_kw = st.number_input("Max laddeffekt (kW)", value=15.0, min_value=0.5, step=0.5)
        discharge_kw = st.number_input("Max urladdeffekt (kW)", value=15.0, min_value=0.5, step=0.5)
    with col2:
        efficiency = st.slider("Verkningsgrad (%)", 70, 100, 93) / 100
        cycle_life = st.number_input("Cykellivslängd", value=8000, min_value=100, step=500)
        calendar_life = st.number_input("Kalenderlivslängd (år)", value=15, min_value=1, step=1)

# --- Solar ---
with tab_solar:
    use_solar = st.checkbox("Solceller", value=True)
    if use_solar:
        col1, col2 = st.columns(2)
        with col1:
            solar_kwp = st.number_input("System (kWp)", value=15.0, min_value=0.5, step=0.5)
            solar_tilt = st.number_input("Lutning (grader)", value=35.0, min_value=0.0, max_value=90.0, step=5.0)
            solar_perf = st.slider("Systemverkningsgrad (%)", 70, 100, 85) / 100
        with col2:
            solar_degradation = st.number_input("Degradering (%/år)", value=0.5, min_value=0.0, max_value=2.0, step=0.1) / 100
            solar_lifetime = st.number_input("Panellivslängd (år)", value=25, min_value=5, step=1)

        solar_config = SolarConfig(
            capacity_kwp=solar_kwp, tilt=solar_tilt,
            performance_ratio=solar_perf, degradation_per_year=solar_degradation,
            lifetime_years=solar_lifetime,
        )
        yearly_prod = estimate_yearly_production(solar_config)
        st.info(f"Beräknad årsproduktion: **{yearly_prod:,.0f} kWh/år** ({yearly_prod/solar_kwp:.0f} kWh/kWp)")
    else:
        solar_config = None

# --- Grid & Tariff ---
with tab_grid:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Elnät")
        fuse_options = sorted(FUSE_YEARLY_FEE.keys())
        fuse_amps = st.selectbox("Säkring (A)", fuse_options, index=fuse_options.index(25))
        phases = st.selectbox("Faser", [3, 1], index=0)
        current_fuse_options = [None] + [a for a in fuse_options if a < fuse_amps]
        current_fuse = st.selectbox(
            "Nuvarande säkring (för merkostnad vid uppgradering)",
            current_fuse_options,
            format_func=lambda x: "Ingen uppgradering" if x is None else f"{x:.0f}A",
        )
        grid_max = fuse_amps * 230 * phases / 1000
        st.caption(f"Max från nät: {grid_max:.1f} kW | Abonnemang: {get_fuse_fee_yearly(fuse_amps):,.0f} kr/år")

    with col2:
        st.subheader("Nätavgift")
        tariff_type = st.selectbox("Tariffmodell", ["Tidstariff", "Enkeltariff", "Ingen"])
        if tariff_type == "Tidstariff":
            peak_rate = st.number_input("Höglasttid (öre/kWh)", value=76.50, step=0.5)
            offpeak_rate = st.number_input("Övrig tid (öre/kWh)", value=30.50, step=0.5)
        elif tariff_type == "Enkeltariff":
            flat_rate = st.number_input("Överföringsavgift (öre/kWh)", value=44.50, step=0.5)
        energy_tax = st.number_input("Energiskatt (öre/kWh, inkl. moms)", value=54.88, step=0.1)

# --- Consumption & Loads ---
with tab_loads:
    hourly_load_profile = None
    seasonal_load_profile = None
    base_load = 1.5

    # Check if profile was loaded from sidebar
    has_profile = ("tibber_seasonal" in st.session_state or "tibber_hourly_profile" in st.session_state
                   or "imported_seasonal" in st.session_state or "imported_hourly_profile" in st.session_state)

    if has_profile:
        if "tibber_seasonal" in st.session_state:
            seasonal_load_profile = st.session_state["tibber_seasonal"]
            src = "Tibber (säsongsanpassad)"
        elif "imported_seasonal" in st.session_state:
            seasonal_load_profile = st.session_state["imported_seasonal"]
            src = "CSV (säsongsanpassad)"
        elif "tibber_hourly_profile" in st.session_state:
            hourly_load_profile = st.session_state["tibber_hourly_profile"]
            src = "Tibber (timmeprofil)"
        elif "imported_hourly_profile" in st.session_state:
            hourly_load_profile = st.session_state["imported_hourly_profile"]
            src = "CSV (timmeprofil)"

        if seasonal_load_profile:
            all_kw = [kw for m in seasonal_load_profile.values() for kw in m.values()]
            st.success(f"Förbrukningsprofil: **{src}** — {min(all_kw):.1f}–{max(all_kw):.1f} kW")
        elif hourly_load_profile:
            avg = sum(hourly_load_profile.values()) / 24
            st.success(f"Förbrukningsprofil: **{src}** — medel {avg:.1f} kW")

        use_loaded = st.checkbox("Använd laddad profil", value=True)
        if not use_loaded:
            hourly_load_profile = None
            seasonal_load_profile = None
            base_load = st.number_input("Grundförbrukning (kW, alltid)", value=1.5, min_value=0.0, step=0.5)
    else:
        st.info("Ladda förbrukningsdata i sidopanelen (Tibber API eller CSV) för att använda verklig profil, "
                "eller ange manuellt nedan.")
        base_load = st.number_input("Grundförbrukning (kW, alltid)", value=1.5, min_value=0.0, step=0.5)

    # Scheduled loads
    st.subheader("Schemalagda laster (fasta tider)")
    st.caption("Påverkar tillgänglig laddkapacitet under specifika timmar")

    if "scheduled_loads" not in st.session_state:
        st.session_state["scheduled_loads"] = [
            {"name": "Elbil", "power": 11.0, "start": 23, "end": 6},
        ]

    loads_to_remove = []
    for i, load in enumerate(st.session_state["scheduled_loads"]):
        cols = st.columns([3, 2, 2, 2, 1])
        load["name"] = cols[0].text_input("Namn", value=load["name"], key=f"load_name_{i}")
        load["power"] = cols[1].number_input("kW", value=load["power"], min_value=0.0, step=0.5, key=f"load_kw_{i}")
        load["start"] = cols[2].number_input("Från kl", value=load["start"], min_value=0, max_value=23, key=f"load_start_{i}")
        load["end"] = cols[3].number_input("Till kl", value=load["end"], min_value=0, max_value=23, key=f"load_end_{i}")
        if cols[4].button("X", key=f"load_rm_{i}"):
            loads_to_remove.append(i)

    for i in sorted(loads_to_remove, reverse=True):
        st.session_state["scheduled_loads"].pop(i)

    if st.button("Lägg till schemalagd last"):
        st.session_state["scheduled_loads"].append({"name": "Ny last", "power": 1.0, "start": 0, "end": 6})
        st.rerun()

    scheduled_loads = [
        LoadSchedule(name=l["name"], power_kw=l["power"], start_hour=l["start"], end_hour=l["end"])
        for l in st.session_state["scheduled_loads"] if l["power"] > 0
    ]

    # Flexible loads
    st.subheader("Flexibla laster (solöverskott)")
    st.caption("Körs när det finns solöverskott — t.ex. poolvärmepump, varmvattenberedare")

    if "flexible_loads" not in st.session_state:
        st.session_state["flexible_loads"] = [
            {"name": "Poolpump", "power": 3.0, "daily_kwh": 20.0, "start_month": 5, "end_month": 9},
        ]

    flex_to_remove = []
    for i, fl in enumerate(st.session_state["flexible_loads"]):
        cols = st.columns([3, 2, 2, 2, 2, 1])
        fl["name"] = cols[0].text_input("Namn", value=fl["name"], key=f"flex_name_{i}")
        fl["power"] = cols[1].number_input("kW", value=fl["power"], min_value=0.0, step=0.5, key=f"flex_kw_{i}")
        fl["daily_kwh"] = cols[2].number_input("Max kWh/dag", value=fl["daily_kwh"], min_value=0.0, step=1.0, key=f"flex_daily_{i}")
        fl["start_month"] = cols[3].number_input("Från mån", value=fl["start_month"], min_value=1, max_value=12, key=f"flex_sm_{i}")
        fl["end_month"] = cols[4].number_input("Till mån", value=fl["end_month"], min_value=1, max_value=12, key=f"flex_em_{i}")
        if cols[5].button("X", key=f"flex_rm_{i}"):
            flex_to_remove.append(i)

    for i in sorted(flex_to_remove, reverse=True):
        st.session_state["flexible_loads"].pop(i)

    if st.button("Lägg till flexibel last"):
        st.session_state["flexible_loads"].append(
            {"name": "Ny last", "power": 2.0, "daily_kwh": 10.0, "start_month": 1, "end_month": 12}
        )
        st.rerun()

    flexible_loads = [
        FlexibleLoad(name=fl["name"], power_kw=fl["power"], daily_kwh=fl["daily_kwh"],
                     start_month=fl["start_month"], end_month=fl["end_month"])
        for fl in st.session_state["flexible_loads"] if fl["power"] > 0
    ]

    # Load profile visualization
    st.subheader("Lastprofil")
    load_profile_data = []
    for h in range(24):
        if seasonal_load_profile:
            # Average across months
            load_kw = sum(seasonal_load_profile.get(m, {}).get(h, 0) for m in range(1, 13)) / 12
        elif hourly_load_profile:
            load_kw = hourly_load_profile.get(h, 0)
        else:
            load_kw = base_load + sum(l.power_kw for l in scheduled_loads if l.is_active(h))
        avail = min(charge_kw, max(0, grid_max - load_kw))
        load_profile_data.append({"Timme": f"{h:02d}", "Hushållslast (kW)": load_kw, "Laddkapacitet (kW)": avail})

    df_lp = pd.DataFrame(load_profile_data)
    fig_lp = go.Figure()
    fig_lp.add_trace(go.Bar(x=df_lp["Timme"], y=df_lp["Hushållslast (kW)"],
                             name="Hushållslast", marker_color="#e74c3c"))
    fig_lp.add_trace(go.Bar(x=df_lp["Timme"], y=df_lp["Laddkapacitet (kW)"],
                             name="Batterikapacitet", marker_color="#2ecc71"))
    fig_lp.add_hline(y=grid_max, line_dash="dash", line_color="gray",
                     annotation_text=f"Säkring {fuse_amps:.0f}A = {grid_max:.1f} kW")
    fig_lp.update_layout(barmode="stack", yaxis_title="kW", height=300,
                         margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig_lp, use_container_width=True)

# --- Investment ---
with tab_invest:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Batteri")
        bat_price = st.number_input("Inköpspris batteri (SEK)", value=25000, min_value=0, step=1000)
        bat_install = st.number_input("Installation batteri (SEK)", value=10000, min_value=0, step=1000)
    with col2:
        st.subheader("Solceller")
        if use_solar:
            sol_price = st.number_input("Inköpspris solceller (SEK)", value=0, min_value=0, step=5000,
                                        help="Sätt 0 om solcellerna redan är betalda")
            sol_install = st.number_input("Installation solceller (SEK)", value=0, min_value=0, step=5000)
            if solar_config:
                solar_config.purchase_price = sol_price
                solar_config.installation_cost = sol_install
        else:
            sol_price = 0
            sol_install = 0

    total_inv = bat_price + bat_install + sol_price + sol_install
    st.info(f"Total investering: **{total_inv:,.0f} SEK**")

# ================================================================
# RUN SIMULATION
# ================================================================
st.header("Simulering & Resultat")

if st.button("Kör simulering", type="primary", use_container_width=True):
    config = BatteryConfig(
        capacity_kwh=capacity,
        max_charge_kw=charge_kw,
        max_discharge_kw=discharge_kw,
        efficiency=efficiency,
        fuse_amps=fuse_amps,
        phases=phases,
        base_load_kw=base_load,
        scheduled_loads=scheduled_loads if not (hourly_load_profile or seasonal_load_profile) else [],
        hourly_load_profile=hourly_load_profile if not seasonal_load_profile else None,
        seasonal_load_profile=seasonal_load_profile,
        flexible_loads=flexible_loads,
        purchase_price=bat_price,
        installation_cost=bat_install,
        cycle_life=cycle_life,
        calendar_life_years=calendar_life,
    )

    tariff = None
    if tariff_type == "Tidstariff":
        tariff = Tidstariff(peak=peak_rate, offpeak=offpeak_rate,
                            energy_tax=energy_tax, fuse_amps=fuse_amps)
    elif tariff_type == "Enkeltariff":
        tariff = FastTariff(flat_rate=flat_rate, energy_tax=energy_tax, fuse_amps=fuse_amps)

    # Fuse analysis before simulation
    fuse_warnings = config.fuse_analysis()
    st.session_state["fuse_warnings"] = fuse_warnings

    price_rows = df_prices.to_dict("records")

    with st.spinner("Simulerar..."):
        result = simulate(price_rows, config, tariff=tariff,
                          solar=solar_config if use_solar else None)

    st.session_state["sim_result"] = result
    st.session_state["sim_tariff"] = tariff
    st.session_state["sim_config"] = config
    st.session_state["sim_current_fuse"] = current_fuse
    st.session_state["sim_solar"] = solar_config if use_solar else None
    st.session_state["sim_price_rows"] = price_rows

# ================================================================
# RESULTS
# ================================================================
if "sim_result" in st.session_state:
    result = st.session_state["sim_result"]
    tariff = st.session_state["sim_tariff"]
    config = st.session_state["sim_config"]
    current_fuse = st.session_state["sim_current_fuse"]
    solar_cfg = st.session_state.get("sim_solar")
    price_rows = st.session_state.get("sim_price_rows", [])

    st.subheader("Resultat")

    # Fuse warnings
    if "fuse_warnings" in st.session_state:
        fw = st.session_state["fuse_warnings"]
        errors = [w for w in fw if w["severity"] == "error"]
        no_charge = [w for w in fw if w["severity"] == "warning"]
        limited = [w for w in fw if w["severity"] == "info"]

        if errors:
            msg = f"**Säkringen är för liten!** Hushållslasten överskrider säkringens kapacitet ({config.grid_max_kw:.1f} kW):\n\n"
            for w in errors[:8]:
                msg += f"- {w['period']}: last **{w['load_kw']} kW** ({w['over_kw']} kW för mycket)\n"
            if len(errors) > 8:
                msg += f"- ... och {len(errors)-8} fler tillfällen\n"
            msg += f"\nÖverväg att uppgradera säkringen eller minska lasten."
            st.error(msg)

        if no_charge:
            unique_hours = sorted(set(w["hour"] for w in no_charge))
            hours_str = ", ".join(f"{h:02d}:00" for h in unique_hours)
            st.warning(
                f"**Ingen batteriladdning möjlig** kl {hours_str} — "
                f"hushållslasten tar all säkringskapacitet. "
                f"Batteriet kan bara laddas under övriga timmar."
            )

        if limited and not errors and not no_charge:
            unique_hours = sorted(set(w["hour"] for w in limited))
            st.info(
                f"Batteriladdningen begränsas kl {', '.join(f'{h:02d}' for h in unique_hours)} "
                f"(under {config.max_charge_kw:.0f} kW) på grund av andra laster."
            )

    num_days = len(set(s.date for s in result.slots))
    num_months = num_days / 30.44
    monthly_fee = tariff.monthly_fee if tariff else 0

    upgrade_monthly = 0
    if current_fuse is not None and tariff:
        base_fee = get_fuse_fee_monthly(current_fuse)
        upgrade_monthly = monthly_fee - base_fee

    arbitrage = result.net_profit_sek
    upgrade_cost_total = upgrade_monthly * num_months
    net = arbitrage - upgrade_cost_total
    per_year = net / num_days * 365.25 if num_days > 0 else 0

    # Key metrics row
    cols = st.columns(5)
    cols[0].metric("Arbitrage", f"{arbitrage:,.0f} SEK")
    cols[1].metric("Netto/år", f"{per_year:,.0f} SEK")
    cols[2].metric("Cykler", f"{result.num_cycles:.0f}")
    if result.total_solar_charge_kwh > 0:
        cols[3].metric("Solladdat", f"{result.total_solar_charge_kwh:,.0f} kWh")
    if result.total_flex_consumed_kwh > 0:
        cols[4].metric("Flex-förbrukning", f"{result.total_flex_consumed_kwh:,.0f} kWh")

    # Investment ROI
    bat_inv = config.purchase_price + config.installation_cost
    sol_inv = (solar_cfg.purchase_price + solar_cfg.installation_cost) if solar_cfg else 0
    total_investment = bat_inv + sol_inv

    if total_investment > 0 and num_days > 0:
        cycles_per_year = result.num_cycles / (num_days / 365.25)
        cycle_lifetime = config.cycle_life / cycles_per_year if cycles_per_year > 0 else config.calendar_life_years
        bat_lifetime = min(cycle_lifetime, config.calendar_life_years)
        effective_lifetime = bat_lifetime
        if solar_cfg:
            effective_lifetime = min(bat_lifetime, solar_cfg.lifetime_years)
        payback_years = total_investment / per_year if per_year > 0 else float("inf")
        total_profit = per_year * effective_lifetime - total_investment
        roi = (total_profit / total_investment) * 100 if total_investment > 0 else 0

        st.subheader("Investeringskalkyl")
        cols = st.columns(5)
        cols[0].metric("Investering", f"{total_investment:,.0f} SEK")
        cols[1].metric("Återbetalningstid", f"{payback_years:.1f} år" if payback_years < 100 else "Aldrig")
        cols[2].metric("Livslängd", f"{effective_lifetime:.0f} år")
        cols[3].metric("Total vinst", f"{total_profit:,.0f} SEK")
        cols[4].metric("ROI", f"{roi:.0f}%")

        if payback_years <= effective_lifetime:
            st.success(f"Återbetald inom livslängden ({payback_years:.1f} av {effective_lifetime:.0f} år)")
        elif per_year > 0:
            st.warning(f"Återbetalas EJ inom livslängden ({payback_years:.1f} > {effective_lifetime:.0f} år)")

        # Breakdown
        with st.expander("Investeringsdetaljer"):
            if bat_inv > 0:
                st.text(f"Batteri inköp:      {config.purchase_price:>10,.0f} SEK")
                st.text(f"Batteri installation:{config.installation_cost:>10,.0f} SEK")
            if sol_inv > 0:
                st.text(f"Sol inköp:          {solar_cfg.purchase_price:>10,.0f} SEK")
                st.text(f"Sol installation:   {solar_cfg.installation_cost:>10,.0f} SEK")
                lifetime_kwh = estimate_lifetime_production(solar_cfg)
                cost_ore = sol_inv / lifetime_kwh * 100
                st.text(f"Sol avskrivning:    {cost_ore:>10.1f} öre/kWh ({lifetime_kwh:,.0f} kWh/{solar_cfg.lifetime_years} år)")
            st.text(f"Cykler/år:          {cycles_per_year:>10.0f}")
            st.text(f"Batterilivslängd:   {bat_lifetime:>10.1f} år")

    # Detailed summary
    with st.expander("Detaljerad sammanfattning"):
        details = {
            "Period (dagar)": num_days,
            "Laddat totalt (kWh)": f"{result.total_charged_kwh:.1f}",
            "Urladdat totalt (kWh)": f"{result.total_discharged_kwh:.1f}",
            "Antal cykler": f"{result.num_cycles:.1f}",
        }
        if result.total_solar_charge_kwh > 0:
            details["Solladdat (kWh)"] = f"{result.total_solar_charge_kwh:.1f}"
        if result.total_flex_consumed_kwh > 0:
            details["Flex-förbrukning (kWh)"] = f"{result.total_flex_consumed_kwh:.1f}"
        details.update({
            "Laddkostnad (SEK)": f"{result.total_charge_cost:.2f}",
            "Urladdningsvärde (SEK)": f"{result.total_discharge_value:.2f}",
            "Arbitragevinst (SEK)": f"{arbitrage:.2f}",
            "Nätavgiftsmodell": tariff.name if tariff else "Ingen",
            "Per dag (SEK)": f"{net/num_days:.2f}" if num_days > 0 else "—",
            "Per månad (SEK)": f"{per_year/12:.0f}" if num_days > 0 else "—",
            "Per år (SEK)": f"{per_year:.0f}" if num_days > 0 else "—",
        })
        for k, v in details.items():
            st.text(f"{k:.<40} {v}")

    # Daily profit chart
    st.subheader("Daglig vinst")
    df_slots = pd.DataFrame([{
        "date": s.date, "action": s.action,
        "energy_kwh": s.energy_kwh, "cost_sek": s.cost_sek,
        "saving_sek": s.saving_sek, "soc_after": s.soc_after,
    } for s in result.slots])

    df_daily = df_slots.groupby("date").agg(
        charged=("energy_kwh", lambda x: x[df_slots.loc[x.index, "action"] == "charge"].sum()),
        discharged=("energy_kwh", lambda x: x[df_slots.loc[x.index, "action"] == "discharge"].sum()),
        cost=("cost_sek", "sum"),
        value=("saving_sek", "sum"),
    ).reset_index()
    df_daily["profit"] = df_daily["value"] - df_daily["cost"]

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=df_daily["date"], y=df_daily["profit"],
        name="Daglig vinst",
        marker_color=["#2ecc71" if p >= 0 else "#e74c3c" for p in df_daily["profit"]],
        hovertemplate="%{x}<br>%{y:.2f} SEK<extra></extra>",
    ))
    fig2.update_layout(yaxis_title="SEK", height=350, margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig2, use_container_width=True)

    # SOC chart
    st.subheader("Batteristatus (SOC)")
    df_soc = pd.DataFrame([{
        "datetime": s.date + " " + s.hour, "soc_kwh": s.soc_after,
    } for s in result.slots])
    df_soc["datetime"] = pd.to_datetime(df_soc["datetime"])

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=df_soc["datetime"], y=df_soc["soc_kwh"],
        mode="lines", name="SOC", fill="tozeroy",
        line=dict(width=1, color="#3498db"),
        hovertemplate="%{x}<br>%{y:.1f} kWh<extra></extra>",
    ))
    fig3.add_hline(y=config.capacity_kwh * config.max_soc, line_dash="dash", line_color="gray", annotation_text="Max")
    fig3.add_hline(y=config.capacity_kwh * config.min_soc, line_dash="dash", line_color="gray", annotation_text="Min")
    fig3.update_layout(yaxis_title="kWh", height=300, margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig3, use_container_width=True)

    # Fuse comparison
    st.subheader("Jämförelse säkringsstorlekar")
    fuse_compare = []
    for amps in sorted(FUSE_YEARLY_FEE.keys()):
        test_config = BatteryConfig(
            capacity_kwh=config.capacity_kwh,
            max_charge_kw=config.max_charge_kw,
            max_discharge_kw=config.max_discharge_kw,
            efficiency=config.efficiency,
            fuse_amps=amps,
            phases=config.phases,
            base_load_kw=config.base_load_kw,
            scheduled_loads=config.scheduled_loads,
            hourly_load_profile=config.hourly_load_profile,
            seasonal_load_profile=config.seasonal_load_profile,
            flexible_loads=config.flexible_loads,
        )
        test_tariff = None
        if tariff:
            if isinstance(tariff, Tidstariff):
                test_tariff = Tidstariff(peak=tariff.peak, offpeak=tariff.offpeak,
                                         energy_tax=tariff.energy_tax, fuse_amps=amps)
            else:
                test_tariff = FastTariff(flat_rate=tariff.flat_rate,
                                         energy_tax=tariff.energy_tax, fuse_amps=amps)

        test_result = simulate(price_rows, test_config, tariff=test_tariff,
                               solar=solar_cfg)
        yearly_fee = get_fuse_fee_yearly(amps)
        arb = test_result.net_profit_sek
        arb_yr = arb / num_days * 365.25 if num_days > 0 else 0
        fuse_compare.append({
            "Säkring": f"{amps:.0f}A",
            "Abonnemang (kr/år)": f"{yearly_fee:,.0f}",
            "Arbitrage/år (SEK)": f"{arb_yr:,.0f}",
        })

    st.dataframe(pd.DataFrame(fuse_compare), use_container_width=True, hide_index=True)
