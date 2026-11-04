"""
Import consumption data from Swedish grid operators.

Supports:
- Vattenfall Eldistribution CSV (downloaded from Mina sidor)
- Generic CSV with date + hour + consumption columns
- Tibber API (see tibber_source.py)

Swedish CSVs typically use:
- Semicolon delimiter
- Comma as decimal separator
- ISO 8859-1 or UTF-8 encoding
"""

import csv
import io
from datetime import datetime
from pathlib import Path


def detect_csv_format(content: str) -> dict:
    """Detect delimiter, decimal separator, and encoding of a CSV."""
    lines = content.split("\n")
    header = lines[0] if lines else ""

    # Detect delimiter
    if ";" in header:
        delimiter = ";"
    elif "\t" in header:
        delimiter = "\t"
    else:
        delimiter = ","

    # Detect decimal separator (look for numbers with comma) — scan the whole
    # file, a "1,5" row may appear far below rows of integers like "0" or "2".
    has_comma_decimal = False
    for line in lines[1:]:
        fields = line.split(delimiter)
        for f in fields:
            f = f.strip().strip('"')
            for ch in (" ", "\xa0", "\u202f"):
                f = f.replace(ch, "")
            # Pattern like "1,234" or "0,5" (not "1,234,567")
            if "," in f and f.replace(",", "").replace(".", "").replace("-", "").isdigit():
                parts = f.split(",")
                if len(parts) == 2 and len(parts[1]) <= 4:
                    has_comma_decimal = True
                    break
        if has_comma_decimal:
            break

    return {
        "delimiter": delimiter,
        "comma_decimal": has_comma_decimal,
    }


def parse_number(value: str, comma_decimal: bool = False, delimiter: str = ";") -> float | None:
    """Parse a numeric CSV cell tolerantly. Returns None if not a number.

    Handles Swedish formats: "1,5", "1 234,5" (space/nbsp thousands
    separators), "1.234,5", as well as English "1,234.5" and "1.5".
    A lone comma is treated as decimal separator when the file uses comma
    decimals or when ',' is not the field delimiter.
    """
    s = value.strip().strip('"').strip()
    for ch in (" ", "\xa0", "\u202f", "'"):
        s = s.replace(ch, "")
    if not s or s == "-":
        return None
    if "," in s and "." in s:
        # Whichever separator comes last is the decimal separator
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        if comma_decimal or delimiter != "," or s.count(",") == 1 and len(s.split(",")[1]) != 3:
            if s.count(",") > 1:
                return None
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_consumption_csv(content: str, filename: str = "") -> list[dict]:
    """
    Parse a consumption CSV file into a list of dicts with:
    - date (YYYY-MM-DD)
    - hour (HH:MM)
    - consumption_kwh (float)

    Handles Vattenfall Eldistribution format and common Swedish CSV variants.
    """
    fmt = detect_csv_format(content)
    delimiter = fmt["delimiter"]
    comma_decimal = fmt["comma_decimal"]

    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    rows_raw = list(reader)

    if not rows_raw:
        return []

    # Find header row (might have metadata rows before it)
    header_idx = 0
    header = rows_raw[0]
    for i, row in enumerate(rows_raw[:10]):
        row_lower = [c.strip().lower() for c in row]
        if any(kw in " ".join(row_lower) for kw in ["datum", "date", "tid", "time", "förbrukning", "consumption", "kwh", "mätarställning"]):
            header_idx = i
            header = row
            break

    header_lower = [h.strip().lower() for h in header]

    # Find relevant columns
    date_col = None
    time_col = None
    consumption_col = None

    for i, h in enumerate(header_lower):
        if any(kw in h for kw in ["datum", "date", "från", "from", "starttid"]):
            if date_col is None:
                date_col = i
        if any(kw in h for kw in ["tid", "time", "timme", "hour"]) and "starttid" not in h:
            time_col = i
        if any(kw in h for kw in ["förbrukning", "consumption", "energi", "energy", "kwh", "mängd"]):
            consumption_col = i

    # If no separate time column, date column might contain datetime
    if date_col is None:
        # Try first column as date
        date_col = 0
    if consumption_col is None:
        # Try last numeric column
        for i in range(len(header) - 1, -1, -1):
            if i != date_col and i != time_col:
                consumption_col = i
                break

    if consumption_col is None:
        raise ValueError(f"Kunde inte hitta förbrukningskolumn i CSV. Kolumner: {header}")

    results = []
    for row in rows_raw[header_idx + 1:]:
        if len(row) <= max(c for c in [date_col, time_col, consumption_col] if c is not None):
            continue

        # Parse date/time
        date_str = row[date_col].strip().strip('"') if date_col is not None else ""
        time_str = row[time_col].strip().strip('"') if time_col is not None else ""

        # Try to parse datetime from date column
        dt = None
        for fmt_str in ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M",
                        "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d"]:
            try:
                dt = datetime.strptime(date_str, fmt_str)
                break
            except ValueError:
                continue

        if dt is None and time_str:
            # Try date + time separately
            for fmt_str in ["%Y-%m-%d", "%d/%m/%Y"]:
                try:
                    d = datetime.strptime(date_str, fmt_str)
                    # Parse time
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
            continue  # Skip unparseable rows

        # Parse consumption
        consumption = parse_number(row[consumption_col], comma_decimal, delimiter)
        if consumption is None:
            continue

        results.append({
            "date": dt.strftime("%Y-%m-%d"),
            "hour": dt.strftime("%H:%M"),
            "consumption_kwh": round(consumption, 4),
        })

    return results


def load_consumption_file(path: str) -> list[dict]:
    """Load consumption data from a file, trying different encodings."""
    p = Path(path)
    for encoding in ["utf-8", "utf-8-sig", "iso-8859-1", "cp1252"]:
        try:
            content = p.read_text(encoding=encoding)
            return parse_consumption_csv(content, p.name)
        except (UnicodeDecodeError, ValueError):
            continue
    raise ValueError(f"Kunde inte läsa {path} med någon känd teckenkodning")


def consumption_to_hourly_profile(data: list[dict]) -> dict[int, float]:
    """Build average hourly load profile from consumption data."""
    hourly_sums: dict[int, float] = {h: 0.0 for h in range(24)}
    hourly_counts: dict[int, int] = {h: 0 for h in range(24)}

    for row in data:
        h = int(row["hour"].split(":")[0])
        hourly_sums[h] += row["consumption_kwh"]
        hourly_counts[h] += 1

    profile = {}
    for h in range(24):
        if hourly_counts[h] > 0:
            profile[h] = hourly_sums[h] / hourly_counts[h]
        else:
            profile[h] = 0.0
    return profile


def consumption_to_monthly_daily(data: list[dict]) -> dict[int, float]:
    """Build average daily consumption per month."""
    from collections import defaultdict
    monthly_days: dict[int, set] = defaultdict(set)
    monthly_kwh: dict[int, float] = defaultdict(float)

    for row in data:
        m = int(row["date"].split("-")[1])
        monthly_days[m].add(row["date"])
        monthly_kwh[m] += row["consumption_kwh"]

    profile = {}
    for m in range(1, 13):
        if monthly_days[m]:
            profile[m] = monthly_kwh[m] / len(monthly_days[m])
        else:
            profile[m] = 0.0
    return profile
