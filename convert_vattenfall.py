#!/usr/bin/env python3
"""
Convert Vattenfall Eldistribution Excel files to standard consumption JSON.

Usage:
    python convert_vattenfall.py file1.xlsx [file2.xlsx ...] -o consumption.json
    python convert_vattenfall.py *.xlsx    # writes to consumption_vattenfall.json
"""

import argparse
import sys
from import_vattenfall import parse_vattenfall_hourly, parse_vattenfall_excel
from consumption_format import save


def main():
    parser = argparse.ArgumentParser(
        description="Convert Vattenfall Excel to standard consumption JSON")
    parser.add_argument("files", nargs="+", help="Vattenfall Excel files (.xlsx)")
    parser.add_argument("-o", "--output", default="consumption_vattenfall.json",
                        help="Output JSON file (default: consumption_vattenfall.json)")
    parser.add_argument("--daily-fallback", action="store_true",
                        help="Fall back to daily totals if hourly extraction fails")
    args = parser.parse_args()

    all_hourly = []
    for path in args.files:
        print(f"Reading {path}...")
        hourly = parse_vattenfall_hourly(path)
        if hourly:
            all_hourly.extend(hourly)
        elif args.daily_fallback:
            print(f"  No hourly data, trying daily totals...")
            daily = parse_vattenfall_excel(path)
            # Spread daily total evenly across 24 hours (rough approximation)
            for d in daily:
                kwh_per_hour = d["consumption_kwh"] / 24
                for h in range(24):
                    all_hourly.append({
                        "date": d["date"], "hour": h,
                        "kwh": round(kwh_per_hour, 3),
                    })
        else:
            print(f"  WARNING: No hourly data found in {path}. Use --daily-fallback for approximation.")

    if not all_hourly:
        print("ERROR: No data extracted from any file.")
        sys.exit(1)

    # Deduplicate by (date, hour)
    seen = set()
    unique = []
    for r in sorted(all_hourly, key=lambda r: (r["date"], r["hour"])):
        key = (r["date"], r["hour"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    out = save(args.output, unique, source="vattenfall")
    total = sum(r["kwh"] for r in unique)
    days = len(set(r["date"] for r in unique))
    years = days / 365.25
    print(f"\nWrote {out}")
    print(f"  {len(unique):,} hourly records, {days} days")
    print(f"  {total:,.0f} kWh total ({total/years:,.0f} kWh/yr)")


if __name__ == "__main__":
    main()
