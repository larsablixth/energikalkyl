#!/usr/bin/env python3
"""
Energikalkyl — El, Sol & Batteri

Analysverktyg för svenska elpriser, solceller och hembatteri.
Simulerar lönsamhet baserat på historiska spotpriser, verklig förbrukning,
solproduktion, nätavgifter och investeringskostnader.

Datakällor: elprisetjustnu.se, ENTSO-E, Tibber, Vattenfall Eldistribution.
"""

import argparse
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

API_URL = "https://www.elprisetjustnu.se/api/v1/prices"
CACHE_DIR = Path(__file__).parent / ".price_cache"

ZONES = ["SE1", "SE2", "SE3", "SE4"]
ZONE_NAMES = {
    "SE1": "Norra Sverige (Luleå)",
    "SE2": "Norra mellansverige (Sundsvall)",
    "SE3": "Södra mellansverige (Stockholm)",
    "SE4": "Södra Sverige (Malmö)",
}


def _cache_path(day: date, zone: str) -> Path:
    return CACHE_DIR / f"{day.isoformat()}_{zone}.json"


def fetch_prices(day: date, zone: str) -> list[dict]:
    """Fetch hourly prices for a given date and zone, with disk cache."""
    cache = _cache_path(day, zone)
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    url = f"{API_URL}/{day.year}/{day.strftime('%m')}-{day.strftime('%d')}_{zone}.json"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    CACHE_DIR.mkdir(exist_ok=True)
    cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def _parse_day_data(day: date, zone: str, data: list[dict]) -> list[dict]:
    """Convert raw API data for one day into our row format."""
    rows = []
    for entry in data:
        rows.append({
            "date": day.isoformat(),
            "hour": datetime.fromisoformat(entry["time_start"]).strftime("%H:%M"),
            "zone": zone,
            "sek_per_kwh": round(entry["SEK_per_kWh"], 4),
            "eur_per_kwh": round(entry["EUR_per_kWh"], 4),
            "ore_per_kwh": round(entry["SEK_per_kWh"] * 100, 2),
        })
    return rows


def fetch_range(start: date, end: date, zone: str, max_workers: int = 20) -> list[dict]:
    """Fetch prices for a date range using concurrent requests + disk cache."""
    days = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)

    total = len(days)
    cached = sum(1 for d in days if _cache_path(d, zone).exists())
    to_fetch = total - cached
    print(f"  {total} dagar totalt, {cached} i cache, {to_fetch} att hämta från API...")

    results: dict[date, list[dict]] = {}
    errors: dict[date, str] = {}
    done = 0

    def _fetch_one(day: date):
        return day, fetch_prices(day, zone)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch_one, d): d for d in days}
        for future in as_completed(futures):
            done += 1
            try:
                day, data = future.result()
                results[day] = data
            except Exception as e:
                day = futures[future]
                errors[day] = str(e)
            if done % 50 == 0 or done == total:
                print(f"  Framsteg: {done}/{total} dagar")

    if errors:
        print(f"  Varning: {len(errors)} dagar kunde inte hämtas")
        for d in sorted(errors)[:5]:
            print(f"    {d}: {errors[d]}")
        if len(errors) > 5:
            print(f"    ... och {len(errors) - 5} till")

    rows = []
    for day in sorted(results.keys()):
        rows.extend(_parse_day_data(day, zone, results[day]))
    return rows


def save_csv(rows: list[dict], path: str):
    """Save rows to a CSV file, using keys from first row as fieldnames."""
    if not rows:
        print("Inga rader att spara.")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Sparat {len(rows)} rader till {path}")


