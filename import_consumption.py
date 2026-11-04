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
    """Load consumption data from any supported file (CSV/Excel/JSON, any encoding)."""
    p = Path(path)
    rows, _info = parse_any_consumption_file(p.name, p.read_bytes())
    return rows


def consumption_to_hourly_profile(data: list[dict]) -> dict[int, float]:
    """Build average hourly load profile (kWh per clock hour ≈ average kW).

    Rows may be hourly or sub-hourly (15-min): values are first summed per
    (date, hour) so four quarter-hours make one hour, then averaged over days.
    """
    per_hour: dict[tuple[str, int], float] = {}
    for row in data:
        key = (row["date"], int(str(row["hour"]).split(":")[0]))
        per_hour[key] = per_hour.get(key, 0.0) + row["consumption_kwh"]

    hourly_sums: dict[int, float] = {h: 0.0 for h in range(24)}
    hourly_counts: dict[int, int] = {h: 0 for h in range(24)}
    for (_d, h), kwh in per_hour.items():
        hourly_sums[h] += kwh
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


# ===========================================================================
# Universal consumption import: parse_any_consumption_file()
# ===========================================================================
#
# One entry point for whatever file a Swedish user downloads from their grid
# company (elnätsbolag), Home Assistant or similar. It sniffs the container
# (CSV/TXT in any common encoding, Excel .xlsx, JSON), finds the table and
# routes to the right layout parser. Output rows are always
#     {"date": "YYYY-MM-DD", "hour": "HH:MM", "consumption_kwh": float}
# in Swedish local time (Europe/Stockholm). Sub-hourly data (15 min) is kept
# as rows with HH:MM = 00/15/30/45; use rows_to_hourly() to aggregate.
#
# What is VERIFIED against real public sources vs ASSUMED (2026-11):
#  - Home Assistant History panel "Download data" (history.csv): VERIFIED from
#    the HA frontend source (src/panels/history/ha-panel-history.ts): header
#    "entity_id,state,last_changed", comma separated, last_changed as
#    JavaScript toISOString() i.e. UTC "2024-01-01T00:00:00.000Z". Long ranges
#    (>10 days) contain hourly long-term statistics rows instead of raw states.
#  - Home Assistant long-term statistics files of the widely used
#    "Import Statistics" custom integration (github.com/klausj1/
#    homeassistant-statistics): VERIFIED from its README: columns
#    statistic_id, start, unit and sum,state (counters) or delta (counters)
#    or mean,min,max (measurements); start default "%d.%m.%Y %H:%M", local
#    time, delimiter tab/comma/semicolon. Database dumps with start_ts epochs
#    are also accepted (assumed layout).
#  - Vattenfall Eldistribution Excel ("Serie" sheet): verified with real files
#    (see import_vattenfall.py).
#  - Greenely CSV "Tid,Elanvändning (kWh)" hourly and a Mälarenergi CSV with
#    "Kvart;Förbrukning;Kostnad;Kostnad, elnät" (quarter-hours, decimal comma)
#    are known only second-hand from forum/search snippets (not seen as files).
#  - Ellevio, E.ON Energidistribution, Göteborg Energi, Jämtkraft, Skellefteå
#    Kraft, Kraftringen (XLSX): no published layouts found. These grid
#    companies publish no file specification (Ei only requires "Excel or CSV").
#    Supported here by GENERIC detection (date/time/Från/Till columns, Swedish
#    or English headers, decimal comma, metadata rows above the header, wide
#    one-row-per-day files, meter readings) — ASSUMED, not verified.

import json
import re
import statistics
from bisect import bisect_left, bisect_right
from datetime import date as _date, time as _time, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Stockholm")


class ConsumptionParseError(ValueError):
    """Raised when a file can't be turned into consumption rows.

    reason: short key (translated in the app as cons_err_<reason>)
    columns: the column headers that were found (shown to the user)
    """

    def __init__(self, reason: str, columns=None, detail: str = ""):
        self.reason = reason
        self.columns = [str(c) for c in (columns or []) if str(c).strip()]
        self.detail = detail
        msg = f"{reason}"
        if detail:
            msg += f": {detail}"
        if self.columns:
            msg += f" (kolumner: {', '.join(self.columns)})"
        super().__init__(msg)


# ---- keywords --------------------------------------------------------------

_CONS_KW = ("förbrukning", "forbrukning", "förbr", "consumption", "elanvändning",
            "användning", "anvandning", "energi", "energy", "kwh", "uttag",
            "mängd", "mangd", "värde", "varde", "value", "volym", "volume",
            "köpt", "import", "delta", "usage", "förbrukat")
_METER_KW = ("mätarställning", "matarstallning", "mätarst", "ställning",
             "stallning", "meter reading", "meterreading", "reading", "zählerstand",
             "ackumulerad", "kumulativ", "cumulative", "räkneverk", "mätarvärde")
_EXCL_SUBSTR = ("kostnad", "cost", "pris", "price", "temp", "status", "kvalitet",
                "quality", "produktion", "production", "inmatning", "export",
                "levererad", "returned", "solar", "mätpunkt", "matpunkt",
                "anläggning", "anlaggning", "nummer", "number", "månad", "month",
                "vecka", "week", "belopp", "amount", "moms", "vat", "summa", "total")
_EXCL_WORDS = {"kr", "sek", "öre", "ore", "id", "år", "year", "dag", "day", "min",
               "max", "mean", "medel", "avg", "typ", "type", "enhet", "unit"}
