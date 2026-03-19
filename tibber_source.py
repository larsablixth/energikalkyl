"""
Tibber API integration.

Fetches actual consumption data and prices from Tibber's GraphQL API.
Requires a personal API token from https://developer.tibber.com/

Set your token via:
  - Environment variable TIBBER_TOKEN
  - Or file .tibber_token in the project directory
"""

import os
import json
from datetime import datetime
from pathlib import Path

import requests

TIBBER_API = "https://api.tibber.com/v1-beta/gql"
TOKEN_FILE = Path(__file__).parent / ".tibber_token"


def _get_token() -> str:
    token = os.environ.get("TIBBER_TOKEN", "").strip()
    if token:
        return token
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token
    raise RuntimeError(
        "Tibber API-token saknas. Sätt TIBBER_TOKEN eller skriv token i .tibber_token\n"
        "Hämta din token på https://developer.tibber.com/"
    )


def _query(query: str, token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = requests.post(TIBBER_API, json={"query": query}, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"Tibber API-fel: {data['errors']}")
    return data


def get_homes(token: str = None) -> list[dict]:
    """Get all homes associated with the Tibber account."""
    token = token or _get_token()
    query = """
    {
      viewer {
        homes {
          id
          appNickname
          address {
            address1
            postalCode
            city
          }
          currentSubscription {
            status
          }
        }
      }
    }
    """
    data = _query(query, token)
    return data["data"]["viewer"]["homes"]


def fetch_consumption(hours: int = 24 * 30, home_id: str = None, token: str = None) -> list[dict]:
    """
    Fetch hourly consumption data from Tibber.

    Args:
        hours: number of hours to fetch (default: 30 days)
        home_id: specific home ID (uses first home if None)
        token: API token (auto-detected if None)

    Returns list of dicts compatible with the app format, with actual consumption.
    """
    token = token or _get_token()

    if home_id is None:
        homes = get_homes(token)
        if not homes:
            raise RuntimeError("Inga hem hittades på Tibber-kontot")
        home_id = homes[0]["id"]
        addr = homes[0].get("address", {})
        print(f"  Tibber hem: {addr.get('address1', '?')}, {addr.get('city', '?')}")

    # Tibber limits to ~2500 nodes per query, so we may need to paginate
    all_nodes = []
    remaining = hours
    batch_size = 2000

    while remaining > 0:
        fetch_count = min(remaining, batch_size)
        query = """
        {
          viewer {
            home(id: "%s") {
              consumption(resolution: HOURLY, last: %d) {
                nodes {
                  from
                  to
                  consumption
                  cost
                  unitPrice
                  currency
                }
              }
            }
          }
        }
        """ % (home_id, fetch_count)

        print(f"  Hämtar {fetch_count} timmar från Tibber...")
        data = _query(query, token)
        nodes = data["data"]["viewer"]["home"]["consumption"]["nodes"]
        nodes = [n for n in nodes if n.get("consumption") is not None]
        all_nodes.extend(nodes)

        if len(nodes) < fetch_count:
            break  # No more data available
        remaining -= fetch_count

    print(f"  Hämtade {len(all_nodes)} timmar med förbrukningsdata")
    return all_nodes


def fetch_prices_tibber(home_id: str = None, token: str = None) -> list[dict]:
    """
    Fetch today's and tomorrow's prices from Tibber.
    Returns list of dicts in the app's price format.
    """
    token = token or _get_token()

    if home_id is None:
        homes = get_homes(token)
        if not homes:
            raise RuntimeError("Inga hem hittades på Tibber-kontot")
        home_id = homes[0]["id"]

    query = """
    {
      viewer {
        home(id: "%s") {
          currentSubscription {
            priceInfo {
              current {
                total
                energy
                tax
                startsAt
                level
                currency
              }
              today {
                total
                energy
                tax
                startsAt
                level
                currency
              }
              tomorrow {
                total
                energy
                tax
                startsAt
                level
                currency
              }
            }
          }
        }
      }
    }
    """ % home_id

    data = _query(query, token)
    price_info = data["data"]["viewer"]["home"]["currentSubscription"]["priceInfo"]

    rows = []
    for period in ["today", "tomorrow"]:
        for p in price_info.get(period, []):
            ts = datetime.fromisoformat(p["startsAt"])
            rows.append({
                "date": ts.strftime("%Y-%m-%d"),
                "hour": ts.strftime("%H:%M"),
                "zone": "SE3",  # Tibber doesn't expose zone, but price includes it
                "sek_per_kwh": round(p["total"], 4),
                "eur_per_kwh": 0,  # Tibber gives SEK directly
                "ore_per_kwh": round(p["total"] * 100, 2),
                "tibber_level": p.get("level", ""),
            })

    return rows


def fetch_daily_consumption(days: int = 365 * 3, home_id: str = None, token: str = None) -> list[dict]:
    """
    Fetch daily consumption data from Tibber.
    Daily resolution is available for much longer periods than hourly.

    Returns list of nodes with from, to, consumption, cost, unitPrice.
    """
    token = token or _get_token()

    if home_id is None:
        homes = get_homes(token)
        if not homes:
            raise RuntimeError("Inga hem hittades på Tibber-kontot")
        home_id = homes[0]["id"]
        addr = homes[0].get("address", {})
        print(f"  Tibber hem: {addr.get('address1', '?')}, {addr.get('city', '?')}")

    all_nodes = []
    remaining = days
    batch_size = 2000

    while remaining > 0:
        fetch_count = min(remaining, batch_size)
        query = """
        {
          viewer {
            home(id: "%s") {
              consumption(resolution: DAILY, last: %d) {
                nodes {
                  from
                  to
                  consumption
                  cost
                  unitPrice
                  currency
                }
              }
            }
          }
        }
        """ % (home_id, fetch_count)

        print(f"  Hämtar {fetch_count} dagar från Tibber...")
        data = _query(query, token)
        nodes = data["data"]["viewer"]["home"]["consumption"]["nodes"]
        nodes = [n for n in nodes if n.get("consumption") is not None]
        all_nodes.extend(nodes)

        if len(nodes) < fetch_count:
            break
        remaining -= fetch_count

    print(f"  Hämtade {len(all_nodes)} dagar med förbrukningsdata")
    return all_nodes


def fetch_monthly_consumption(months: int = 36, home_id: str = None, token: str = None) -> list[dict]:
    """Fetch monthly consumption data from Tibber."""
    token = token or _get_token()

    if home_id is None:
        homes = get_homes(token)
        if not homes:
            raise RuntimeError("Inga hem hittades på Tibber-kontot")
        home_id = homes[0]["id"]
        addr = homes[0].get("address", {})
        print(f"  Tibber hem: {addr.get('address1', '?')}, {addr.get('city', '?')}")

    query = """
    {
      viewer {
        home(id: "%s") {
          consumption(resolution: MONTHLY, last: %d) {
            nodes {
              from
              to
              consumption
              cost
              unitPrice
              currency
            }
          }
        }
      }
    }
    """ % (home_id, months)

    print(f"  Hämtar {months} månader från Tibber...")
    data = _query(query, token)
    nodes = data["data"]["viewer"]["home"]["consumption"]["nodes"]
    nodes = [n for n in nodes if n.get("consumption") is not None]
    print(f"  Hämtade {len(nodes)} månader med förbrukningsdata")
    return nodes


def daily_to_monthly_profile(nodes: list[dict]) -> dict[int, float]:
    """
    Build average daily consumption per month from daily data.
    Returns dict mapping month (1-12) to average kWh/day.
    """
    monthly_sums: dict[int, float] = {m: 0.0 for m in range(1, 13)}
    monthly_counts: dict[int, int] = {m: 0 for m in range(1, 13)}

    for node in nodes:
        if node.get("consumption") is None:
            continue
        ts = datetime.fromisoformat(node["from"])
        m = ts.month
        monthly_sums[m] += node["consumption"]
        monthly_counts[m] += 1

    profile = {}
    for m in range(1, 13):
        if monthly_counts[m] > 0:
            profile[m] = monthly_sums[m] / monthly_counts[m]
        else:
            profile[m] = 0.0
    return profile


def print_daily_consumption_summary(daily_nodes: list[dict]):
    """Print summary of daily consumption data."""
    if not daily_nodes:
        print("  Ingen daglig data tillgänglig.")
        return

    months_sv = ["", "Jan", "Feb", "Mar", "Apr", "Maj", "Jun",
                 "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]

    profile = daily_to_monthly_profile(daily_nodes)

    # Date range
    dates = [datetime.fromisoformat(n["from"]) for n in daily_nodes]
    first = min(dates).strftime("%Y-%m-%d")
    last = max(dates).strftime("%Y-%m-%d")
    total_days = len(daily_nodes)
    total_kwh = sum(n["consumption"] for n in daily_nodes if n.get("consumption"))
    total_cost = sum(n.get("cost", 0) or 0 for n in daily_nodes)

    print(f"\n  Tibber förbrukningshistorik: {first} → {last} ({total_days} dagar)")
    print(f"  Total förbrukning: {total_kwh:,.0f} kWh")
    print(f"  Total kostnad:     {total_cost:,.0f} SEK")
    print(f"  Snitt per dag:     {total_kwh/total_days:.1f} kWh/dag")
    print(f"  Snitt per månad:   {total_kwh/total_days*30.44:,.0f} kWh/mån")
    print(f"  Snitt per år:      {total_kwh/total_days*365.25:,.0f} kWh/år")
    if total_cost > 0:
        print(f"  Snittpris:         {total_cost/total_kwh*100:.1f} öre/kWh")

    print(f"\n  Genomsnittlig förbrukning per månad:")
    print(f"  {'Månad':>6} {'kWh/dag':>10} {'kWh/mån':>10}")
    print(f"  {'-'*30}")
    for m in range(1, 13):
        kwh_day = profile[m]
        kwh_month = kwh_day * 30.44
        bar = "█" * int(kwh_day / 3)
        print(f"  {months_sv[m]:>5}  {kwh_day:>8.1f}  {kwh_month:>8.0f}  {bar}")

    yearly_total = sum(profile[m] * 30.44 for m in range(1, 13))
    print(f"  {'-'*30}")
    print(f"  {'Totalt':>5}  {yearly_total/365.25:>8.1f}  {yearly_total:>8.0f}")


def build_seasonal_hourly_profile(hourly_nodes: list[dict], monthly_nodes: list[dict]) -> dict[int, dict[int, float]]:
    """
    Build a seasonal hourly load profile: month -> hour -> kW.

    Uses the hourly shape from recent data, scaled by monthly totals
    to reflect seasonal variation (heating in winter, etc.).
    """
    # Base hourly shape (from recent ~30 days)
    base_profile = consumption_to_load_profile(hourly_nodes)
    base_daily_kwh = sum(base_profile.values())

    if base_daily_kwh == 0:
        return {m: {h: 0.0 for h in range(24)} for m in range(1, 13)}

    # Monthly average daily kWh
    monthly_daily = {}
    for node in monthly_nodes:
        if node.get("consumption") is None:
            continue
        ts = datetime.fromisoformat(node["from"])
        m = ts.month
        # Get days in this month's data
        ts_end = datetime.fromisoformat(node["to"])
        days = max(1, (ts_end - ts).days)
        monthly_daily[m] = node["consumption"] / days

    # Scale hourly shape by monthly factor
    seasonal = {}
    for m in range(1, 13):
        if m in monthly_daily and monthly_daily[m] > 0:
            scale = monthly_daily[m] / base_daily_kwh
        else:
            scale = 1.0  # no data for this month, use base shape
        seasonal[m] = {h: base_profile[h] * scale for h in range(24)}

    return seasonal


def print_seasonal_profile(profile: dict[int, dict[int, float]]):
    """Print seasonal hourly profile summary."""
    months_sv = ["", "Jan", "Feb", "Mar", "Apr", "Maj", "Jun",
                 "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]
    print(f"\n  Säsongsanpassad förbrukningsprofil (kWh/dag per månad):")
    print(f"  {'Månad':>6} {'kWh/dag':>10} {'Max kW':>8} {'Min kW':>8}")
    print(f"  {'-'*36}")
    for m in range(1, 13):
        if m in profile:
            daily = sum(profile[m].values())
            max_kw = max(profile[m].values())
            min_kw = min(profile[m].values())
            bar = "█" * int(daily / 4)
            print(f"  {months_sv[m]:>5}  {daily:>8.1f}  {max_kw:>7.1f}  {min_kw:>7.1f}  {bar}")


def consumption_to_load_profile(nodes: list[dict]) -> dict[int, float]:
    """
    Analyze consumption data to build an average hourly load profile (kW).
    Returns dict mapping hour (0-23) to average consumption in kW.
    """
    hourly_sums: dict[int, float] = {h: 0.0 for h in range(24)}
    hourly_counts: dict[int, int] = {h: 0 for h in range(24)}

    for node in nodes:
        if node.get("consumption") is None:
            continue
        ts = datetime.fromisoformat(node["from"])
        h = ts.hour
        hourly_sums[h] += node["consumption"]  # kWh per hour ≈ kW average
        hourly_counts[h] += 1

    profile = {}
    for h in range(24):
        if hourly_counts[h] > 0:
            profile[h] = hourly_sums[h] / hourly_counts[h]
        else:
            profile[h] = 0.0

    return profile


def print_load_profile(profile: dict[int, float]):
    """Print the hourly load profile."""
    print("\n  Genomsnittlig förbrukningsprofil (från Tibber):")
    print(f"  {'Timme':>6} {'kW':>8} {'kWh/dygn':>10}")
    print(f"  {'-'*28}")
    total = 0
    for h in range(24):
        kw = profile.get(h, 0)
        total += kw
        bar = "█" * int(kw * 2)
        print(f"  {h:>4}:00 {kw:>8.2f} {bar}")
    print(f"  {'-'*28}")
    print(f"  {'Total':>6} {total:>18.1f} kWh/dygn")
    print(f"  {'Medel':>6} {total/24:>8.2f} kW")


def consumption_to_rows(nodes: list[dict]) -> list[dict]:
    """
    Convert Tibber consumption nodes to app-compatible price rows.
    Uses unitPrice from Tibber (which is the total price you pay per kWh).
    """
    rows = []
    for node in nodes:
        if node.get("consumption") is None or node.get("unitPrice") is None:
            continue
        ts = datetime.fromisoformat(node["from"])
        rows.append({
            "date": ts.strftime("%Y-%m-%d"),
            "hour": ts.strftime("%H:%M"),
            "zone": "SE3",
            "sek_per_kwh": round(node["unitPrice"], 4),
            "eur_per_kwh": 0,
            "ore_per_kwh": round(node["unitPrice"] * 100, 2),
            "consumption_kwh": round(node["consumption"], 4),
            "cost_sek": round(node.get("cost", 0) or 0, 4),
        })
    return rows
