#!/usr/bin/env python3
"""
Convert E.ON Energidata API export to standard consumption JSON.

Usage:
    python convert_eon.py --installation-id ABC123 --years 3 -o consumption.json
    python convert_eon.py --installation-id ABC123   # writes to consumption_eon.json
"""

import argparse
import sys
from datetime import date, timedelta
from eon_source import fetch_consumption
from consumption_format import save


def main():
    parser = argparse.ArgumentParser(
        description="Fetch E.ON consumption data and convert to standard JSON")
    parser.add_argument("--installation-id", required=True,
                        help="E.ON installation/measurement ID")
    parser.add_argument("--years", type=int, default=3,
                        help="Number of years to fetch (default: 3)")
    parser.add_argument("-o", "--output", default="consumption_eon.json",
                        help="Output JSON file (default: consumption_eon.json)")
    args = parser.parse_args()

    end = date.today() - timedelta(days=1)
    start = date(end.year - args.years, end.month, end.day)

    print(f"Fetching E.ON data: {start} to {end} ({args.years} years)...")
    records = fetch_consumption(args.installation_id, start, end, resolution="hour")

    if not records:
        print("ERROR: No data returned from E.ON API.")
        sys.exit(1)

    out = save(args.output, records, source="eon")
    total = sum(r["kwh"] for r in records)
    days = len(set(r["date"] for r in records))
    print(f"\nWrote {out}")
    print(f"  {len(records):,} hourly records, {days} days, {total:,.0f} kWh")


if __name__ == "__main__":
    main()