_END_WORDS = {"till", "to", "slut", "end", "stop", "stopp", "tom", "until",
              "sluttid", "slutdatum", "periodslut", "end_time", "endtime"}
_TIME_HINT = ("tid", "time", "timme", "hour", "kl", "från", "fran", "from", "start",
              "kvart", "period", "intervall", "interval", "datum", "date", "changed",
              "updated", "timestamp")
_MISSING = {"", "-", "unavailable", "unknown", "none", "null", "nan", "n/a", "na"}


def _words(h: str) -> set[str]:
    return set(re.findall(r"[a-zåäöü_]+", h.lower()))


def _is_end_header(h: str) -> bool:
    hl = h.lower().strip()
    return bool(_words(hl) & _END_WORDS) or hl.startswith(("till", "slut"))


def _excluded_header(h: str) -> bool:
    hl = h.lower()
    if any(k in hl for k in _EXCL_SUBSTR):
        return True
    return bool(_words(hl) & _EXCL_WORDS)


def _unit_factor(text: str):
    """Energy unit factor to kWh from a header/unit text, or None if unknown.

    Returns ("energy", f) for kWh/Wh/MWh or ("power", f) for kW/W (f → kW).
    """
    tl = text.lower()
    if re.search(r"mwh", tl):
        return ("energy", 1000.0)
    if re.search(r"kwh", tl):
        return ("energy", 1.0)
    if re.search(r"(?<![a-zåäö])wh\b", tl):
        return ("energy", 0.001)
    if re.search(r"(?<![a-zåäö])kw\b", tl):
        return ("power", 1.0)
    if re.search(r"(?<![a-zåäö])w\b", tl) or re.search(r"\(w\)|\[w\]", tl):
        return ("power", 0.001)
    return None


# ---- cell parsing ----------------------------------------------------------

_RE_ISO = re.compile(
    r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})"
    r"(?:(?:T|\s+|\s*kl\.?\s*)(\d{1,2})[:.](\d{2})(?:[:.](\d{2})(?:[.,]\d+)?)?)?"
    r"\s*(Z|UTC|[+-]\d{2}(?::?\d{2})?)?", re.I)
_RE_ISO_HOURRANGE = re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2})\s*[-–]\s*\d{1,2}\s*$")
_RE_EU = re.compile(
    r"^\s*(\d{1,2})([./])(\d{1,2})[./](\d{4})"
    r"(?:(?:T|[\s,]+)(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?)?"
    r"\s*(Z|UTC|[+-]\d{2}(?::?\d{2})?)?", re.I)
_RE_COMPACT = re.compile(r"^\s*((?:19|20)\d{2})(\d{2})(\d{2})(?:[T\s]?(\d{2}):?(\d{2}))?\s*$")
_RE_TIME = re.compile(
    r"^\s*(?:kl\.?\s*|tim(?:me)?\s*|h\s*|hour\s*)?(\d{1,2})(?:[:.](\d{2}))?(?:[:.]\d{2})?"
    r"\s*(?:[-–]\s*(\d{1,2})(?:[:.]\d{2})?(?:[:.]\d{2})?)?\s*$", re.I)


def _tz_from(s):
    if not s:
        return None
    s = s.upper()
    if s in ("Z", "UTC"):
        return timezone.utc
    sign = 1 if s[0] == "+" else -1
    digits = s[1:].replace(":", "")
    hh = int(digits[:2])
    mm = int(digits[2:4]) if len(digits) >= 4 else 0
    return timezone(sign * timedelta(hours=hh, minutes=mm))


def _parse_dt(cell, dayfirst: bool = True):
    """Parse a date or datetime cell. Returns (datetime, has_time) or None.

    Aware datetimes are returned for ISO strings with Z/offset.
    """
    if cell is None:
        return None
    if isinstance(cell, datetime):
        return cell, (cell.hour, cell.minute, cell.second) != (0, 0, 0)
    if isinstance(cell, _date):
        return datetime(cell.year, cell.month, cell.day), False
    if not isinstance(cell, str):
        return None
    s = cell.strip().strip('"')
    if not s:
        return None
    try:
        m = _RE_ISO.match(s)
        if m:
            y, mo, d = int(m[1]), int(m[2]), int(m[3])
            if m[4] is not None:
                dt = datetime(y, mo, d, int(m[4]) % 24, int(m[5]), int(m[6] or 0))
                if int(m[4]) == 24:
                    dt += timedelta(days=1)
                tz = _tz_from(m[7])
                return (dt.replace(tzinfo=tz) if tz else dt), True
            m2 = _RE_ISO_HOURRANGE.match(s)
            if m2:
                return datetime(y, mo, d, int(m2[4]) % 24), True
            return datetime(y, mo, d), False
        m = _RE_EU.match(s)
        if m:
            a, b, y = int(m[1]), int(m[3]), int(m[4])
            d, mo = (a, b) if (dayfirst or m[2] == ".") else (b, a)
            if m[5] is not None:
                dt = datetime(y, mo, d, int(m[5]) % 24, int(m[6]), int(m[7] or 0))
                if int(m[5]) == 24:
                    dt += timedelta(days=1)
                tz = _tz_from(m[8])
                return (dt.replace(tzinfo=tz) if tz else dt), True
            return datetime(y, mo, d), False
        m = _RE_COMPACT.match(s)
        if m:
            dt = datetime(int(m[1]), int(m[2]), int(m[3]))
            if m[4] is not None:
                return dt.replace(hour=int(m[4]), minute=int(m[5])), True
            return dt, False
    except ValueError:
        return None
    return None


