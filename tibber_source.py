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


def _fetch_paginated(home_id: str, field: str, resolution: str, count: int,
                     node_fields: str, token: str, batch_size: int = 2000) -> list[dict]:
    """
    Fetch the latest `count` nodes of consumption/production, paging backwards
    in time with Tibber's cursor pagination (last: N, before: startCursor).

    Returns nodes in chronological order (oldest first), nulls included.
    """
    pages = []
    remaining = count
    before = None
    while remaining > 0:
        fetch_count = min(remaining, batch_size)
        before_arg = ', before: "%s"' % before if before else ""
        query = """
        {
          viewer {
            home(id: "%s") {
              %s(resolution: %s, last: %d%s) {
                pageInfo {
                  startCursor
                }
                nodes {
                  %s
                }
              }
            }
          }
        }
        """ % (home_id, field, resolution, fetch_count, before_arg, node_fields)

        data = _query(query, token)
        conn = data["data"]["viewer"]["home"][field] or {}
        nodes = conn.get("nodes") or []
        pages.append(nodes)
        remaining -= len(nodes)

        page_info = conn.get("pageInfo") or {}
        before = page_info.get("startCursor")
        if len(nodes) < fetch_count or not before:
            break  # No more (older) data available

    # Pages were fetched newest-first; each page is oldest-first
    all_nodes = []
    for nodes in reversed(pages):
        all_nodes.extend(nodes)
    return all_nodes


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

    # Tibber limits to ~2500 nodes per query — page backwards with cursors
    print(f"  Hämtar {hours} timmar från Tibber...")
    all_nodes = _fetch_paginated(home_id, "consumption", "HOURLY", hours,
                                 "from to consumption cost unitPrice unitPriceVAT currency", token)
    all_nodes = [n for n in all_nodes if n.get("consumption") is not None]

    print(f"  Hämtade {len(all_nodes)} timmar med förbrukningsdata")
    return all_nodes


def fetch_production(hours: int = 24 * 30, home_id: str = None, token: str = None) -> list[dict]:
    """
    Fetch hourly solar production data from Tibber.

    Works for homes with solar panels registered in Tibber (e.g., via Pulse).
    Same structure as consumption: nodes with from, to, production, profit, unitPrice.

    Returns list of nodes, or empty list if no production data available.
    """
    token = token or _get_token()

    if home_id is None:
        homes = get_homes(token)
        if not homes:
            raise RuntimeError("Inga hem hittades på Tibber-kontot")
        home_id = homes[0]["id"]

    all_nodes = _fetch_paginated(home_id, "production", "HOURLY", hours,
                                 "from to production profit unitPrice currency", token)
    all_nodes = [n for n in all_nodes if n.get("production") is not None]

    if all_nodes:
        print(f"  Hämtade {len(all_nodes)} timmar med solproduktionsdata")
    return all_nodes


def fetch_daily_production(days: int = 365 * 3, home_id: str = None, token: str = None) -> list[dict]:
    """
    Fetch daily solar production data from Tibber.
    Daily resolution available for longer periods than hourly.
    """
    token = token or _get_token()

    if home_id is None:
        homes = get_homes(token)
        if not homes:
            raise RuntimeError("Inga hem hittades på Tibber-kontot")
        home_id = homes[0]["id"]

    all_nodes = _fetch_paginated(home_id, "production", "DAILY", days,
                                 "from to production profit unitPrice currency", token)
    all_nodes = [n for n in all_nodes if n.get("production") is not None]

    if all_nodes:
        print(f"  Hämtade {len(all_nodes)} dagar med solproduktionsdata")
    return all_nodes


def production_to_hourly_dict(nodes: list[dict]) -> dict[str, float]:
    """
    Convert Tibber production nodes to a lookup dict: "YYYY-MM-DD HH:00" -> kW.

    Since each node is 1 hour, production in kWh ≈ average kW for that hour.
    """
    result = {}
    for node in nodes:
        if node.get("production") is None:
            continue
        ts = datetime.fromisoformat(node["from"])
        key = ts.strftime("%Y-%m-%d %H:00")
        result[key] = node["production"]
    return result


def production_to_monthly_kwh(nodes: list[dict]) -> dict[int, float]:
    """
    Aggregate production nodes (hourly or daily) to monthly totals in kWh.
    Returns dict mapping month (1-12) to total kWh across all years.
    """
    monthly: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    # Group by year-month
    ym_totals: dict[tuple[int, int], float] = {}
    for node in nodes:
        if node.get("production") is None:
            continue
        ts = datetime.fromisoformat(node["from"])
        key = (ts.year, ts.month)
        ym_totals[key] = ym_totals.get(key, 0) + node["production"]

    for (y, m), total in ym_totals.items():
        monthly[m].append(total)

    # Average across years
    return {m: (sum(vals) / len(vals) if vals else 0.0) for m, vals in monthly.items()}


def fetch_prices_tibber(home_id: str = None, token: str = None, zone: str = "SE3") -> list[dict]:
    """
    Fetch today's and tomorrow's prices from Tibber.
    Returns list of dicts in the app's price format.

    NOTE: sek_per_kwh here is Tibber's TOTAL price (incl. energy tax and
    VAT) — fine for display, not as spot input to simulate().
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
                "zone": zone,  # Tibber doesn't expose zone; passed in by caller
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

    print(f"  Hämtar {days} dagar från Tibber...")
    all_nodes = _fetch_paginated(home_id, "consumption", "DAILY", days,
                                 "from to consumption cost unitPrice currency", token)
    all_nodes = [n for n in all_nodes if n.get("consumption") is not None]

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


VAT = 0.25


def consumption_to_rows(nodes: list[dict], zone: str = "SE3") -> list[dict]:
    """
    Convert Tibber consumption nodes to app-compatible price rows.

    Tibber's unitPrice is the energy price you pay Tibber per kWh (spot +
    Tibber markup + VAT). In Sweden energy tax is billed by the grid
    company, so it is not part of unitPrice. The simulation treats
    sek_per_kwh as the spot price excl. VAT and adds VAT itself, so:
        spot ≈ unitPrice - unitPriceVAT
    (VAT from unitPriceVAT if provided, else unitPrice / 1.25 × 0.25).
    Tibber's small markup remains included. The raw unitPrice is kept in
    "tibber_unit_price_sek"; rows are flagged with "spot_derived": True.

    zone: elområde (Tibber's consumption API doesn't expose it).
    """
    rows = []
    for node in nodes:
        if node.get("consumption") is None or node.get("unitPrice") is None:
            continue
        ts = datetime.fromisoformat(node["from"])
        unit_price = node["unitPrice"]
        vat_part = node.get("unitPriceVAT")
        if vat_part is None:
            vat_part = unit_price * VAT / (1 + VAT)
        spot_sek = unit_price - vat_part
        rows.append({
            "date": ts.strftime("%Y-%m-%d"),
            "hour": ts.strftime("%H:%M"),
            "zone": zone,
            "sek_per_kwh": round(spot_sek, 4),
            "eur_per_kwh": 0,
            "ore_per_kwh": round(spot_sek * 100, 2),
            "consumption_kwh": round(node["consumption"], 4),
            "cost_sek": round(node.get("cost", 0) or 0, 4),
            "tibber_unit_price_sek": round(unit_price, 4),
            "spot_derived": True,
        })
    return rows