def load_csv(path: str) -> list[dict]:
    """Load price rows from a CSV file."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    print(f"Läste {len(rows)} rader från {path}")
    return rows


def print_table(rows: list[dict]):
    """Print prices as a formatted table."""
    if not rows:
        print("Inga priser att visa.")
        return
    print(f"\n{'Datum':<12} {'Timme':<7} {'Zon':<5} {'öre/kWh':>10} {'SEK/kWh':>10} {'EUR/kWh':>10}")
    print("-" * 58)
    for r in rows:
        print(
            f"{r['date']:<12} {r['hour']:<7} {r['zone']:<5} "
            f"{float(r['ore_per_kwh']):>10.2f} {float(r['sek_per_kwh']):>10.4f} {float(r['eur_per_kwh']):>10.4f}"
        )

    sek_values = [float(r["sek_per_kwh"]) for r in rows]
    print("-" * 58)
    avg = sum(sek_values) / len(sek_values)
    print(f"  Medel: {avg*100:.2f} öre/kWh | Min: {min(sek_values)*100:.2f} | Max: {max(sek_values)*100:.2f}")


def parse_date(s: str) -> date:
    return date.fromisoformat(s)


def main():
    parser = argparse.ArgumentParser(
        description="Energikalkyl — Elpriser, solceller och batterisimulering för Sverige."
    )
    sub = parser.add_subparsers(dest="command")

    # --- fetch ---
    p_fetch = sub.add_parser("hämta", help="Hämta priser från API och visa/spara")
    p_fetch.add_argument("--zon", choices=ZONES, default="SE3", help="Elområde (default: SE3)")
    p_fetch.add_argument("--datum", type=parse_date, default=date.today().isoformat(),
                         help="Datum (YYYY-MM-DD, default: idag)")
    p_fetch.add_argument("--till", type=parse_date, default=None,
                         help="Slutdatum för intervall (YYYY-MM-DD)")
    p_fetch.add_argument("--csv", type=str, default=None, help="Spara till CSV-fil")
    p_fetch.add_argument("--källa", choices=["elpris", "entsoe"], default="elpris",
                         help="Datakälla: elpris (elprisetjustnu.se) eller entsoe (ENTSO-E, kräver API-nyckel)")

    # --- read csv ---
    p_read = sub.add_parser("läs", help="Läs och visa priser från en CSV-fil")
    p_read.add_argument("fil", help="Sökväg till CSV-fil")

    # --- today shortcut ---
    p_today = sub.add_parser("idag", help="Visa dagens priser (snabbkommando)")
    p_today.add_argument("--zon", choices=ZONES, default="SE3")

    # --- tomorrow ---
    p_tomorrow = sub.add_parser("imorgon", help="Visa morgondagens priser (tillgängliga ~13:00)")
    p_tomorrow.add_argument("--zon", choices=ZONES, default="SE3")

    # --- tibber ---
    p_tibber = sub.add_parser("tibber", help="Hämta data från Tibber (kräver API-token)")
    p_tibber.add_argument("--timmar", type=int, default=24*30,
                          help="Antal timmar att hämta (default: 720 = 30 dagar)")
    p_tibber.add_argument("--dagar", type=int, default=None,
                          help="Hämta daglig förbrukning (t.ex. --dagar 1095 för 3 år)")
    p_tibber.add_argument("--månader", type=int, default=None,
                          help="Hämta månadsförbrukning (t.ex. --månader 36)")
    p_tibber.add_argument("--csv", type=str, default=None, help="Spara till CSV-fil")
    p_tibber.add_argument("--profil", action="store_true", help="Visa genomsnittlig förbrukningsprofil")
    p_tibber.add_argument("--priser", action="store_true", help="Visa dagens/morgondagens priser från Tibber")

    # --- battery simulation ---
    p_bat = sub.add_parser("batteri", help="Simulera lönsamhet för hembatteri")
    p_bat_src = p_bat.add_mutually_exclusive_group(required=True)
    p_bat_src.add_argument("--csv", type=str, help="Läs prisdata från CSV-fil")
    p_bat_src.add_argument("--datum", type=parse_date, help="Hämta från API (startdatum)")
    p_bat_src.add_argument("--tibber", type=int, default=None, metavar="TIMMAR",
                           help="Hämta från Tibber (antal timmar, t.ex. --tibber 8760 för 1 år)")
    p_bat.add_argument("--till", type=parse_date, default=None, help="Slutdatum")
    p_bat.add_argument("--zon", choices=ZONES, default="SE3")
    p_bat.add_argument("--kapacitet", type=float, default=13.5, help="Batterikapacitet i kWh (default: 13.5)")
    p_bat.add_argument("--laddeffekt", type=float, default=5.0, help="Max laddeffekt i kW (default: 5.0)")
    p_bat.add_argument("--urladdeffekt", type=float, default=5.0, help="Max urladdeffekt i kW (default: 5.0)")
    p_bat.add_argument("--verkningsgrad", type=float, default=0.90, help="Tur-retur-verkningsgrad (default: 0.90)")
    p_bat.add_argument("--säkring", type=float, default=25.0, choices=[16, 20, 25, 35, 50, 63],
                       help="Huvudsäkring i ampere (default: 25)")
    p_bat.add_argument("--faser", type=int, choices=[1, 3], default=3, help="Antal faser (default: 3)")
    p_bat.add_argument("--grundlast", type=float, default=1.5, help="Hushållets grundförbrukning i kW (default: 1.5)")
    p_bat.add_argument("--last", type=str, action="append", default=[],
                       help="Schemalagd last: NAMN:KW:START-SLUT, t.ex. --last elbil:11:23-06")
    p_bat.add_argument("--tibber-profil", action="store_true",
                       help="Använd verklig förbrukningsprofil från Tibber (ersätter --grundlast och --last)")
    p_bat.add_argument("--förbruknings-csv", type=str, default=None,
                       help="CSV med timförbrukning (t.ex. från Vattenfall Mina sidor)")
    p_bat.add_argument("--flex", type=str, action="append", default=[],
                       help="Flexibel last (solöverskott): NAMN:KW[:DAGKWH:STARTMÅN-SLUTMÅN], "
                            "t.ex. --flex poolpump:3:20:5-9")
    p_bat.add_argument("--dagvis", action="store_true", help="Visa daglig uppdelning")
    p_bat.add_argument("--pris", type=float, default=0, help="Batteriets inköpspris i SEK")
    p_bat.add_argument("--installation", type=float, default=0, help="Installationskostnad i SEK")
    p_bat.add_argument("--cykler", type=int, default=8000, help="Batteriets cykellivslängd (default: 8000)")
    p_bat.add_argument("--livslängd", type=int, default=15, help="Max kalenderlivslängd i år (default: 15)")
    p_bat.add_argument("--sol", type=float, default=0,
                       help="Solceller i kWp (t.ex. --sol 15 för 15 kWp)")
    p_bat.add_argument("--sol-pris", type=float, default=0,
                       help="Solcellers inköpspris i SEK")
    p_bat.add_argument("--sol-installation", type=float, default=0,
                       help="Solcellers installationskostnad i SEK")
    p_bat.add_argument("--sol-livslängd", type=int, default=25,
                       help="Solcellers livslängd i år (default: 25)")
    p_bat.add_argument("--export-faktor", type=float, default=1.0,
                       help="Andel av spotpris vid försäljning till nät (default: 1.0)")
    p_bat.add_argument("--export-avgift", type=float, default=5.0,
                       help="Leverantörsavgift vid export öre/kWh (default: 5.0)")
    p_bat.add_argument("--källa", choices=["elpris", "entsoe"], default="elpris",
                       help="Datakälla vid hämtning (default: elpris)")
    p_bat.add_argument("--tariff", choices=["tid", "fast", "ingen"], default="tid",
                       help="Nätavgiftsmodell: tid (tidstariff), fast (fast avgift), ingen (default: tid)")
    p_bat.add_argument("--höglast", type=float, default=76.50,
                       help="Tidstariff: höglasttid öre/kWh (default: 76.50)")
    p_bat.add_argument("--låglast", type=float, default=30.50,
                       help="Tidstariff: övrig tid öre/kWh (default: 30.50)")
    p_bat.add_argument("--fast-avgift", type=float, default=44.50,
                       help="Enkeltariff överföringsavgift öre/kWh (default: 44.50)")
    p_bat.add_argument("--energiskatt", type=float, default=54.88,
                       help="Energiskatt inkl. moms öre/kWh (default: 54.88)")
    p_bat.add_argument("--nuvarande-säkring", type=float, default=None, choices=[16, 20, 25, 35, 50, 63],
                       help="Nuvarande säkring innan uppgradering (för att beräkna merkostnad)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        print("\nElområden:")
        for z, name in ZONE_NAMES.items():
            print(f"  {z}: {name}")
        sys.exit(0)

    if args.command == "hämta":
        start = args.datum if isinstance(args.datum, date) else parse_date(args.datum)
        end = args.till or start
        print(f"Hämtar priser för {args.zon} ({ZONE_NAMES[args.zon]}), {start} → {end}...")
        if args.källa == "entsoe":
            from entsoe_source import fetch_entsoe
            rows = fetch_entsoe(start, end, args.zon)
        else:
            rows = fetch_range(start, end, args.zon)
        print_table(rows)
        if args.csv:
            save_csv(rows, args.csv)

    elif args.command == "läs":
        rows = load_csv(args.fil)
        print_table(rows)

    elif args.command == "idag":
        print(f"Dagens elpriser för {args.zon} ({ZONE_NAMES[args.zon]}):")
        rows = fetch_range(date.today(), date.today(), args.zon)
        print_table(rows)

    elif args.command == "imorgon":
        tomorrow = date.today() + timedelta(days=1)
        print(f"Morgondagens elpriser för {args.zon} ({ZONE_NAMES[args.zon]}):")
        rows = fetch_range(tomorrow, tomorrow, args.zon)
        print_table(rows)

    elif args.command == "tibber":
        from tibber_source import (
            fetch_consumption, fetch_prices_tibber, consumption_to_rows,
            consumption_to_load_profile, print_load_profile,
            fetch_daily_consumption, fetch_monthly_consumption,
            print_daily_consumption_summary,
        )

        if args.priser:
            print("Hämtar priser från Tibber...")
            rows = fetch_prices_tibber()
            print_table(rows)

        elif args.dagar is not None:
            daily_nodes = fetch_daily_consumption(days=args.dagar)
            print_daily_consumption_summary(daily_nodes)
            if args.csv:
                daily_rows = []
                for n in daily_nodes:
                    if n.get("consumption") is None:
                        continue
                    from datetime import datetime as dt
                    ts = dt.fromisoformat(n["from"])
                    daily_rows.append({
                        "date": ts.strftime("%Y-%m-%d"),
                        "consumption_kwh": round(n["consumption"], 2),
                        "cost_sek": round(n.get("cost", 0) or 0, 2),
                        "unit_price_sek": round(n.get("unitPrice", 0) or 0, 4),
                    })
                save_csv(daily_rows, args.csv)

        elif args.månader is not None:
            monthly_nodes = fetch_monthly_consumption(months=args.månader)
            for n in monthly_nodes:
                if n.get("consumption") is None:
                    continue
                from datetime import datetime as dt
                ts = dt.fromisoformat(n["from"])
                kwh = n["consumption"]
                cost = n.get("cost", 0) or 0
                print(f"  {ts.strftime('%Y-%m')}: {kwh:>8.0f} kWh, {cost:>8.0f} SEK")

        else:
            print(f"Hämtar {args.timmar} timmar förbrukningsdata från Tibber...")
            nodes = fetch_consumption(hours=args.timmar)
            rows = consumption_to_rows(nodes)
            print_table(rows)

            if args.profil:
                profile = consumption_to_load_profile(nodes)
                print_load_profile(profile)

            if args.csv:
                save_csv(rows, args.csv)

    elif args.command == "batteri":
        from batteri import BatteryConfig, LoadSchedule, FlexibleLoad, simulate, print_summary, print_daily_breakdown
        from tariff import Tidstariff, FastTariff, print_tariff_info

        if args.csv:
            rows = load_csv(args.csv)
        elif args.tibber is not None:
            from tibber_source import fetch_consumption, consumption_to_rows, \
                consumption_to_load_profile, print_load_profile
            print(f"Hämtar {args.tibber} timmar förbrukningsdata från Tibber...")
            nodes = fetch_consumption(hours=args.tibber)
            rows = consumption_to_rows(nodes)
            profile = consumption_to_load_profile(nodes)
            print_load_profile(profile)
        else:
            start = args.datum
            end = args.till or start
            print(f"Hämtar prisdata för {args.zon}, {start} → {end}...")
            if args.källa == "entsoe":
                from entsoe_source import fetch_entsoe
                rows = fetch_entsoe(start, end, args.zon)
            else:
                rows = fetch_range(start, end, args.zon)

        # Load profile: either from Tibber or manual
        hourly_profile = None
        scheduled_loads = []

        if getattr(args, "förbruknings_csv", None):
            from import_consumption import load_consumption_file, consumption_to_hourly_profile, consumption_to_monthly_daily
            print(f"Läser förbrukningsdata från {args.förbruknings_csv}...")
            cons_data = load_consumption_file(args.förbruknings_csv)
            print(f"  Läste {len(cons_data)} datapunkter ({cons_data[0]['date']} → {cons_data[-1]['date']})")

            hourly_profile = consumption_to_hourly_profile(cons_data)

            # Print profile
            total_daily = sum(hourly_profile.values())
            print(f"\n  Förbrukningsprofil från CSV:")
            print(f"  {'Timme':>6} {'kW':>8}")
            print(f"  {'-'*18}")
            for h in range(24):
                bar = "█" * int(hourly_profile[h] * 2)
                print(f"  {h:>4}:00 {hourly_profile[h]:>8.2f} {bar}")
            print(f"  {'-'*18}")
            print(f"  Medel: {total_daily/24:.2f} kW | Dygn: {total_daily:.0f} kWh | År: {total_daily*365.25:,.0f} kWh")

            # Seasonal scaling
            monthly_daily = consumption_to_monthly_daily(cons_data)
            months_with_data = sum(1 for v in monthly_daily.values() if v > 0)
            if months_with_data >= 6:
                seasonal = {}
                for m in range(1, 13):
                    scale = monthly_daily[m] / total_daily if monthly_daily[m] > 0 and total_daily > 0 else 1.0
                    seasonal[m] = {h: hourly_profile[h] * scale for h in range(24)}
                config_kwargs_extra = {"seasonal_load_profile": seasonal}
                print(f"  Säsongsanpassad profil från {months_with_data} månader")
            else:
                config_kwargs_extra = {"hourly_load_profile": hourly_profile}

        elif args.tibber_profil:
            from tibber_source import (
                fetch_consumption, consumption_to_load_profile, print_load_profile,
                fetch_monthly_consumption, build_seasonal_hourly_profile, print_seasonal_profile,
            )
            print("Hämtar förbrukningsprofil från Tibber...")
            hourly_nodes = fetch_consumption(hours=24*30)
            hourly_profile = consumption_to_load_profile(hourly_nodes)
            print_load_profile(hourly_profile)

            # Try to get monthly data for seasonal scaling
            print("Hämtar månadsdata för säsongsanpassning...")
            monthly_nodes = fetch_monthly_consumption(months=36)
            if len(monthly_nodes) >= 6:
                seasonal = build_seasonal_hourly_profile(hourly_nodes, monthly_nodes)
                print_seasonal_profile(seasonal)
                config_kwargs_extra = {"seasonal_load_profile": seasonal}
            else:
                print("  För lite månadsdata för säsongsanpassning, använder fast profil")
                config_kwargs_extra = {"hourly_load_profile": hourly_profile}
        else:
            # Parse scheduled loads: --last elbil:11:23-06
            for spec in args.last:
                try:
                    parts = spec.split(":")
                    name = parts[0]
                    power = float(parts[1])
                    times = parts[2].split("-")
                    start_h = int(times[0])
                    end_h = int(times[1])
                    scheduled_loads.append(LoadSchedule(name=name, power_kw=power,
                                                         start_hour=start_h, end_hour=end_h))
                except (ValueError, IndexError):
                    print(f"  Varning: Kunde inte tolka last '{spec}', format: NAMN:KW:START-SLUT")

        # Parse flexible loads: --flex poolpump:3:20:5-9
        flexible_loads = []
        for spec in args.flex:
            try:
                parts = spec.split(":")
                name = parts[0]
                power = float(parts[1])
                daily_kwh = float(parts[2]) if len(parts) > 2 else 0
                if len(parts) > 3:
                    months = parts[3].split("-")
                    start_m = int(months[0])
                    end_m = int(months[1])
                else:
                    start_m, end_m = 1, 12
                flexible_loads.append(FlexibleLoad(
                    name=name, power_kw=power, daily_kwh=daily_kwh,
                    start_month=start_m, end_month=end_m,
                ))
            except (ValueError, IndexError):
                print(f"  Varning: Kunde inte tolka flex '{spec}', format: NAMN:KW[:DAGKWH:STARTMÅN-SLUTMÅN]")

        if not args.tibber_profil:
            config_kwargs_extra = {
                "scheduled_loads": scheduled_loads,
            }

        config = BatteryConfig(
            capacity_kwh=args.kapacitet,
            max_charge_kw=args.laddeffekt,
            max_discharge_kw=args.urladdeffekt,
            efficiency=args.verkningsgrad,
            fuse_amps=args.säkring,
            phases=args.faser,
            base_load_kw=args.grundlast,
            purchase_price=args.pris,
            installation_cost=args.installation,
            cycle_life=args.cykler,
            calendar_life_years=args.livslängd,
            export_price_factor=args.export_faktor,
            export_fee_ore=args.export_avgift,
            flexible_loads=flexible_loads,
            **config_kwargs_extra,
        )

        tariff = None
        if args.tariff == "tid":
            tariff = Tidstariff(
                peak=getattr(args, "höglast"),
                offpeak=getattr(args, "låglast"),
                energy_tax=args.energiskatt,
                fuse_amps=args.säkring,
            )
        elif args.tariff == "fast":
            tariff = FastTariff(
                flat_rate=args.fast_avgift,
                energy_tax=args.energiskatt,
                fuse_amps=args.säkring,
            )

        if tariff:
            print_tariff_info(tariff)

        # Solar
        solar = None
        if args.sol > 0:
            from solar import SolarConfig
            solar = SolarConfig(
                capacity_kwp=args.sol,
                purchase_price=args.sol_pris,
                installation_cost=args.sol_installation,
                lifetime_years=args.sol_livslängd,
            )

        result = simulate(rows, config, tariff=tariff, solar=solar)
        base_fuse = getattr(args, "nuvarande_säkring", None)
        print_summary(result, tariff=tariff, base_fuse_amps=base_fuse, solar=solar)
        if args.dagvis:
            print_daily_breakdown(result)


if __name__ == "__main__":
    main()
