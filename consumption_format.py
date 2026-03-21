"""
Standard consumption data format for Energikalkyl.

All provider-specific converters produce this JSON format. The app reads only
this format. Converters handle the messy provider-specific parsing separately.

If your grid operator is not supported by the included converters, you can
write your own. The only requirement is that the output matches the JSON
schema below.


JSON Schema
===========

{
    "version": 1,                        # REQUIRED. Always 1.
    "source": "vattenfall",              # REQUIRED. Provider name (free text).
    "metering_point": "735999...",       # Optional. Swedish metering point ID
                                         #   (anläggnings-id), 18 digits.
    "unit": "kWh",                       # REQUIRED. Always "kWh".
    "resolution": "hourly",              # REQUIRED. Always "hourly".
    "period": {                          # REQUIRED. Date range of the data.
        "start": "2023-01-01",           #   ISO 8601 date (YYYY-MM-DD).
        "end": "2025-12-31"              #   Inclusive.
    },
    "summary": {                         # REQUIRED. Pre-computed statistics.
        "total_kwh": 66000,              #   Sum of all kwh values.
        "days": 1095,                    #   Number of unique dates.
        "avg_kwh_per_day": 60.3          #   total_kwh / days.
    },
    "data": [                            # REQUIRED. One entry per hour.
        {
            "date": "2023-01-01",        #   ISO 8601 date (YYYY-MM-DD).
            "hour": 0,                   #   Hour of day, 0-23 (integer).
            "kwh": 2.31                  #   Consumption in kWh (float, >= 0).
        },
        ...
    ]
}


Field details
-------------

- **version**: Must be 1. Future format changes will increment this.
- **source**: Free-text provider name. Used for display only. Examples:
  "vattenfall", "eon", "ellevio", "tibber", "greenely".
- **metering_point**: Optional. The 18-digit Swedish anläggnings-ID
  (starts with 735999). Useful for matching data to a specific meter.
- **data**: Must contain hourly records sorted by (date, hour). A complete
  year has 8,760 records (8,784 in leap years). Missing hours are allowed
  but reduce calibration accuracy. Aim for at least 1 full year of data;
  3+ years is ideal.
- **kwh**: Energy consumed during that hour. Must be >= 0. Typical range
  for a Swedish villa: 0.5-15 kWh/h (higher during winter with heat pump).


Writing your own converter
--------------------------

Your converter needs to:

1. Read the provider's native format (Excel, CSV, API response, etc.)
2. Extract hourly consumption as (date, hour, kwh) tuples
3. Call consumption_format.save() or write the JSON directly

Minimal example:

    from consumption_format import save

    records = []
    for row in my_provider_data:
        records.append({
            "date": row.date.strftime("%Y-%m-%d"),
            "hour": row.date.hour,
            "kwh": float(row.consumption),
        })

    save("consumption_myprovider.json", records, source="myprovider")

Or write the JSON directly without importing this module — just match the
schema above. The app validates on load and will report any errors.

See convert_vattenfall.py, convert_eon.py, and convert_csv.py for examples.
"""

import json
from pathlib import Path


def validate(data: dict) -> list[str]:
    """Validate consumption JSON. Returns list of errors (empty = valid)."""
    errors = []
    if not isinstance(data, dict):
        return ["Root must be a JSON object"]
    if data.get("version") != 1:
        errors.append(f"Unsupported version: {data.get('version')} (expected 1)")
    if data.get("resolution") != "hourly":
        errors.append(f"Unsupported resolution: {data.get('resolution')} (expected 'hourly')")
    records = data.get("data", [])
    if not records:
        errors.append("No data records")
        return errors
    # Spot-check first record
    r = records[0]
    if not isinstance(r, dict):
        errors.append("Data records must be objects")
    elif not all(k in r for k in ("date", "hour", "kwh")):
        errors.append(f"Record missing required fields (date, hour, kwh): {r}")
    return errors


def load(path: str) -> dict:
    """Load and validate a consumption JSON file."""
    with open(path) as f:
        data = json.load(f)
    errors = validate(data)
    if errors:
        raise ValueError(f"Invalid consumption file {path}: {'; '.join(errors)}")
    return data


def save(path: str, records: list[dict], source: str = "unknown",
         metering_point: str = "") -> str:
    """
    Save hourly records to standard JSON format.

    Args:
        path: output file path
        records: list of {"date": str, "hour": int, "kwh": float}
        source: provider name
        metering_point: optional meter ID

    Returns path written.
    """
    records = sorted(records, key=lambda r: (r["date"], r["hour"]))

    dates = [r["date"] for r in records]
    total_kwh = sum(r["kwh"] for r in records)
    days = len(set(dates))

    data = {
        "version": 1,
        "source": source,
        "metering_point": metering_point,
        "unit": "kWh",
        "resolution": "hourly",
        "period": {
            "start": min(dates),
            "end": max(dates),
        },
        "summary": {
            "total_kwh": round(total_kwh, 1),
            "days": days,
            "avg_kwh_per_day": round(total_kwh / days, 1) if days > 0 else 0,
        },
        "data": [
            {"date": r["date"], "hour": r["hour"], "kwh": round(r["kwh"], 3)}
            for r in records
        ],
    }

    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return path


def to_seasonal_profile(records: list[dict]) -> dict[int, dict[int, float]]:
    """Convert hourly records to seasonal profile (month → hour → avg kW)."""
    from collections import defaultdict
    sums = defaultdict(lambda: defaultdict(float))
    counts = defaultdict(lambda: defaultdict(int))
    for r in records:
        month = int(r["date"].split("-")[1])
        hour = r["hour"]
        sums[month][hour] += r["kwh"]
        counts[month][hour] += 1
    return {
        m: {h: sums[m][h] / counts[m][h] for h in sorted(sums[m])}
        for m in sorted(sums)
    }
