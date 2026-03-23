"""
PVGIS (Photovoltaic Geographical Information System) integration.

Fetches hourly PV production estimates from the EU JRC PVGIS API.
Based on satellite irradiance data (SARAH3), no API key needed.

Covers ~2005-2023 for Europe. Returns hourly production in kW for a given
system size, tilt, and orientation at any location.

API docs: https://joint-research-centre.ec.europa.eu/pvgis/pvgis-tools/hourly-radiation_en
"""

import csv
import io
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

PVGIS_API = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"
CACHE_DIR = Path(__file__).parent / ".pvgis_cache"


def fetch_pvgis(lat: float, lon: float, peakpower: float = 10.0,
                loss: float = 14.0, angle: float = 35.0, aspect: float = 0.0,
                startyear: int = 2020, endyear: int = 2023) -> list[dict]:
    """
    Fetch hourly PV production from PVGIS.

    Args:
        lat, lon: location coordinates
        peakpower: system size in kWp
        loss: system losses in % (default 14 = inverter + cables + dirt)
        angle: panel tilt in degrees (0 = horizontal, 90 = vertical)
        aspect: panel azimuth (0 = south, -90 = east, 90 = west)
        startyear, endyear: year range (SARAH3: ~2005-2023)

    Returns list of dicts with date, hour, production_kw.
    """
    # Check cache first
    cache_file = _cache_path(lat, lon, peakpower, loss, angle, aspect, startyear, endyear)
    if cache_file.exists():
        return _load_cache(cache_file)

    params = (
        f"lat={lat}&lon={lon}&peakpower={peakpower}&loss={loss}"
        f"&angle={angle}&aspect={aspect}&pvcalculation=1"
        f"&outputformat=csv&startyear={startyear}&endyear={endyear}"
    )
    url = f"{PVGIS_API}?{params}"

    print(f"  Hämtar soldata från PVGIS ({startyear}-{endyear}, {peakpower} kWp)...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "energikalkyl/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as e:
        print(f"  PVGIS-fel: {e}")
        return []

    records = _parse_pvgis_csv(raw)

    if records:
        _save_cache(cache_file, records)
        print(f"  PVGIS: {len(records)} timvärden ({startyear}-{endyear})")

    return records


def _parse_pvgis_csv(raw: str) -> list[dict]:
    """Parse PVGIS CSV response into records."""
    records = []
    in_data = False

    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        # Header line marks start of data
        if line.startswith("time,"):
            in_data = True
            continue

        if not in_data:
            continue

        # End of data section (metadata footer)
        if not line[0].isdigit():
            break

        parts = line.split(",")
        if len(parts) < 2:
            continue

        # Parse timestamp: YYYYMMDD:HHMM
        ts_str = parts[0]
        try:
            # The :11 suffix means mid-point of hour — we use the hour start
            dt = datetime.strptime(ts_str[:11], "%Y%m%d:%H")
        except ValueError:
            continue

        # P column = watts, convert to kW
        try:
            power_w = float(parts[1])
        except ValueError:
            continue

        records.append({
            "date": dt.strftime("%Y-%m-%d"),
            "hour": dt.strftime("%H:00"),
            "production_kw": round(power_w / 1000, 4),
        })

    return records


def pvgis_to_hourly_dict(records: list[dict]) -> dict[str, float]:
    """Convert PVGIS records to lookup dict: 'YYYY-MM-DD HH:00' -> kW."""
    return {f"{r['date']} {r['hour']}": r["production_kw"] for r in records}


def pvgis_to_monthly_kwh(records: list[dict]) -> dict[int, float]:
    """
    Aggregate PVGIS records to average monthly production in kWh.
    For hourly data, kW * 1h = kWh per record.
    Returns dict mapping month (1-12) -> average kWh/month across years.
    """
    ym_totals: dict[tuple[int, int], float] = {}
    for r in records:
        y = int(r["date"][:4])
        m = int(r["date"][5:7])
        key = (y, m)
        ym_totals[key] = ym_totals.get(key, 0) + r["production_kw"]

    monthly: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    for (y, m), total in ym_totals.items():
        monthly[m].append(total)

    return {m: (sum(vals) / len(vals) if vals else 0.0) for m, vals in monthly.items()}


def _cache_path(lat, lon, peakpower, loss, angle, aspect, startyear, endyear) -> Path:
    """Generate cache filename from parameters."""
    key = f"{lat:.2f}_{lon:.2f}_{peakpower}kWp_{loss}loss_{angle}deg_{aspect}az_{startyear}-{endyear}"
    return CACHE_DIR / f"pvgis_{key}.json"


def _save_cache(path: Path, records: list[dict]):
    """Save records to cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump(records, f)


def _load_cache(path: Path) -> list[dict]:
    """Load records from cache."""
    with open(path) as f:
        records = json.load(f)
    print(f"  PVGIS (cachad): {len(records)} timvärden")
    return records