def _parse_time(cell, allow_int: bool = False):
    """Parse a time-of-day cell → (hour, minute) with hour 0..24, or None."""
    if cell is None:
        return None
    if isinstance(cell, _time):
        return cell.hour, cell.minute
    if isinstance(cell, datetime):
        return None
    if isinstance(cell, (int, float)) and not isinstance(cell, bool):
        if allow_int and float(cell).is_integer() and 0 <= cell <= 24:
            return int(cell), 0
        return None
    if not isinstance(cell, str):
        return None
    s = cell.strip().strip('"')
    m = _RE_TIME.match(s)
    if not m:
        return None
    if m[2] is None and m[3] is None and not allow_int and not re.match(r"^\s*(kl|tim|h)", s, re.I):
        return None
    h, mi = int(m[1]), int(m[2] or 0)
    if h > 24 or mi > 59:
        return None
    return h, mi


def _num(cell, comma_decimal: bool = True, delimiter: str = ";"):
    if cell is None or isinstance(cell, bool):
        return None
    if isinstance(cell, (int, float)):
        f = float(cell)
        return None if f != f else f
    if isinstance(cell, (datetime, _date, _time)):
        return None
    s = str(cell).strip()
    if s.lower() in _MISSING:
        return None
    return parse_number(s, comma_decimal, delimiter)


def _nonempty(cell) -> bool:
    return cell is not None and not (isinstance(cell, str) and cell.strip().strip('"') == "")


def _to_utc(local_naive: datetime, fold: int = 0) -> datetime:
    return local_naive.replace(tzinfo=TZ, fold=fold).astimezone(timezone.utc)


def _is_ambiguous(local_naive: datetime) -> bool:
    a = local_naive.replace(tzinfo=TZ, fold=0).utcoffset()
    b = local_naive.replace(tzinfo=TZ, fold=1).utcoffset()
    return a != b


