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
import re
from datetime import datetime

# Shared tolerant format detection / number parsing (decimal comma, thousands
# separators) — same rules for consumption and production CSVs.
from import_consumption import detect_csv_format, parse_number

_ENERGY_KEYWORDS = ["produktion", "production", "yield", "energi", "energy",
                    "genererad", "generated", "kwh"]
_POWER_KEYWORDS = ["effekt", "power"]


def _column_unit(header: str) -> str | None:
    """Return unit found in a column header: 'kwh', 'wh', 'kw', 'w' or None."""
    for unit in ("kwh", "wh", "kw", "w"):
        if re.search(rf"(?<![a-z]){unit}(?![a-z])", header):
            return unit
    return None


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

    # Pick production column: prefer an energy column (kWh/Wh) over a power
    # column (W/kW) — exports often contain both, e.g. "Power (W)" + "Energy (kWh)".
    energy_cols = []
    power_cols = []
    for i, h in enumerate(header_lower):
        if i in (date_col, time_col):
            continue
        unit = _column_unit(h)
        if unit in ("kwh", "wh"):
            energy_cols.append((0, i))
        elif unit in ("kw", "w") or any(kw in h for kw in _POWER_KEYWORDS):
            power_cols.append(i)
        elif any(kw in h for kw in _ENERGY_KEYWORDS):
            energy_cols.append((1, i))
    is_power = False
    scale = 1.0
    if energy_cols:
        prod_col = min(energy_cols)[1]
        if _column_unit(header_lower[prod_col]) == "wh":
            scale = 0.001
    elif power_cols:
        prod_col = power_cols[0]
        is_power = True
        if _column_unit(header_lower[prod_col]) == "w":
            scale = 0.001  # W -> kW

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

    samples: dict[tuple[str, str], list[float]] = {}
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
        production = parse_number(row[prod_col], comma_decimal, delimiter)
        if production is None:
            continue

        if production < 0:
            continue  # Skip negative values (some inverters log consumption as negative)

        key = (dt.strftime("%Y-%m-%d"), dt.strftime("%H:00"))
        samples.setdefault(key, []).append(production * scale)

    # Aggregate to one record per hour: energy samples (kWh) are summed,
    # power samples (kW) are averaged — mean kW over an hour == kWh that hour.
    results = []
    for (d, h), vals in samples.items():
        kwh = sum(vals) / len(vals) if is_power else sum(vals)
        results.append({
            "date": d,
            "hour": h,
            "production_kwh": round(kwh, 4),
        })

    return results


def solar_to_hourly_dict(records: list[dict]) -> dict[str, float]:
    """
    Convert parsed solar records to lookup dict: "YYYY-MM-DD HH:00" -> kW.

    For hourly data, kWh ≈ kW average for that hour.
    parse_solar_csv() already aggregates sub-hourly samples per hour (energy
    summed, power averaged); any remaining duplicates are summed as energy.
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
