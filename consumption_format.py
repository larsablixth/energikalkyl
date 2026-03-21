"""
Standard consumption data format for Energikalkyl.

All provider-specific converters produce this JSON format. The app reads only this format.
Converters handle the messy provider-specific parsing separately.

Format:
{
    "version": 1,
    "source": "vattenfall",          # provider name
    "metering_point": "735999...",   # optional, for reference
    "unit": "kWh",
    "resolution": "hourly",
    "period": {
        "start": "2023-01-01",
        "end": "2025-12-31"
    },
    "summary": {
        "total_kwh": 66000,
        "days": 1095,
        "avg_kwh_per_day": 60.3
    },
    "data": [
        {"date": "2023-01-01", "hour": 0, "kwh": 2.31},
        ...
    ]
}
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
