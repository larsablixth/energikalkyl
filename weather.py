"""
SMHI weather data — fetch and cache hourly temperatures for any Swedish station.

Uses SMHI Open Data API (no authentication required).
Stations are auto-discovered from the API.
"""

import csv
import json
import math
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

CACHE_DIR = Path(__file__).parent / ".weather_cache"
TZ = ZoneInfo("Europe/Stockholm")
CUTOFF = datetime(2023, 1, 1, tzinfo=TZ)

SMHI_BASE = "https://opendata-download-metobs.smhi.se/api/version/1.0/parameter/1"


def _fetch_url(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "energikalkyl/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_stations() -> dict[str, tuple[str, float, float]]:
    """Get all active SMHI stations with hourly temperature data.

    Returns dict: station_id -> (name, latitude, longitude)
    """
    # Try loading from local module first (faster)
    try:
        from smhi_stations import STATIONS
        if STATIONS:
            return STATIONS
    except ImportError:
        pass

    # Fetch from API
    raw = _fetch_url(f"{SMHI_BASE}.json")
    data = json.loads(raw)
    stations = {}
    for s in data.get("station", []):
        if not s.get("active"):
            continue
        sid = str(s["key"])
        name = s.get("name", sid)
        lat = s.get("latitude", 0)
        lon = s.get("longitude", 0)
        if lat and lon:
            stations[sid] = (name, lat, lon)
    return stations


def find_nearest_station(lat: float, lon: float,
                          stations: dict | None = None) -> tuple[str, str, float]:
    """Find the nearest SMHI station to a given coordinate.

    Returns (station_id, station_name, distance_km)
    """
    if stations is None:
        stations = get_stations()

    best_id = None
    best_name = ""
    best_dist = float("inf")

    for sid, (name, slat, slon) in stations.items():
        dist = _haversine_km(lat, lon, slat, slon)
        if dist < best_dist:
            best_dist = dist
            best_id = sid
            best_name = name

    return best_id, best_name, best_dist


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance between two coordinates in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def get_cache_path(station_id: str) -> Path:
    return CACHE_DIR / f"station_{station_id}.csv"


def fetch_station_data(station_id: str, force: bool = False) -> Path:
    """Fetch and cache temperature data for a station.

    Returns path to the cached CSV file.
    """
    cache_path = get_cache_path(station_id)
    if cache_path.exists() and not force:
        # Check if cache is recent enough (less than 1 day old)
        age_hours = (datetime.now().timestamp() - cache_path.stat().st_mtime) / 3600
        if age_hours < 24:
            return cache_path

    CACHE_DIR.mkdir(exist_ok=True)

    # Fetch corrected archive (CSV)
    archive_url = f"{SMHI_BASE}/station/{station_id}/period/corrected-archive/data.csv"
    try:
        archive_raw = _fetch_url(archive_url)
        records = _parse_archive_csv(archive_raw)
    except Exception:
        records = {}

    # Fetch latest months (JSON)
    latest_url = f"{SMHI_BASE}/station/{station_id}/period/latest-months/data.json"
    try:
        latest_raw = _fetch_url(latest_url)
        latest = _parse_latest_json(latest_raw)
        records.update(latest)  # latest overwrites archive on conflict
    except Exception:
        pass

    if not records:
        return cache_path  # empty, but don't crash

    # Write CSV
    sorted_keys = sorted(records.keys())
    with open(cache_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "hour", "temp_c"])
        for date_str, hour in sorted_keys:
            w.writerow([date_str, hour, round(records[(date_str, hour)], 1)])

    return cache_path


def _parse_archive_csv(raw_bytes: bytes) -> dict:
    records = {}
    text = raw_bytes.decode("utf-8-sig")
    for line in text.splitlines():
        parts = line.split(";")
        if len(parts) < 3:
            continue
        date_str = parts[0].strip()
        if len(date_str) != 10 or date_str[4] != "-":
            continue
        try:
            time_str = parts[1].strip()
            temp = float(parts[2].strip())
        except (ValueError, IndexError):
            continue
        dt_utc = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        dt_local = dt_utc.astimezone(TZ)
        if dt_local < CUTOFF:
            continue
        records[(dt_local.strftime("%Y-%m-%d"), dt_local.hour)] = temp
    return records


def _parse_latest_json(raw_bytes: bytes) -> dict:
    records = {}
    data = json.loads(raw_bytes)
    for item in data.get("value", []):
        try:
            temp = float(item["value"])
        except (ValueError, KeyError):
            continue
        dt_utc = datetime.fromtimestamp(item["date"] / 1000, tz=timezone.utc)
        dt_local = dt_utc.astimezone(TZ)
        if dt_local < CUTOFF:
            continue
        records[(dt_local.strftime("%Y-%m-%d"), dt_local.hour)] = temp
    return records


def load_temperatures(station_id: str = "97400") -> dict[str, list[tuple[int, float]]]:
    """Load temperature data for a station (from cache or fetch).

    Returns dict: date_str -> [(hour, temp_c), ...]
    """
    cache_path = get_cache_path(station_id)

    # Also check legacy path for Arlanda
    if station_id == "97400" and not cache_path.exists():
        legacy = CACHE_DIR / "arlanda_temp.csv"
        if legacy.exists():
            cache_path = legacy

    if not cache_path.exists():
        return {}

    temps: dict[str, list[tuple[int, float]]] = {}
    with open(cache_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row["date"]
            hour = int(row["hour"])
            temp = float(row["temp_c"])
            temps.setdefault(date, []).append((hour, temp))
    return temps


# Common Swedish cities with approximate coordinates
SWEDISH_CITIES = {
    "Stockholm": (59.33, 18.07),
    "Göteborg": (57.71, 11.97),
    "Malmö": (55.60, 13.00),
    "Uppsala": (59.86, 17.64),
    "Linköping": (58.41, 15.63),
    "Örebro": (59.27, 15.21),
    "Västerås": (59.61, 16.55),
    "Norrköping": (58.59, 16.18),
    "Jönköping": (57.78, 14.16),
    "Umeå": (63.83, 20.26),
    "Lund": (55.70, 13.19),
    "Luleå": (65.58, 22.15),
    "Gävle": (60.67, 17.15),
    "Sundsvall": (62.39, 17.31),
    "Östersund": (63.18, 14.64),
    "Karlstad": (59.38, 13.50),
    "Växjö": (56.88, 14.81),
    "Halmstad": (56.67, 12.86),
    "Sigtuna": (59.62, 17.72),
    "Sollentuna": (59.43, 17.95),
    "Kiruna": (67.86, 20.23),
    "Visby": (57.64, 18.30),
    "Kalmar": (56.66, 16.36),
    "Falun": (60.61, 15.63),
    "Skellefteå": (64.75, 20.95),
    "Borås": (57.72, 12.94),
    "Trollhättan": (58.28, 12.29),
    "Eskilstuna": (59.37, 16.51),
    "Nyköping": (58.75, 17.01),
    "Karlskrona": (56.16, 15.59),
}
