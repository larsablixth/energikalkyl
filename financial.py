"""
financial.py — Time-value-of-money analysis for energikalkyl.

The existing batteri.py computes *annual savings* (how much the battery earns
per year by arbitrage + self-consumption). That is correct but incomplete.

For an honest investment decision you need three more things:

1. **A discount rate.** A krona saved in year 10 is not worth a krona saved
   today. We use a *real* (inflation-adjusted) discount rate, typically 3-5%,
   reflecting the opportunity cost of capital (what the money could earn
   elsewhere with similar risk).

2. **A battery degradation schedule.** A battery that loses 2% capacity per
   year delivers less savings in year 10 than in year 1. We apply a
   year-by-year derating factor to the base annual savings.

3. **Operating costs over time.** The battery + inverter draws standby power
   around the clock. On a typical Deye + BMS setup that's 40-80 W, which is
   ~350-700 kWh/year of grid power the battery *consumes*. Ignoring this
   overstates savings.

With those three corrections you can compute:

- **NPV** (Net Present Value): sum of all discounted cashflows. If positive,
  the investment beats the discount rate. If negative, it doesn't.

- **IRR** (Internal Rate of Return): the discount rate at which NPV = 0.
  Answers "what return am I actually getting on this investment?" Compare
  against what the money would earn in alternatives (savings account,
  index fund).

- **Discounted payback**: years until cumulative *discounted* cashflows turn
  positive. Always longer than simple (undiscounted) payback.

All functions here are pure — they take numbers, return numbers. No side
effects, no I/O. That makes them easy to test and easy to reuse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence


# ============================================================
# Assumptions
# ============================================================

@dataclass
class FinancialAssumptions:
    """Assumptions driving the financial analysis.

    All rates are *real* (inflation-adjusted) unless noted. Default values
    are intentionally conservative; adjust per scenario.
    """

    # Discount rate (real, fraction). The return your capital could earn
    # elsewhere. Swedish risk-free real rate has historically been 1-3%;
    # 4% represents a modest equity-like alternative.
    discount_rate: float = 0.04

    # Analysis horizon (years). Should not exceed the shorter of battery
    # cycle life and calendar life.
    analysis_horizon_years: int = 15

    # Real electricity price inflation. How fast do you expect retail
    # electricity prices to rise above general inflation? Historical Swedish
    # data: roughly 0-2% real over long periods. Leave at 0 unless you have
    # a specific view — extrapolating 2022-2023 volatility is a classic trap.
    electricity_price_inflation: float = 0.0

    # Battery capacity retention per year (fraction of year-1 capacity).
    # Typical LFP warranty: 70% at end of rated cycles. Spread linearly:
    # if rated 6000 cycles at 300/year = 20 years to 70%, that's 1.5%/year.
    # For a 15 kWh NKON ESS Pro with heavy use, assume 2%/year.
    annual_capacity_degradation: float = 0.02

    # Standby draw of battery + inverter + BMS, watts. Always-on load the
    # battery system creates. Deye 12K ~30 W + Seplos BMS ~15 W ≈ 45 W.
    standby_draw_w: float = 45.0

    # Price paid for the standby draw (SEK/kWh, incl. all taxes and fees).
    # This is import retail price since standby runs 24/7 including import
    # hours. Default is a realistic 2026 SE3 average.
    standby_price_sek_per_kwh: float = 1.80

    # Residual value at end of horizon, as fraction of initial investment.
    # Used-battery market is thin; set to 0 unless you have a clear resale
    # path. Setting to 0.1 assumes 10% scrap/resale value.
    residual_value_fraction: float = 0.0

    # Maintenance cost per year (SEK). Inverter fan replacement, the odd
    # service call. Usually small.
    annual_maintenance_sek: float = 0.0


# ============================================================
# Cashflow construction
# ============================================================

def build_cashflows(
    investment_sek: float,
    annual_savings_sek: float,
    assumptions: FinancialAssumptions,
    degradation_override: Callable[[int], float] | None = None,
) -> list[float]:
    """Build a list of year-by-year cashflows.

    Index 0 is the investment (negative). Index 1..N are annual net
    cashflows (positive = savings exceed operating costs).

    Applies, per year t ∈ 1..N:
        savings(t) = annual_savings × (1 + price_inflation)^(t-1)
                                     × capacity_retention(t)
        standby_cost = standby_w × 8760 / 1000 × standby_price
                                     × (1 + price_inflation)^(t-1)
        net(t) = savings(t) - standby_cost - maintenance

    The final year also gets the residual value added.

    degradation_override: optional function year→retention_factor, for
        calibrated manufacturer curves. Default is linear degradation.
    """
    N = assumptions.analysis_horizon_years
    cashflows: list[float] = [-investment_sek]

    # Default: linear degradation from 1.0 in year 1
    def default_retention(year: int) -> float:
        return max(0.0, 1.0 - assumptions.annual_capacity_degradation * (year - 1))

    retention = degradation_override or default_retention

    standby_kwh_per_year = assumptions.standby_draw_w * 8760 / 1000.0

    for t in range(1, N + 1):
        infl = (1.0 + assumptions.electricity_price_inflation) ** (t - 1)

        savings = annual_savings_sek * retention(t) * infl
        standby_cost = standby_kwh_per_year * assumptions.standby_price_sek_per_kwh * infl
        maintenance = assumptions.annual_maintenance_sek

        net = savings - standby_cost - maintenance

        if t == N:
            net += investment_sek * assumptions.residual_value_fraction

        cashflows.append(net)

    return cashflows


# ============================================================
# NPV
# ============================================================

def npv(cashflows: Sequence[float], discount_rate: float) -> float:
    """Net Present Value of a cashflow sequence.

    cashflows[0] is assumed to be at time zero (no discount applied);
    cashflows[t] for t >= 1 is discounted by (1 + r)^t.
    """
    return sum(cf / (1.0 + discount_rate) ** t for t, cf in enumerate(cashflows))


# ============================================================
# IRR
# ============================================================

def irr(cashflows: Sequence[float], guess: float = 0.05, tol: float = 1e-6,
        max_iter: int = 200) -> float | None:
    """Internal Rate of Return — the discount rate where NPV = 0.

    Uses Newton-Raphson with a bisection fallback. Returns None if no
    valid IRR exists (e.g. all cashflows same sign, or no sign change).

    For a typical battery investment (one negative cashflow followed by
    positive ones) IRR is unique and well-behaved.
    """
    # Sanity check: need at least one negative and one positive cashflow
    has_neg = any(cf < 0 for cf in cashflows)
    has_pos = any(cf > 0 for cf in cashflows)
    if not (has_neg and has_pos):
        return None

    # Newton-Raphson
    r = guess
    for _ in range(max_iter):
        # NPV and its derivative w.r.t. r
        f = sum(cf / (1.0 + r) ** t for t, cf in enumerate(cashflows))
        df = sum(-t * cf / (1.0 + r) ** (t + 1) for t, cf in enumerate(cashflows))

        if abs(df) < 1e-12:
            break
        r_new = r - f / df

        # Don't allow r to drop below -0.99 (division by zero territory)
        if r_new <= -0.99:
            r_new = -0.99 + 1e-6

        if abs(r_new - r) < tol:
            return r_new
        r = r_new

    # Newton failed — try bisection between -0.99 and +10 (1000%)
    lo, hi = -0.99, 10.0
    f_lo = npv(cashflows, lo)
    f_hi = npv(cashflows, hi)
    if f_lo * f_hi > 0:
        return None  # no sign change in bracket

    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv(cashflows, mid)
        if abs(f_mid) < tol:
            return mid
        if f_mid * f_lo < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


# ============================================================
# Discounted payback
# ============================================================

def discounted_payback(cashflows: Sequence[float], discount_rate: float) -> float | None:
    """Years until cumulative discounted cashflows turn positive.

    Returns a fractional year (interpolated within the year it happens).
    Returns None if never paid back within the horizon.

    cashflows[0] is the investment (negative).
    """
    cumulative = 0.0
    previous = 0.0
    for t, cf in enumerate(cashflows):
        discounted = cf / (1.0 + discount_rate) ** t
        previous = cumulative
        cumulative += discounted

        if cumulative >= 0 and t > 0:
            # Linear interpolation within year t
            if discounted == 0:
                return float(t)
            fraction = -previous / discounted
            return (t - 1) + fraction

    return None  # never paid back


# ============================================================
# High-level summary
# ============================================================

@dataclass
class FinancialResult:
    """Result of a full financial analysis."""
    investment_sek: float
    annual_savings_sek_year_1: float
    assumptions: FinancialAssumptions
    cashflows: list[float]
    npv_sek: float
    irr: float | None
    simple_payback_years: float | None  # undiscounted
    discounted_payback_years: float | None
    total_nominal_savings_sek: float  # sum of undiscounted positive cashflows
    standby_cost_per_year_sek: float

    @property
    def verdict(self) -> str:
        """One-line plain-language verdict."""
        if self.npv_sek > 0:
            irr_pct = (self.irr or 0) * 100
            return (f"LÖNSAM — NPV = {self.npv_sek:+,.0f} SEK vid "
                    f"{self.assumptions.discount_rate*100:.1f}% diskontering, "
                    f"IRR = {irr_pct:.1f}%")
        else:
            return (f"EJ LÖNSAM — NPV = {self.npv_sek:+,.0f} SEK vid "
                    f"{self.assumptions.discount_rate*100:.1f}% diskontering")


def analyze(
    investment_sek: float,
    annual_savings_sek: float,
    assumptions: FinancialAssumptions | None = None,
) -> FinancialResult:
    """Run the complete analysis and return a structured result.

    This is the main entry point. Most callers want this rather than the
    low-level functions.
    """
    if assumptions is None:
        assumptions = FinancialAssumptions()

    cashflows = build_cashflows(investment_sek, annual_savings_sek, assumptions)

    # Simple payback — ignore discounting and operating costs' inflation
    if annual_savings_sek > 0:
        standby_kwh = assumptions.standby_draw_w * 8760 / 1000.0
        standby_cost = standby_kwh * assumptions.standby_price_sek_per_kwh
        net_year_1 = annual_savings_sek - standby_cost - assumptions.annual_maintenance_sek
        simple_payback = investment_sek / net_year_1 if net_year_1 > 0 else None
    else:
        simple_payback = None
        standby_cost = (assumptions.standby_draw_w * 8760 / 1000.0 *
                        assumptions.standby_price_sek_per_kwh)

    return FinancialResult(
        investment_sek=investment_sek,
        annual_savings_sek_year_1=annual_savings_sek,
        assumptions=assumptions,
        cashflows=cashflows,
        npv_sek=npv(cashflows, assumptions.discount_rate),
        irr=irr(cashflows),
        simple_payback_years=simple_payback,
        discounted_payback_years=discounted_payback(cashflows, assumptions.discount_rate),
        total_nominal_savings_sek=sum(cf for cf in cashflows[1:] if cf > 0),
        standby_cost_per_year_sek=standby_cost,
    )


# ============================================================
# Pretty-print
# ============================================================

def print_report(result: FinancialResult, label: str = "Investering") -> None:
    """Print a formatted report to stdout."""
    a = result.assumptions
    print()
    print("=" * 70)
    print(f"  FINANSIELL ANALYS — {label}")
    print("=" * 70)
    print(f"  Investering:                    {result.investment_sek:>12,.0f} SEK")
    print(f"  Besparing år 1:                 {result.annual_savings_sek_year_1:>12,.0f} SEK/år")
    print()
    print(f"  Antaganden:")
    print(f"    Diskonteringsränta (real):    {a.discount_rate*100:>8.2f} %")
    print(f"    Analysperiod:                 {a.analysis_horizon_years:>8d} år")
    print(f"    Elprisinflation (real):       {a.electricity_price_inflation*100:>8.2f} %/år")
    print(f"    Batteridegradering:           {a.annual_capacity_degradation*100:>8.2f} %/år")
    print(f"    Standbyeffekt:                {a.standby_draw_w:>8.0f} W")
    print(f"    Standbykostnad:               {result.standby_cost_per_year_sek:>8,.0f} SEK/år")
    print(f"    Restvärde:                    {a.residual_value_fraction*100:>8.1f} % av inköp")
    print("-" * 70)
    print(f"  NPV @ {a.discount_rate*100:.1f}%:                    {result.npv_sek:>+12,.0f} SEK")

    if result.irr is not None:
        print(f"  IRR (real):                     {result.irr*100:>12.2f} %")
    else:
        print(f"  IRR (real):                     {'ej definierad':>12s}")

    if result.simple_payback_years is not None:
        print(f"  Återbetalningstid (enkel):      {result.simple_payback_years:>12.1f} år")
    else:
        print(f"  Återbetalningstid (enkel):      {'aldrig':>12s}")

    if result.discounted_payback_years is not None:
        print(f"  Återbetalningstid (diskonterad):{result.discounted_payback_years:>12.1f} år")
    else:
        print(f"  Återbetalningstid (diskonterad):{'ej inom horisont':>12s}")

    print(f"  Total besparing (nominell):     {result.total_nominal_savings_sek:>+12,.0f} SEK")
    print("-" * 70)
    print(f"  {result.verdict}")
    print("=" * 70)
