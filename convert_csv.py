#!/usr/bin/env python3
"""
Convert generic Swedish consumption CSV to standard consumption JSON.

Handles common CSV formats from Swedish grid operators:
- Semicolon or comma delimited
- Comma or dot decimal separator
- Various date/time formats
- ISO 8859-1 or UTF-8 encoding

Usage:
    python convert_csv.py data.csv -o consumption.json
    python convert_csv.py *.csv --source "ellevio"
"""

import argparse
import sys
from import_consumption import load_consumption_file
from consumption_format import save


def main():
    parser = argparse.ArgumentParser(
        description="Convert Swedish consumption CSV to standard JSON")
    parser.add_argument("files", nargs="+", help="CSV files to convert")
    parser.add_argument("-o", "--output", default="consumption_csv.json",
                        help="Output JSON file (default: consumption_csv.json)")
    parser.add_argument("--source", default="csv",
                        help="Provider name (default: csv)")
    args = parser.parse_args()

    all_records = []
    for path in args.files:
        print(f"Reading {path}...")
        records = load_consumption_file(path)
        # Normalize: import_consumption uses "hour" as "HH:MM" string
        for r in records:
            if isinstance(r.get("hour"), str):
                r["hour"] = int(r["hour"].split(":")[0])
            if "consumption_kwh" in r and "kwh" not in r:
                r["kwh"] = r.pop("consumption_kwh")
        all_records.extend(records)
        print(f"  {len(records)} records")

    if not all_records:
        print("ERROR: No data extracted from any file.")
        sys.exit(1)

    # Deduplicate
    seen = set()
    unique = []
    for r in sorted(all_records, key=lambda r: (r["date"], r["hour"])):
        key = (r["date"], r["hour"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    out = save(args.output, unique, source=args.source)
    total = sum(r["kwh"] for r in unique)
    days = len(set(r["date"] for r in unique))
    print(f"\nWrote {out}")
    print(f"  {len(unique):,} hourly records, {days} days, {total:,.0f} kWh")


if __name__ == "__main__":
    main()
