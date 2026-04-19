"""
scenarios.py — Per-year scenario analysis for energikalkyl.

A single average over 4 years of price history hides the truth. 2020 and
2021 were cheap, 2022 was an outlier with Russia-related price spikes,
2023 was still elevated, 2024 was closer to long-run normal.

A battery that looks great averaged over 2022-2024 might barely pay back
in a future that looks more like 2020 or 2024. Or the other way around.

What this module does:

1. Splits a multi-year price series into one series per calendar year.
2. Runs the simulator once per year.
3. Returns the annual savings as a distribution, not a single number.
4. Lets the caller feed the distribution (or a chosen percentile) into
   financial.analyze() to get NPV/IRR under conservative, central, and
   optimistic assumptions.

This is the missing piece that makes the tool usable for pushing back on
sales pitches — when someone quotes you "15,000 kr/year in savings" you
can answer "over which year? 2022 — sure. 2020 — no, 3,500 kr."
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
from statistics import median, mean
from typing import Callable


@dataclass
class YearlyScenario:
    """Simulator result for a single calendar year."""
    year: int
    num_days: int
    annual_savings_sek: float          # extrapolated to full year if partial
    cycles: float
    avg_spot_ore_per_kwh: float
    avg_spread_ore_per_kwh: float      # intra-day max-min averaged over days


@dataclass
class ScenarioSummary:
    """Summary statistics across all years run."""
    years: list[YearlyScenario]

    @property
    def savings_by_year(self) -> dict[int, float]:
        return {s.year: s.annual_savings_sek for s in self.years}

    @property
    def median_savings(self) -> float:
        return median(s.annual_savings_sek for s in self.years)

    @property
    def mean_savings(self) -> float:
        return mean(s.annual_savings_sek for s in self.years)

    @property
    def min_savings(self) -> float:
        return min(s.annual_savings_sek for s in self.years)

    @property
    def max_savings(self) -> float:
        return max(s.annual_savings_sek for s in self.years)

    def percentile(self, p: float) -> float:
        """Linear-interpolated percentile. p in [0, 1]."""
        vals = sorted(s.annual_savings_sek for s in self.years)
        if not vals:
            return 0.0
        if len(vals) == 1:
            return vals[0]
        idx = p * (len(vals) - 1)
        lo_idx = int(idx)
        hi_idx = min(lo_idx + 1, len(vals) - 1)
        frac = idx - lo_idx
        return vals[lo_idx] * (1 - frac) + vals[hi_idx] * frac


# ============================================================
# Scenario runner
# ============================================================

def run_yearly_scenarios(
    prices: list[dict],
    simulate_fn: Callable,
    config,
    tariff=None,
    solar=None,
) -> ScenarioSummary:
    """Run the simulator once per calendar year and return the distribution.

    prices: full multi-year price series as used by batteri.simulate()
    simulate_fn: usually batteri.simulate (passed in to keep this module
                 free of circular imports)
    config, tariff, solar: same as batteri.simulate()

    Strategy: groups prices by the year portion of the `date` field.
    Skips any year with fewer than 180 days (too sparse to be meaningful).
    Annualises savings from partial years by scaling to 365 days.
    """
    # Group by year
    by_year: dict[int, list[dict]] = defaultdict(list)
    for row in prices:
        y = int(row["date"][:4])
        by_year[y].append(row)

    results: list[YearlyScenario] = []
    for y in sorted(by_year):
        year_prices = by_year[y]
        unique_days = {p["date"] for p in year_prices}
        num_days = len(unique_days)
        if num_days < 180:
            continue  # skip sparse years

        result = simulate_fn(year_prices, config, tariff=tariff, solar=solar)

        # Extrapolate to full year
        net_profit = result.net_profit_sek
        annual = net_profit * (365.25 / num_days)

        # Average spot price and intra-day spread
        spots = [p["sek_per_kwh"] for p in year_prices]
        avg_spot_ore = (sum(spots) / len(spots)) * 100

        # Spread: for each day, max - min of that day's prices, averaged
        day_spreads = []
        prices_by_day: dict[str, list[float]] = defaultdict(list)
        for p in year_prices:
            prices_by_day[p["date"]].append(p["sek_per_kwh"])
        for day, ps in prices_by_day.items():
            day_spreads.append((max(ps) - min(ps)) * 100)
        avg_spread_ore = sum(day_spreads) / len(day_spreads) if day_spreads else 0.0

        results.append(YearlyScenario(
            year=y,
            num_days=num_days,
            annual_savings_sek=annual,
            cycles=result.num_cycles * (365.25 / num_days),
            avg_spot_ore_per_kwh=avg_spot_ore,
            avg_spread_ore_per_kwh=avg_spread_ore,
        ))

    return ScenarioSummary(years=results)


# ============================================================
# Pretty-print
# ============================================================

def print_scenario_table(summary: ScenarioSummary) -> None:
    """Print the per-year scenarios as a table."""
    print()
    print("=" * 78)
    print("  ÅRLIGA SCENARIER — besparing per historiskt kalenderår")
    print("=" * 78)
    print(f"  {'År':<6}{'Dagar':>7}{'Snittspot':>12}{'Snittspread':>14}"
          f"{'Cykler':>9}{'Besparing':>14}")
    print(f"  {'':6}{'':7}{'öre/kWh':>12}{'öre/kWh':>14}"
          f"{'/år':>9}{'SEK/år':>14}")
    print("-" * 78)
    for s in summary.years:
        print(f"  {s.year:<6d}{s.num_days:>7d}{s.avg_spot_ore_per_kwh:>12.1f}"
              f"{s.avg_spread_ore_per_kwh:>14.1f}"
              f"{s.cycles:>9.0f}{s.annual_savings_sek:>14,.0f}")
    print("-" * 78)

    if summary.years:
        print(f"  {'Median':<34}{'':14}{summary.median_savings:>14,.0f}")
        print(f"  {'Medelvärde':<34}{'':14}{summary.mean_savings:>14,.0f}")
        print(f"  {'Min':<34}{'':14}{summary.min_savings:>14,.0f}")
        print(f"  {'Max':<34}{'':14}{summary.max_savings:>14,.0f}")
        print(f"  {'25:e percentilen':<34}{'':14}{summary.percentile(0.25):>14,.0f}")
        print(f"  {'75:e percentilen':<34}{'':14}{summary.percentile(0.75):>14,.0f}")
    print("=" * 78)
    print()
    print("  Variansen är den verkliga osäkerheten i investeringen.")
    print("  Diskontera framtida år mot MEDIAN eller P25, inte mot MAX.")
    print()
