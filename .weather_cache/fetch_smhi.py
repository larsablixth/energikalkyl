"""Fetch SMHI hourly temperature for Arlanda, merge archive + latest, save CSV."""
import csv
import io
import json
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ARCHIVE_URL = "https://opendata-download-metobs.smhi.se/api/version/1.0/parameter/1/station/97400/period/corrected-archive/data.csv"
LATEST_URL = "https://opendata-download-metobs.smhi.se/api/version/1.0/parameter/1/station/97400/period/latest-months/data.json"
OUTPUT = "/home/larsabl/projects/elpriser/.weather_cache/arlanda_temp.csv"
TZ = ZoneInfo("Europe/Stockholm")
CUTOFF = datetime(2023, 1, 1, tzinfo=TZ)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "elpriser/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def parse_archive(raw_bytes):
    """Parse semicolon-delimited CSV, skip header section."""
    records = {}
    text = raw_bytes.decode("utf-8-sig")
    for line in text.splitlines():
        parts = line.split(";")
        if len(parts) < 3:
            continue
        # Data rows start with a date like 2008-02-01
        date_str = parts[0].strip()
        if len(date_str) != 10 or date_str[4] != "-":
            continue
        try:
            time_str = parts[1].strip()
            temp = float(parts[2].strip())
        except (ValueError, IndexError):
            continue
        # Archive times are UTC
        dt_utc = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        dt_local = dt_utc.astimezone(TZ)
        if dt_local < CUTOFF:
            continue
        key = (dt_local.strftime("%Y-%m-%d"), dt_local.hour)
        records[key] = temp
    return records


def parse_latest(raw_bytes):
    """Parse latest-months JSON."""
    records = {}
    data = json.loads(raw_bytes)
    for item in data.get("value", []):
        ts_ms = item["date"]
        try:
            temp = float(item["value"])
        except (ValueError, KeyError):
            continue
        dt_utc = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        dt_local = dt_utc.astimezone(TZ)
        if dt_local < CUTOFF:
            continue
        key = (dt_local.strftime("%Y-%m-%d"), dt_local.hour)
        records[key] = temp
    return records


def main():
    print("Fetching corrected archive...")
    archive_raw = fetch(ARCHIVE_URL)
    print(f"  archive: {len(archive_raw)} bytes")

    print("Fetching latest months...")
    latest_raw = fetch(LATEST_URL)
    print(f"  latest: {len(latest_raw)} bytes")

    print("Parsing archive...")
    records = parse_archive(archive_raw)
    print(f"  archive records (>=2023): {len(records)}")

    print("Parsing latest months...")
    latest = parse_latest(latest_raw)
    print(f"  latest records (>=2023): {len(latest)}")

    # Merge — latest overwrites archive on conflict
    records.update(latest)
    print(f"  merged total: {len(records)}")

    # Sort and write
    sorted_keys = sorted(records.keys())
    with open(OUTPUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "hour", "temp_c"])
        for date_str, hour in sorted_keys:
            w.writerow([date_str, hour, round(records[(date_str, hour)], 1)])

    print(f"Wrote {len(sorted_keys)} rows to {OUTPUT}")
    print(f"Date range: {sorted_keys[0][0]} to {sorted_keys[-1][0]}")


if __name__ == "__main__":
    main()
