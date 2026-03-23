"""
Import solar production data from CSV files.

Supports common inverter portal exports:
- Huawei FusionSolar (timestamp + kWh)
- SMA Sunny Portal (date, time, power/energy columns)
- Fronius Solar.web
- Enphase Enlighten
- Generic CSV with date/time + production/energy/power columns

Swedish CSVs typically use semicolon delimiter and comma decimal separator.
"""

import csv
import io
from datetime import datetime


def detect_csv_format(content: str) -> dict:
    """Detect delimiter and decimal separator."""
    first_lines = content.split("\n")[:5]
    header = first_lines[0] if first_lines else ""

    if ";" in header:
        delimiter = ";"
    elif "\t" in header:
        delimiter = "\t"
    else:
        delimiter = ","

    has_comma_decimal = False
    for line in first_lines[1:]:
        fields = line.split(delimiter)
        for f in fields:
            f = f.strip().strip('"')
            if "," in f and f.replace(",", "").replace(".", "").replace("-", "").isdigit():
                parts = f.split(",")
                if len(parts) == 2 and len(parts[1]) <= 4:
                    has_comma_decimal = True

    return {"delimiter": delimiter, "comma_decimal": has_comma_decimal}


def parse_solar_csv(content: str, filename: str = "") -> list[dict]:
    """
    Parse a solar production CSV into hourly records.

    Returns list of dicts with:
    - date (YYYY-MM-DD)
    - hour (HH:00)
    - production_kwh (float)

    Handles various inverter export formats automatically.
    """
    fmt = detect_csv_format(content)
    delimiter = fmt["delimiter"]
    comma_decimal = fmt["comma_decimal"]

    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    rows_raw = list(reader)

    if not rows_raw:
        return []

    # Find header row (skip metadata rows)
    header_idx = 0
    header = rows_raw[0]
    for i, row in enumerate(rows_raw[:10]):
        row_lower = [c.strip().lower() for c in row]
        joined = " ".join(row_lower)
        if any(kw in joined for kw in [
            "datum", "date", "tid", "time", "timestamp",
            "produktion", "production", "energy", "energi",
            "power", "effekt", "yield", "kwh", "kw",
        ]):
            header_idx = i
            header = row
            break

    header_lower = [h.strip().lower() for h in header]

    # Find columns
    date_col = None
    time_col = None
    prod_col = None

    for i, h in enumerate(header_lower):
        if any(kw in h for kw in ["datum", "date", "från", "from", "starttid", "timestamp"]):
            if date_col is None:
                date_col = i
        if any(kw in h for kw in ["tid", "time", "timme", "hour"]) and "starttid" not in h:
            if time_col is None:
                time_col = i
        if any(kw in h for kw in [
            "produktion", "production", "yield", "energi", "energy",
            "kwh", "genererad", "generated", "effekt", "power",
        ]):
            if prod_col is None:
                prod_col = i

    if date_col is None:
        date_col = 0
    if prod_col is None:
        # Try last numeric column (skip date/time)
        for i in range(len(header) - 1, -1, -1):
            if i != date_col and i != time_col:
                prod_col = i
                break

    if prod_col is None:
        raise ValueError(f"Kunde inte hitta produktionskolumn i CSV. Kolumner: {header}")

    results = []
    for row in rows_raw[header_idx + 1:]:
        max_col = max(c for c in [date_col, time_col, prod_col] if c is not None)
        if len(row) <= max_col:
            continue

        date_str = row[date_col].strip().strip('"') if date_col is not None else ""
        time_str = row[time_col].strip().strip('"') if time_col is not None else ""

        # Parse datetime — try separate date+time first if time column exists
        dt = None
        if time_str:
            for fmt_str in ["%Y-%m-%d", "%d/%m/%Y"]:
                try:
                    d = datetime.strptime(date_str, fmt_str)
                    for t_fmt in ["%H:%M", "%H:%M:%S", "%H"]:
                        try:
                            t = datetime.strptime(time_str, t_fmt)
                            dt = d.replace(hour=t.hour, minute=t.minute)
                            break
                        except ValueError:
                            continue
                    if dt:
                        break
                except ValueError:
                    continue

        if dt is None:
            # Try combined datetime in date column
            clean = date_str.split("+")[0].split("Z")[0]
            for fmt_str in ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M",
                            "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d"]:
                try:
                    dt = datetime.strptime(clean, fmt_str)
                    break
                except ValueError:
                    continue

        if dt is None:
            continue

        # Parse production value
        prod_str = row[prod_col].strip().strip('"')
        if not prod_str or prod_str == "-":
            continue
        if comma_decimal:
            prod_str = prod_str.replace(",", ".")
        try:
            production = float(prod_str)
        except ValueError:
            continue

        if production < 0:
            continue  # Skip negative values (some inverters log consumption as negative)

        results.append({
            "date": dt.strftime("%Y-%m-%d"),
            "hour": dt.strftime("%H:00"),
            "production_kwh": round(production, 4),
        })

    return results


def solar_to_hourly_dict(records: list[dict]) -> dict[str, float]:
    """
    Convert parsed solar records to lookup dict: "YYYY-MM-DD HH:00" -> kW.

    For hourly data, kWh ≈ kW average for that hour.
    If multiple records exist for the same hour, they are summed
    (handles sub-hourly data like 15-min intervals).
    """
    result: dict[str, float] = {}
    for r in records:
        key = f"{r['date']} {r['hour']}"
        result[key] = result.get(key, 0) + r["production_kwh"]
    return result


def solar_to_monthly_kwh(records: list[dict]) -> dict[int, float]:
    """
    Aggregate solar records to average monthly production in kWh.
    Returns dict mapping month (1-12) -> avg kWh/month.
    """
    ym_totals: dict[tuple[int, int], float] = {}
    for r in records:
        m = int(r["date"].split("-")[1])
        y = int(r["date"].split("-")[0])
        key = (y, m)
        ym_totals[key] = ym_totals.get(key, 0) + r["production_kwh"]

    monthly: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    for (y, m), total in ym_totals.items():
        monthly[m].append(total)

    return {m: (sum(vals) / len(vals) if vals else 0.0) for m, vals in monthly.items()}
