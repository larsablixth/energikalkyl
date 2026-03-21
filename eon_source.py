"""
E.ON Energidata API integration.

Fetches consumption data from E.ON Navigator API.
Requires client_id and client_secret from E.ON.

Set credentials via:
  - Environment variables EON_CLIENT_ID and EON_CLIENT_SECRET
  - Or file .eon_credentials in project directory (format: client_id:client_secret)

API docs: https://navigator-api.eon.se/swagger/index.html
"""

import os
import json
from datetime import datetime, date
from pathlib import Path

import requests

API_BASE = "https://navigator-api.eon.se"
TOKEN_URL = f"{API_BASE}/connect/token"
API_PREFIX = f"{API_BASE}/api"
CRED_FILE = Path(__file__).parent / ".eon_credentials"


def _get_credentials() -> tuple[str, str]:
    """Get E.ON API credentials."""
    client_id = os.environ.get("EON_CLIENT_ID", "").strip()
    client_secret = os.environ.get("EON_CLIENT_SECRET", "").strip()
    if client_id and client_secret:
        return client_id, client_secret

    if CRED_FILE.exists():
        text = CRED_FILE.read_text(encoding="utf-8").strip()
        if ":" in text:
            parts = text.split(":", 1)
            return parts[0].strip(), parts[1].strip()

    raise RuntimeError(
        "E.ON API-uppgifter saknas. Ange EON_CLIENT_ID/EON_CLIENT_SECRET "
        "eller skapa .eon_credentials (format: client_id:client_secret)\n"
        "Kontakta E.ON for att skapa API-konto."
    )


def _get_token() -> str:
    """Authenticate and get bearer token."""
    client_id, client_secret = _get_credentials()
    resp = requests.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
        "scope": "navigator",
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _api_get(endpoint: str, token: str, params: dict = None) -> dict:
    """Make authenticated API request."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    resp = requests.get(f"{API_PREFIX}{endpoint}", headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    if resp.status_code == 204:
        return {}
    return resp.json()


def get_installations(token: str = None) -> list[dict]:
    """Get all installations (metering points) for the account."""
    token = token or _get_token()
    return _api_get("/installations", token)


def fetch_consumption(installation_id: str, start_date: date, end_date: date,
                       resolution: str = "hour", token: str = None) -> list[dict]:
    """
    Fetch consumption data for an installation.

    Args:
        installation_id: E.ON installation/measurement ID
        start_date: start of period
        end_date: end of period
        resolution: 'quarter', 'hour', 'day', or 'month'
        token: bearer token (auto-fetched if None)

    Returns list of dicts with timestamp and value.
    """
    token = token or _get_token()

    # Get measurement series for installation
    series = _api_get("/installations/measurement-series", token,
                       params={"installationFilter": [installation_id]})

    if not series:
        print(f"  Inga mätserier hittade for installation {installation_id}")
        return []

    # Find consumption series (might have multiple)
    series_id = None
    for s in series if isinstance(series, list) else [series]:
        if isinstance(s, dict):
            series_id = s.get("id") or s.get("measurementSeriesId")
            if series_id:
                break

    if not series_id:
        print(f"  Kunde inte hitta mätserie-ID")
        return []

    # Fetch measurements
    params = {
        "from": start_date.isoformat(),
        "to": end_date.isoformat(),
        "resolution": resolution,
        "includeMissing": False,
    }
    data = _api_get(f"/measurements/{series_id}/resolution/{resolution}", token, params)

    if not data:
        return []

    # Parse response
    nodes = []
    values = data if isinstance(data, list) else data.get("values", data.get("data", []))
    for v in values:
        if isinstance(v, dict):
            ts_str = v.get("timestamp") or v.get("from") or v.get("date")
            value = v.get("value") or v.get("consumption")
            if ts_str and value is not None:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    nodes.append({
                        "date": ts.strftime("%Y-%m-%d"),
                        "hour": ts.hour,
                        "kwh": float(value),
                    })
                except (ValueError, TypeError):
                    continue

    print(f"  Hamtade {len(nodes)} matpunkter fran E.ON ({resolution})")
    return nodes


def eon_to_seasonal_profile(hourly_data: list[dict]) -> dict[int, dict[int, float]]:
    """Build seasonal hourly profile from E.ON hourly data."""
    from collections import defaultdict
    sums = defaultdict(lambda: defaultdict(float))
    counts = defaultdict(lambda: defaultdict(int))

    for r in hourly_data:
        m = int(r["date"].split("-")[1])
        h = r["hour"]
        sums[m][h] += r["kwh"]
        counts[m][h] += 1

    profile = {}
    for m in range(1, 13):
        profile[m] = {}
        for h in range(24):
            if counts[m][h] > 0:
                profile[m][h] = round(sums[m][h] / counts[m][h], 3)
            else:
                profile[m][h] = 0.0

    return profile