def _local_slots(d: _date, step_min: int) -> list[tuple[int, int]]:
    """Local wall-clock (hour, minute) slots of a day: 23/24/25 hours on DST days."""
    start = datetime(d.year, d.month, d.day, tzinfo=TZ).astimezone(timezone.utc)
    nxt = d + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=TZ).astimezone(timezone.utc)
    n = int((end - start).total_seconds() // (step_min * 60))
    out = []
    for i in range(n):
        lt = (start + timedelta(minutes=step_min * i)).astimezone(TZ)
        out.append((lt.hour, lt.minute))
    return out


def _row(local: datetime, kwh: float) -> dict:
    return {"date": local.strftime("%Y-%m-%d"), "hour": local.strftime("%H:%M"),
            "consumption_kwh": round(kwh, 5)}


def _snap_step(minutes: float) -> int | None:
    for std in (1, 5, 10, 15, 30, 60, 1440):
        if abs(minutes - std) <= max(0.5, std * 0.1):
            return std
    return None


def _median_step_min(instants: list[datetime]) -> float | None:
    uniq = sorted(set(instants))
    diffs = [(b - a).total_seconds() / 60 for a, b in zip(uniq, uniq[1:])]
    diffs = [x for x in diffs if x > 0]
    return statistics.median(diffs) if diffs else None


# ---- containers: bytes → table ---------------------------------------------

def _decode_text(raw: bytes) -> str:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace")
    for enc in ("utf-8", "cp1252", "iso-8859-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _sniff_delimiter(text: str) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()][:60]
    best, best_score = ";", -1
    for d in (";", "\t", ",", "|"):
        try:
            counts = [len(r) - 1 for r in csv.reader(lines, delimiter=d)]
        except csv.Error:
            continue
        nz = [c for c in counts if c > 0]
        if not nz:
            continue
        mode = statistics.mode(nz)
        score = sum(1 for c in counts if c == mode) * (1 + min(mode, 3) * 0.01)
        if score > best_score:
            best, best_score = d, score
    return best


def _text_to_table(text: str):
    delim = _sniff_delimiter(text)
    table = [row for row in csv.reader(io.StringIO(text), delimiter=delim)]
    fmt = detect_csv_format("\n".join(delim.join(r) for r in table))
    comma_dec = delim != "," or fmt["comma_decimal"]
    return table, delim, comma_dec


def _json_to_tables(obj) -> list[list[list]]:
    """Turn a JSON document into candidate tables (header row + data rows)."""
    tables = []

    def from_records(recs):
        keys = []
        for r in recs:
            for k in r:
                if k not in keys:
                    keys.append(k)
        table = [keys] + [[r.get(k) for k in keys] for r in recs]
        tables.append(table)

    def walk(o, depth=0):
        if depth > 8:
            return
        if isinstance(o, list) and o and all(isinstance(x, dict) for x in o[:50]):
            if any(not isinstance(v, (dict, list)) for x in o[:5] for v in x.values()):
                from_records(o)
            for x in o[:20]:  # nested lists, e.g. Tibber homes → consumption → nodes
                for v in x.values():
                    if isinstance(v, (dict, list)):
                        walk(v, depth + 1)
        elif isinstance(o, dict):
            # {"YYYY-MM-DD": [24 values], ...} — wide day layout (e.g. our own
            # simulator export {"consumption": {...}})
            day_lists = {k: v for k, v in o.items()
                         if isinstance(k, str) and _RE_ISO.match(k) and isinstance(v, list)}
            if day_lists and len(day_lists) >= max(1, len(o) // 2):
                width = max(len(v) for v in day_lists.values())
                if width in (23, 24, 25, 92, 96, 100):
                    step = 15 if width > 25 else 60
                    hdr = ["date"] + [f"{(i * step) // 60:02d}:{(i * step) % 60:02d}"
                                      for i in range(width)]
                    tables.append([hdr] + [[k] + list(v) for k, v in sorted(day_lists.items())])
                    return
            # {"sensor.x": [ {start, sum}, ...], ...} — per-statistic lists
            id_lists = {k: v for k, v in o.items()
                        if isinstance(v, list) and v and isinstance(v[0], dict)}
            if id_lists and all(isinstance(k, str) and "." in k for k in id_lists):
                recs = [dict(r, statistic_id=k) for k, v in id_lists.items() for r in v]
                from_records(recs)
                return
            for v in o.values():
                walk(v, depth + 1)

    walk(obj)
    tables.sort(key=len, reverse=True)
    return tables


def _xlsx_tables(raw: bytes) -> tuple[list[tuple[str, list[list]]], list[str]]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    out = []
    try:
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            # trim trailing empty cells
            rows = [r[:max((i + 1 for i, c in enumerate(r) if _nonempty(c)), default=0)] for r in rows]
            out.append((ws.title, rows))
        names = wb.sheetnames
    finally:
        wb.close()
    return out, names


# ---- table analysis --------------------------------------------------------

def _is_data_row(row, dayfirst=True) -> bool:
    has_dt = any(_parse_dt(c, dayfirst) for c in row[:6] if _nonempty(c))
    has_num = any(_num(c) is not None for c in row if _nonempty(c) and not _parse_dt(c, dayfirst))
    return has_dt and has_num


def _find_header(table):
    """Return (header_idx or None, first_data_idx). header None = headerless."""
    first_data = None
    for i, row in enumerate(table[:200]):
        if _is_data_row(row) and all(_is_data_row(r) for r in table[i + 1:i + 3] if any(map(_nonempty, r))):
            first_data = i
            break
    if first_data is None:
        return None, None
    for j in range(first_data - 1, -1, -1):
        cells = [c for c in table[j] if _nonempty(c)]
        if len(cells) >= 2 or (len(cells) == 1 and len(table[first_data]) <= 2):
            return j, first_data
    return None, first_data


def _header_names(table, header_idx, width):
    if header_idx is None:
        return [f"kolumn {i + 1}" for i in range(width)]
    hdr = table[header_idx]
    names = []
    for i in range(width):
        c = hdr[i] if i < len(hdr) else None
        if isinstance(c, _time):
            names.append(f"{c.hour:02d}:{c.minute:02d}")
        elif isinstance(c, datetime):
            names.append(c.strftime("%H:%M") if c.year < 1901 else c.isoformat(sep=" "))
        elif isinstance(c, float) and c.is_integer():
            names.append(str(int(c)))
        else:
            names.append("" if c is None else str(c).strip().strip('"'))
    return names


_RE_HOUR_HDR = re.compile(
    r"^\s*(?:kl\.?\s*|tim(?:me)?\s*|h\s*|hour\s*|t\s*)?(\d{1,2})(?:[:.](\d{2}))?(?:[:.]00)?"
    r"\s*(?:[-–]\s*\d{1,2}(?:[:.]\d{2})?)?\s*(\(2\)|b|\*|'|:a|:b|a)?\s*$", re.I)


def _hour_columns(names):
    """Detect wide-layout hour/quarter columns. Returns list of (col, h, m, dup) or []."""
    found = []
    for i, n in enumerate(names):
        m = _RE_HOUR_HDR.match(n or "")
        if not m:
            continue
        h, mi = int(m[1]), int(m[2] or 0)
        if mi > 59 or h > 96:
            continue
        found.append((i, h, mi, bool(m[3])))
    if len(found) < 23:
        return []
    hours = [h for _, h, mi, _ in found]
    minutes = {mi for _, _, mi, _ in found}
    if max(hours) > 25 and minutes == {0}:
        # quarter numbering 1..96 (or 0..95)
        base = 0 if 0 in hours else 1
        return [(c, (h - base) * 15 // 60, (h - base) * 15 % 60, d) for c, h, mi, d in found]
    if 0 not in hours and minutes == {0}:
        # hour-ending numbering 1..24 (25 = extra autumn hour)
        return [(c, min(h - 1, 23), 0, d or h == 25) for c, h, mi, d in found]
    return found


def _detect_dayfirst(table, start):
    for row in table[start:start + 500]:
        for c in row:
            if isinstance(c, str):
                m = _RE_EU.match(c.strip())
                if m and m[2] == "/":
                    if int(m[1]) > 12:
                        return True
                    if int(m[3]) > 12:
                        return False
    return True


def _choose_entity(groups: dict) -> str:
    def score(name):
        n = name.lower()
        s = 0
        for k in ("energy", "energi", "consumption", "förbrukning", "forbrukning", "import",
                  "kwh", "meter", "mätare", "matare", "total", "accumulated", "grid"):
            if k in n:
                s += 2
        for k in ("export", "production", "produktion", "solar", "sol_", "returned",
                  "cost", "price", "pris", "temperature", "temp", "battery", "voltage",
                  "current", "spanning"):
            if k in n:
                s -= 5
        return s
    return max(groups, key=lambda k: (score(k), len(groups[k])))


# ---- series builders ---------------------------------------------------------

def _cumulative_to_intervals(points, step_min: int, unit_known: bool,
                             gap_limit_h: float = 3.0):
    """Meter readings (utc_instant, cumulative kWh) → [(utc_start, kWh)].

    Readings are unwrapped (meter resets → continue from 0, tiny negative
    jitter → 0, implausible jumps dropped), then linearly interpolated at
    every step boundary and differenced. Intervals whose surrounding readings
    are more than gap_limit_h apart are skipped (missing data, not zero).
    """
    pts = sorted(points)
    dedup = []
    for t, v in pts:
        if dedup and dedup[-1][0] == t:
            dedup[-1] = (t, v)
        else:
            dedup.append((t, v))
    pts = dedup
    if len(pts) < 2:
        return [], 1.0
    raw_d = []
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        d = v1 - v0
        if d < 0:
            d = v1 if v1 < 0.5 * v0 else 0.0  # reset to zero vs jitter
        raw_d.append((d, max((t1 - t0).total_seconds() / 3600, 1e-9)))
    scale = 1.0
    if not unit_known:
        rates = [d / h for d, h in raw_d if d > 0]
        if rates and statistics.median(rates) > 50:  # >50 "kWh"/h is a Wh meter
            scale = 0.001
    times = [pts[0][0]]
    cum = [0.0]
    for (d, h), (t1, _v) in zip(raw_d, pts[1:]):
        d *= scale
        if d / max(h, 0.25) > 60:  # >60 kW sustained: a glitch, not consumption
            d = 0.0
        times.append(t1)
        cum.append(cum[-1] + d)

    def interp(g):
        k = bisect_left(times, g)
        if k < len(times) and times[k] == g:
            return cum[k]
        frac = (g - times[k - 1]).total_seconds() / (times[k] - times[k - 1]).total_seconds()
        return cum[k - 1] + frac * (cum[k] - cum[k - 1])

    gaps_h = [(b - a).total_seconds() / 3600 for a, b in zip(times, times[1:])]
    step = timedelta(minutes=step_min)
    epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)
    n0 = -(-int((times[0] - epoch).total_seconds()) // (step_min * 60))
    g0 = epoch + n0 * step
    out = []
    while g0 + step <= times[-1]:
        g1 = g0 + step
        # readings bracketing [g0, g1]: last one <= g0 .. first one >= g1
        a = bisect_right(times, g0) - 1
        b = bisect_left(times, g1)
        worst = max(gaps_h[a:b], default=0.0)
        if worst <= gap_limit_h:
            out.append((g0, max(0.0, interp(g1) - interp(g0))))
        g0 = g1
    return out, scale


def _power_to_intervals(points, factor_kw: float | None):
    """Step-function power samples (utc, value) → hourly kWh by time integration."""
    pts = sorted(points)
    if len(pts) < 2:
        return []
    if factor_kw is None:
        factor_kw = 0.001 if statistics.median(v for _, v in pts) > 100 else 1.0
    acc: dict[datetime, float] = {}
    for (t0, v), (t1, _) in zip(pts, pts[1:]):
        if (t1 - t0).total_seconds() > 3 * 3600:
            continue
        cur = t0
        while cur < t1:
            hstart = cur.replace(minute=0, second=0, microsecond=0)
            nxt = min(t1, hstart + timedelta(hours=1))
            acc[hstart] = acc.get(hstart, 0.0) + v * factor_kw * (nxt - cur).total_seconds() / 3600
            cur = nxt
    return sorted(acc.items())


def _rows_from_utc(intervals) -> list[dict]:
    return [_row(t.astimezone(TZ).replace(tzinfo=None), kwh) for t, kwh in intervals]


def _stamp_series(stamps):
    """Naive-local/aware datetimes in file order → UTC instants (handles the
    repeated autumn hour by giving the 2nd occurrence fold=1)."""
    seen: dict[datetime, int] = {}
    out = []
    for dt in stamps:
        if dt.tzinfo is not None:
            out.append(dt.astimezone(timezone.utc))
            continue
        fold = 0
        if _is_ambiguous(dt):
            fold = min(seen.get(dt, 0), 1)
            seen[dt] = seen.get(dt, 0) + 1
        out.append(_to_utc(dt, fold))
    return out


# ---- layout parsers ----------------------------------------------------------

def _parse_ha_history(names, data, comma_dec, delim):
    lower = [n.lower() for n in names]
    i_ent = lower.index("entity_id") if "entity_id" in lower else None
    i_state = lower.index("state")
    i_time = lower.index("last_changed") if "last_changed" in lower else lower.index("last_updated")
    groups: dict[str, list] = {}
    for row in data:
        if len(row) <= max(i_state, i_time):
            continue
        v = _num(row[i_state], comma_dec if delim != "," else False, delim)
        p = _parse_dt(row[i_time])
        if v is None or p is None:
            continue  # 'unavailable', 'unknown', empty
        dt = p[0] if p[0].tzinfo else p[0].replace(tzinfo=timezone.utc)  # HA writes UTC
        ent = str(row[i_ent]).strip() if i_ent is not None else "sensor"
        groups.setdefault(ent, []).append((dt.astimezone(timezone.utc), v))
    if not groups:
        raise ConsumptionParseError("no_values", names, "Home Assistant")
    ent = _choose_entity(groups)
    pts = sorted(groups[ent])
    # counter-like steps: increases, or a reset towards zero (daily/monthly meters)
    steps = [(b[1] - a[1] >= -1e-9) or (b[1] < 0.5 * a[1]) for a, b in zip(pts, pts[1:])]
    nonneg = sum(steps) / max(len(steps), 1)
    ent_l = ent.lower()
    if (("power" in ent_l or "effekt" in ent_l) and "energy" not in ent_l) or nonneg < 0.9:
        rows = _rows_from_utc(_power_to_intervals(pts, None))
        return rows, {"format": "ha_history_power", "detail": ent}
    step_min = _snap_step(_median_step_min([t for t, _ in pts]) or 60)
    step_min = 15 if step_min == 15 else 60
    intervals, _scale = _cumulative_to_intervals(pts, step_min, unit_known=False)
    return _rows_from_utc(intervals), {"format": "ha_history", "detail": ent}


def _parse_ha_statistics(names, data, comma_dec, delim, dayfirst):
    lower = [n.lower().strip() for n in names]
    col = {n: i for i, n in enumerate(lower)}
    i_start = col.get("start", col.get("start_ts"))
    i_id = col.get("statistic_id", col.get("entity_id"))
    i_unit = col.get("unit", col.get("unit_of_measurement"))
    kind = next((k for k in ("delta", "sum", "state", "mean") if k in col), None)
    groups: dict[str, list] = {}
    for row in data:
        if len(row) <= max(i_start, col[kind]):
            continue
        sc = row[i_start]
        dt = None
        n = _num(sc, False, ",") if not isinstance(sc, (datetime, _date)) else None
        if n is not None and n > 1e9:
            dt = datetime.fromtimestamp(n / 1000 if n > 1e12 else n, timezone.utc)
        else:
            p = _parse_dt(sc, dayfirst)
            if p:
                dt = p[0]
        v = _num(row[col[kind]], comma_dec, delim)
        if dt is None or v is None:
            continue
        unit = str(row[i_unit]).strip() if i_unit is not None and i_unit < len(row) and row[i_unit] else ""
        sid = str(row[i_id]).strip() if i_id is not None else "statistic"
        groups.setdefault(sid, []).append((dt, v, unit))
    if not groups:
        raise ConsumptionParseError("no_values", names, "Home Assistant statistics")
    sid = _choose_entity(groups)
    recs = groups[sid]
    unit = next((u for _, _, u in recs if u), "")
    uf = _unit_factor(unit) if unit else None
    utc = _stamp_series([dt for dt, _, _ in recs])
    vals = [v for _, v, _ in recs]
    if kind == "mean":
        if not uf or uf[0] != "power":
            raise ConsumptionParseError("power_unknown", names, sid)
        rows = _rows_from_utc([(t, v * uf[1]) for t, v in zip(utc, vals)])
    elif kind == "delta":
        f = uf[1] if uf and uf[0] == "energy" else 1.0
        rows = _rows_from_utc([(t, v * f) for t, v in zip(utc, vals)])
    else:
        # sum/state is the counter value at the END of the period starting at 'start'
        f = uf[1] if uf and uf[0] == "energy" else 1.0
        step = _snap_step(_median_step_min(utc) or 60) or 60
        pts = [(t + timedelta(minutes=step), v * f) for t, v in zip(utc, vals)]
        intervals, _ = _cumulative_to_intervals(pts, 15 if step == 15 else 60, unit_known=bool(uf))
        rows = _rows_from_utc(intervals)
    return rows, {"format": "ha_statistics", "detail": sid}


def _parse_wide(names, data, hour_cols, comma_dec, delim, dayfirst, unit_text):
    hour_set = {c for c, *_ in hour_cols}
    date_col = None
    for i, n in enumerate(names):
        if i in hour_set:
            continue
        vals = [r[i] for r in data[:200] if i < len(r) and _nonempty(r[i])]
        if vals and sum(1 for v in vals if _parse_dt(v, dayfirst)) >= 0.8 * len(vals):
            date_col = i
            break
    if date_col is None:
        raise ConsumptionParseError("no_time", names)
    step = 15 if len(hour_cols) > 30 else 60
    uf = _unit_factor(unit_text)
    factor = uf[1] if uf and uf[0] == "energy" else 1.0
    if uf and uf[0] == "power":
        factor = uf[1] * step / 60
    rows = []
    for r in data:
        if date_col >= len(r):
            continue
        p = _parse_dt(r[date_col], dayfirst)
        if not p:
            continue
        d = p[0].date()
        cells = [(h, m, _num(r[c], comma_dec, delim) if c < len(r) else None)
                 for c, h, m, _dup in hour_cols]
        present = [(h, m, v) for h, m, v in cells if v is not None]
        slots = _local_slots(d, step)
        if len(present) == len(slots):
            mapped = [(sh, sm, v) for (sh, sm), (_h, _m, v) in zip(slots, present)]
        else:
            mapped = present
        for h, m, v in mapped:
            rows.append(_row(datetime(d.year, d.month, d.day, h, m), v * factor))
    return rows, {"format": "wide", "detail": ""}


def _column_stats(names, data, dayfirst):
    stats = []
    sample = data[:400]
    for i, n in enumerate(names):
        vals = [r[i] for r in sample if i < len(r) and _nonempty(r[i])]
        k = len(vals) or 1
        dts = [_parse_dt(v, dayfirst) for v in vals]
        hint = any(h in n.lower() for h in _TIME_HINT)
        times = [_parse_time(v, allow_int=hint) for v in vals]
        nums = [_num(v) for v, d in zip(vals, dts) if not d]
        stats.append({
            "n": len(vals),
            "dt": sum(1 for d in dts if d) / k,
            "has_time": any(d and d[1] for d in dts),
            "aware": any(d and d[0].tzinfo for d in dts),
            "time": sum(1 for x in times if x) / k,
            "num": sum(1 for x in nums if x is not None) / k,
        })
    return stats


def _parse_long(names, data, comma_dec, delim, dayfirst, meta_text):
    st = _column_stats(names, data, dayfirst)
    nrows = len(data)
    dt_cols = [i for i, s in enumerate(st) if s["n"] and s["dt"] >= 0.8]
    if not dt_cols:
        raise ConsumptionParseError("no_time", names)
    start_cols = [i for i in dt_cols if not _is_end_header(names[i])]
    dt_col = (start_cols or dt_cols)[0]
    # prefer a start column that carries a time of day
    timed = [i for i in (start_cols or dt_cols) if st[i]["has_time"]]
    if timed:
        dt_col = timed[0]
    is_end = _is_end_header(names[dt_col]) and not start_cols
    time_col = None
    if not st[dt_col]["has_time"]:
        cand = [i for i, s in enumerate(st) if i != dt_col and i not in dt_cols and s["time"] >= 0.8]
        cand_start = [i for i in cand if not _is_end_header(names[i])]
        if cand_start or cand:
            time_col = (cand_start or cand)[0]
            is_end = is_end or (not cand_start and bool(cand))
    used = {dt_col, time_col} | set(dt_cols)

    # value column
    best, best_score = None, None
    for i, s in enumerate(st):
        if i in used or s["n"] < 0.5 * min(nrows, 400) or s["num"] < 0.6:
            continue
        h = names[i].lower()
        score = 0
        if any(k in h for k in _CONS_KW):
            score += 3
        if any(k in h for k in _METER_KW):
            score += 3
        if _excluded_header(h) and not any(k in h for k in ("förbrukning", "consumption")):
            score -= 10
        uf = _unit_factor(h)
        if uf and uf[0] == "power":
            score -= 1
        if best_score is None or score > best_score:
            best, best_score = i, score
    if best is None or best_score <= -10:
        raise ConsumptionParseError("no_value", names)
    vh = names[best]
    cumulative = any(k in vh.lower() for k in _METER_KW)

    # unit: value header → unit column → metadata → unknown
    uf = _unit_factor(vh)
    unit_col = next((i for i, n in enumerate(names) if n.lower().strip() in ("enhet", "unit", "unit_of_measurement")), None)
    if not uf and unit_col is not None:
        units = {str(r[unit_col]).strip() for r in data[:50] if unit_col < len(r) and r[unit_col]}
        if len(units) == 1:
            uf = _unit_factor(units.pop())
    if not uf:
        uf = _unit_factor(meta_text)

    # build series in file order
    stamps, vals = [], []
    hour_ending = False
    if time_col is not None:
        hour_ending = any((_parse_time(r[time_col], True) or (0, 0))[0] == 24
                          for r in data if time_col < len(r))
    for r in data:
        if dt_col >= len(r) or best >= len(r):
            continue
        p = _parse_dt(r[dt_col], dayfirst)
        v = _num(r[best], comma_dec, delim)
        if p is None or v is None:
            continue
        dt = p[0]
        if time_col is not None:
            tm = _parse_time(r[time_col] if time_col < len(r) else None, True)
            if tm is None:
                continue
            h, mi = tm
            dt = dt.replace(hour=0, minute=0) + timedelta(hours=h, minutes=mi)
            if hour_ending:
                dt -= timedelta(hours=1)
        stamps.append(dt)
        vals.append(v)
    if not stamps:
        raise ConsumptionParseError("no_values", names)
    # files listed newest-first: put in chronological order before fold logic
    if (stamps[0].tzinfo is None) == (stamps[-1].tzinfo is None) and stamps[0] > stamps[-1]:
        stamps.reverse()
        vals.reverse()
    utc = _stamp_series(stamps)
    med = _median_step_min(utc)
    if med is None:
        raise ConsumptionParseError("no_values", names)
    step = _snap_step(med)
    if med >= 20 * 60:
        raise ConsumptionParseError("daily_only", names)

    if not cumulative and len(vals) >= 48:
        # unlabeled meter readings: (almost) never decreasing and large vs steps
        order = sorted(range(len(utc)), key=lambda k: utc[k])
        sv = [vals[k] for k in order]
        diffs = [b - a for a, b in zip(sv, sv[1:])]
        pos = [d for d in diffs if d > 0]
        if (pos and sum(1 for d in diffs if d >= 0) >= 0.98 * len(diffs)
                and statistics.median(sv) > 200 * statistics.median(pos)):
            cumulative = True

    if cumulative:
        f = uf[1] if uf and uf[0] == "energy" else 1.0
        gstep = step if step in (15, 30, 60) else 60
        # a reading's timestamp is an instant: Från/Till makes no difference here
        intervals, _ = _cumulative_to_intervals([(t, v * f) for t, v in zip(utc, vals)],
                                                gstep, unit_known=bool(uf))
        return _rows_from_utc(intervals), {"format": "meter", "detail": vh}

    if step is None:
        raise ConsumptionParseError("irregular", names)
    if uf and uf[0] == "power":
        factor = uf[1] * step / 60
    elif uf:
        factor = uf[1]
    else:
        factor = 1.0
        per_hour = [v * 60 / step for v in vals]
        if per_hour and statistics.median(per_hour) > 100:  # no unit + huge: Wh
            factor = 0.001
    shift = timedelta(minutes=step) if is_end else timedelta(0)
    rows = [_row((t - shift).astimezone(TZ).replace(tzinfo=None), v * factor)
            for t, v in zip(utc, vals)]
    return rows, {"format": "long", "detail": vh}


def parse_consumption_table(table: list[list], delim: str = ";", comma_dec: bool = True):
    """Parse a generic table (rows of cells: str/number/datetime) → (rows, info)."""
    table = [list(r) for r in table if r is not None]
    while table and not any(map(_nonempty, table[-1])):
        table.pop()
    if not table:
        raise ConsumptionParseError("empty")

    # Home Assistant headers are recognised before generic heuristics
    for hi, row in enumerate(table[:30]):
        lower = [str(c).strip().lower() if c is not None else "" for c in row]
        if "state" in lower and ("last_changed" in lower or "last_updated" in lower):
            return _parse_ha_history(lower, table[hi + 1:], comma_dec, delim)
        if ("start" in lower or "start_ts" in lower) and any(k in lower for k in ("sum", "delta", "state", "mean")):
            data = table[hi + 1:]
            return _parse_ha_statistics(lower, data, comma_dec, delim, _detect_dayfirst(table, hi + 1))

    # wide layout: a header row with >= 23 hour columns
    for hi, row in enumerate(table[:40]):
        names = _header_names(table, hi, max(len(r) for r in table[hi:hi + 5]))
        hcols = _hour_columns(names)
        if hcols:
            data = [r for r in table[hi + 1:] if any(map(_nonempty, r))]
            meta = " ".join(str(c) for r in table[:hi + 1] for c in r if c is not None)
            return _parse_wide(names, data, hcols, comma_dec, delim,
                               _detect_dayfirst(table, hi + 1), meta)

    header_idx, first_data = _find_header(table)
    width = max(len(r) for r in table)
    if first_data is None:
        hdr = next((r for r in table if sum(map(_nonempty, r)) >= 2), table[0])
        raise ConsumptionParseError("no_time", _header_names([hdr], 0, len(hdr)))
    names = _header_names(table, header_idx, width)
    data = [r for r in table[first_data:] if any(map(_nonempty, r))]
    meta_text = " ".join(str(c) for r in table[:first_data] for c in r if c is not None)
    return _parse_long(names, data, comma_dec, delim, _detect_dayfirst(table, first_data), meta_text)


def _finish(rows, info, container, names_for_error=None):
    if not rows:
        raise ConsumptionParseError("no_values", names_for_error or [])
    if not any(r["consumption_kwh"] for r in rows):
        raise ConsumptionParseError("all_zero", names_for_error or [])
    rows.sort(key=lambda r: (r["date"], r["hour"]))
    info = dict(info)
    info["container"] = container
    mins = {r["hour"][3:] for r in rows}
    info["resolution_min"] = 60 if mins == {"00"} else (15 if mins <= {"00", "15", "30", "45"} else 0)
    return rows, info


def parse_any_consumption_file(name: str, raw: bytes):
    """Parse any supported consumption file.

    Returns (rows, info): rows as described at the top of this section;
    info = {"format": key, "detail": str, "container": "CSV"|"Excel"|"JSON",
            "resolution_min": 15|60|0}. format keys: vattenfall_excel, long,
    wide, meter, ha_history, ha_history_power, ha_statistics.
    Raises ConsumptionParseError (a ValueError) with .reason and .columns.
    """
    lname = (name or "").lower()
    if raw[:4] == b"\xd0\xcf\x11\xe0":
        raise ConsumptionParseError("xls_old")
    if raw[:2] == b"PK":
        tables, sheetnames = _xlsx_tables(raw)
        if "Serie" in sheetnames:
            import os
            import tempfile
            from import_vattenfall import parse_vattenfall_hourly
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name
            try:
                hourly = parse_vattenfall_hourly(tmp_path)
            finally:
                os.unlink(tmp_path)
            if hourly:
                rows = [{"date": h["date"], "hour": f"{h['hour']:02d}:00",
                         "consumption_kwh": h["kwh"]} for h in hourly]
                return _finish(rows, {"format": "vattenfall_excel", "detail": ""}, "Excel")
            # Vattenfall workbook without hourly columns: caller may use daily totals
            raise ConsumptionParseError("vattenfall_no_hourly", ["Serie"])
        best, best_err = None, None
        for _title, tbl in tables:
            try:
                rows, info = parse_consumption_table(tbl, ";", True)
            except ConsumptionParseError as e:
                if best_err is None or (e.columns and not best_err.columns):
                    best_err = e
                continue
            if rows and (best is None or len(rows) > len(best[0])):
                best = (rows, info)
        if best:
            return _finish(best[0], best[1], "Excel")
        raise best_err or ConsumptionParseError("empty")

    text = _decode_text(raw)
    stripped = text.lstrip()
    if lname.endswith(".json") or stripped[:1] in ("{", "["):
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            obj = None
        if obj is not None:
            last_err = None
            for tbl in _json_to_tables(obj):
                try:
                    rows, info = parse_consumption_table(tbl, ",", False)
                    return _finish(rows, info, "JSON", tbl[0])
                except ConsumptionParseError as e:
                    last_err = e
            raise last_err or ConsumptionParseError("no_table")

    table, delim, comma_dec = _text_to_table(text)
    rows, info = parse_consumption_table(table, delim, comma_dec)
    return _finish(rows, info, "CSV")


def rows_to_hourly(rows: list[dict]) -> list[dict]:
    """Aggregate rows (hourly or 15-min) → [{"date", "hour": int, "kwh"}] per
    local clock hour (both autumn 02:00 hours are summed into one)."""
    acc: dict[tuple[str, int], float] = {}
    for r in rows:
        key = (r["date"], int(str(r["hour"]).split(":")[0]))
        acc[key] = acc.get(key, 0.0) + r["consumption_kwh"]
    return [{"date": d, "hour": h, "kwh": round(v, 4)} for (d, h), v in sorted(acc.items())]
