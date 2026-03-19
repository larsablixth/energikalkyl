"""
ENTSO-E Transparency Platform data source.

Fetches wholesale day-ahead spot prices for Swedish bidding zones (SE1-SE4).
Requires a free API key from https://transparency.entsoe.eu/

Set your key via:
  - Environment variable ENTSOE_API_KEY
  - Or file .entsoe_key in the project directory
"""

import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from entsoe import EntsoePandasClient

# ENTSO-E area codes for Swedish zones
ZONE_CODES = {
    "SE1": "SE_1",
    "SE2": "SE_2",
    "SE3": "SE_3",
    "SE4": "SE_4",
}

KEY_FILE = Path(__file__).parent / ".entsoe_key"
FX_CACHE_FILE = Path(__file__).parent / ".fx_cache.json"

FALLBACK_EUR_SEK = 11.5


def _get_api_key() -> str:
    key = os.environ.get("ENTSOE_API_KEY", "").strip()
    if key:
        return key
    if KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8").strip()
        if key:
            return key
    raise RuntimeError(
        "ENTSO-E API-nyckel saknas. Sätt ENTSOE_API_KEY eller skriv nyckeln i .entsoe_key"
    )


def _load_fx_cache() -> dict[str, float]:
    """Load cached exchange rates from disk."""
    if FX_CACHE_FILE.exists():
        return json.loads(FX_CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_fx_cache(cache: dict[str, float]):
    FX_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def fetch_exchange_rates(start: date, end: date) -> dict[str, float]:
    """
    Fetch daily EUR→SEK exchange rates from the ECB (via frankfurter.app).

    Returns a dict mapping date string (YYYY-MM-DD) to the EUR/SEK rate.
    Uses a local file cache to avoid re-fetching.
    """
    cache = _load_fx_cache()

    # Check which dates we're missing
    current = start
    missing_start = None
    missing_end = None
    while current <= end:
        if current.isoformat() not in cache:
            if missing_start is None:
                missing_start = current
            missing_end = current
        current += pd.Timedelta(days=1).to_pytimedelta()

    if missing_start is not None:
        print(f"  Hämtar EUR/SEK-kurser från ECB: {missing_start} → {missing_end}...")
        try:
            url = (
                f"https://api.frankfurter.app/{missing_start.isoformat()}"
                f"..{missing_end.isoformat()}?to=SEK"
            )
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            rates = data.get("rates", {})
            for date_str, rate_dict in rates.items():
                cache[date_str] = rate_dict["SEK"]

            _save_fx_cache(cache)
            print(f"  Hämtade {len(rates)} växelkurser (senaste: {max(rates.keys()) if rates else '?'})")
        except Exception as e:
            print(f"  Varning: Kunde inte hämta växelkurser: {e}")
            print(f"  Använder fallback-kurs {FALLBACK_EUR_SEK} SEK/EUR")

    return cache


def _get_rate_for_date(fx_rates: dict[str, float], d: str) -> float:
    """
    Get EUR/SEK rate for a spot price delivery date.

    Nord Pool uses the ECB reference rate published at 14:15 CET the day
    before delivery. So for a Monday delivery, the rate from the previous
    Friday is used. We look up the rate for (delivery_date - 1 day) and
    fall back to the nearest earlier business day if that date has no rate
    (weekends/holidays).
    """
    from datetime import timedelta
    dt = date.fromisoformat(d)

    # Start from the day before delivery
    for i in range(1, 10):
        prev = (dt - timedelta(days=i)).isoformat()
        if prev in fx_rates:
            return fx_rates[prev]

    return FALLBACK_EUR_SEK


def fetch_entsoe(start: date, end: date, zone: str) -> list[dict]:
    """
    Fetch day-ahead prices from ENTSO-E for the given date range and zone.

    Returns list of dicts compatible with the rest of the app.
    Prices are in EUR/MWh from ENTSO-E, converted to SEK/kWh using
    daily ECB exchange rates.
    """
    api_key = _get_api_key()
    client = EntsoePandasClient(api_key=api_key)

    area = ZONE_CODES.get(zone)
    if not area:
        raise ValueError(f"Okänd zon: {zone}. Välj bland {list(ZONE_CODES.keys())}")

    # Fetch exchange rates — include days before start since Nord Pool
    # uses the ECB rate from the day before delivery
    from datetime import timedelta
    fx_start = start - timedelta(days=5)
    fx_rates = fetch_exchange_rates(fx_start, end)

    # ENTSO-E expects timezone-aware timestamps
    start_ts = pd.Timestamp(start.isoformat(), tz="Europe/Stockholm")
    # end is exclusive in the API, so add one day
    end_ts = pd.Timestamp(end.isoformat(), tz="Europe/Stockholm") + pd.Timedelta(days=1)

    print(f"  Hämtar från ENTSO-E: {zone} ({area}), {start} → {end}...")
    series = client.query_day_ahead_prices(area, start=start_ts, end=end_ts)

    # series index is a DatetimeIndex with hourly prices in EUR/MWh
    rows = []
    for ts, eur_per_mwh in series.items():
        local_ts = ts.tz_convert("Europe/Stockholm")
        date_str = local_ts.strftime("%Y-%m-%d")
        rate = _get_rate_for_date(fx_rates, date_str)

        eur_per_kwh = eur_per_mwh / 1000.0
        sek_per_kwh = eur_per_kwh * rate
        rows.append({
            "date": date_str,
            "hour": local_ts.strftime("%H:%M"),
            "zone": zone,
            "sek_per_kwh": round(sek_per_kwh, 4),
            "eur_per_kwh": round(eur_per_kwh, 4),
            "ore_per_kwh": round(sek_per_kwh * 100, 2),
            "eur_sek_rate": round(rate, 4),
        })

    print(f"  Hämtade {len(rows)} datapunkter från ENTSO-E")
    return rows
