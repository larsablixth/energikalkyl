"""
Import consumption data from Vattenfall Eldistribution Excel files.

Vattenfall format (Serie sheet):
- Row 0: year
- Row 1: headers with month names in columns 11-22 (Jan-Dec)
- Row 2: column labels
- Row 3+: one row per day of month
  - Col 0: month name (jan., feb., ...)
  - Col 2: day of month (1-31)
  - Cols 11-22: daily kWh per month (only the column matching current month has data)

Since the Tim sheets use cross-sheet formulas that openpyxl can't evaluate,
we extract daily data from the Serie sheet and combine with Tibber hourly
shape for the simulation.
"""

import openpyxl
from datetime import date
from pathlib import Path


MONTH_MAP = {
    "jan": 1, "jan.": 1, "januari": 1,
    "feb": 2, "feb.": 2, "februari": 2,
    "mar": 3, "mar.": 3, "mars": 3,
    "apr": 4, "apr.": 4, "april": 4,
    "maj": 5, "maj.": 5,
    "jun": 6, "jun.": 6, "juni": 6,
    "jul": 7, "jul.": 7, "juli": 7,
    "aug": 8, "aug.": 8, "augusti": 8,
    "sep": 9, "sep.": 9, "sept": 9, "sept.": 9, "september": 9,
    "okt": 10, "okt.": 10, "oktober": 10,
    "nov": 11, "nov.": 11, "november": 11,
    "dec": 12, "dec.": 12, "december": 12,
}


def parse_vattenfall_excel(path: str) -> list[dict]:
    """
    Parse a Vattenfall Eldistribution Excel file.
    Returns list of dicts with date, consumption_kwh (daily totals).
    """
    wb = openpyxl.load_workbook(path, data_only=True)

    if "Serie" not in wb.sheetnames:
        raise ValueError(f"Hittade inte 'Serie'-bladet i {path}. Blad: {wb.sheetnames}")

    ws = wb["Serie"]
    rows = list(ws.iter_rows(values_only=True))

    # Row 0: year
    year = None
    for cell in rows[0]:
        if isinstance(cell, (int, float)) and 2000 <= cell <= 2100:
            year = int(cell)
            break
    if year is None:
        raise ValueError("Kunde inte hitta årstal i filen")

    # Parse data rows (row 3+)
    # Column 0 = month name, column 2 = day of month, column 6 = daily total kWh
    results = []
    for row_idx in range(3, len(rows)):
        row = rows[row_idx]
        if row is None:
            continue

        month_cell = row[0]
        day_cell = row[2]

        if not isinstance(month_cell, str):
            continue
        month_str = month_cell.strip().lower()
        if month_str not in MONTH_MAP:
            continue
        month_num = MONTH_MAP[month_str]

        if not isinstance(day_cell, (int, float)) or day_cell < 1 or day_cell > 31:
            continue
        day = int(day_cell)

        # Use column 6 (Summa/dag) for daily total
        value = row[6] if len(row) > 6 else None
        if value is None or not isinstance(value, (int, float)):
            continue

        try:
            d = date(year, month_num, day)
        except ValueError:
            continue

        results.append({
            "date": d.isoformat(),
            "consumption_kwh": round(float(value), 4),
        })

    wb.close()
    print(f"  År: {year}, {len(results)} dagar med data")
    return results


def load_vattenfall_files(*paths: str) -> list[dict]:
    """Load and merge multiple Vattenfall Excel files."""
    all_data = []
    for path in paths:
        print(f"  Läser {Path(path).name}...")
        data = parse_vattenfall_excel(path)
        all_data.extend(data)

    # Sort and deduplicate
    all_data.sort(key=lambda r: r["date"])
    seen = set()
    unique = []
    for r in all_data:
        if r["date"] not in seen:
            seen.add(r["date"])
            unique.append(r)

    if unique:
        total_kwh = sum(r["consumption_kwh"] for r in unique)
        num_days = len(unique)
        print(f"  Totalt: {num_days} dagar, {unique[0]['date']} → {unique[-1]['date']}")
        print(f"  Total förbrukning: {total_kwh:,.0f} kWh")
        print(f"  Snitt: {total_kwh/num_days:.0f} kWh/dag | {total_kwh/num_days*365.25:,.0f} kWh/år")

    return unique


def vattenfall_to_monthly_profile(data: list[dict]) -> dict[int, float]:
    """
    Build average daily consumption per month from Vattenfall daily data.
    Returns dict mapping month (1-12) to average kWh/day.
    """
    from collections import defaultdict
    monthly_sums = defaultdict(float)
    monthly_counts = defaultdict(int)

    for r in data:
        m = int(r["date"].split("-")[1])
        monthly_sums[m] += r["consumption_kwh"]
        monthly_counts[m] += 1

    profile = {}
    for m in range(1, 13):
        if monthly_counts[m] > 0:
            profile[m] = monthly_sums[m] / monthly_counts[m]
        else:
            profile[m] = 0.0
    return profile


def vattenfall_to_seasonal_profile(daily_data: list[dict], hourly_shape: dict[int, float] = None) -> dict[int, dict[int, float]]:
    """
    Build seasonal hourly profile from Vattenfall daily data.

    Uses monthly averages from Vattenfall to scale an hourly shape.
    If no hourly_shape is provided, uses a default residential profile.

    Returns dict: month -> hour -> kW
    """
    monthly_daily = vattenfall_to_monthly_profile(daily_data)

    # Default hourly shape if none provided (typical Swedish household)
    if hourly_shape is None:
        hourly_shape = {
            0: 3.0, 1: 2.5, 2: 2.0, 3: 2.0, 4: 2.0, 5: 2.5,
            6: 3.5, 7: 4.0, 8: 3.5, 9: 3.0, 10: 2.5, 11: 2.5,
            12: 2.5, 13: 2.5, 14: 2.5, 15: 3.0, 16: 3.5, 17: 4.0,
            18: 4.5, 19: 4.0, 20: 3.5, 21: 3.0, 22: 3.0, 23: 3.0,
        }

    base_daily_kwh = sum(hourly_shape.values())
    if base_daily_kwh == 0:
        return {m: {h: 0.0 for h in range(24)} for m in range(1, 13)}

    seasonal = {}
    for m in range(1, 13):
        if monthly_daily[m] > 0:
            scale = monthly_daily[m] / base_daily_kwh
        else:
            scale = 1.0
        seasonal[m] = {h: hourly_shape[h] * scale for h in range(24)}

    return seasonal


def print_vattenfall_summary(data: list[dict]):
    """Print monthly consumption summary."""
    months_sv = ["", "Jan", "Feb", "Mar", "Apr", "Maj", "Jun",
                 "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]
    profile = vattenfall_to_monthly_profile(data)

    print(f"\n  Vattenfall förbrukningsprofil:")
    print(f"  {'Månad':>6} {'kWh/dag':>10} {'kWh/mån':>10}")
    print(f"  {'-'*30}")
    for m in range(1, 13):
        kwh = profile[m]
        kwh_month = kwh * 30.44
        bar = "█" * int(kwh / 3)
        print(f"  {months_sv[m]:>5}  {kwh:>8.1f}  {kwh_month:>8.0f}  {bar}")
    total = sum(profile[m] * 30.44 for m in range(1, 13))
    print(f"  {'-'*30}")
    print(f"  {'Total':>5}  {total/365.25:>8.1f}  {total:>8.0f}")
