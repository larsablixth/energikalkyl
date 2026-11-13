"""
Economic evaluation of simulation results (pure functions, no Streamlit).

app.py runs the simulations and calls these to turn a SimResult into the
headline numbers: solar direct use, effekttariff (peak demand) savings,
export revenue the panels would earn without a battery, the household's bill
without any investment (to compare an operator's tariffs), wear and standby
over the years, and loan cost over the battery lifetime.
"""

import math
from collections import defaultdict
from dataclasses import replace

from tariff import EffektTariff


def solar_direct_use(result, cfg) -> tuple[float, float]:
    """Solar used directly by the house: (kWh, SEK) over the whole result.

    Per slot (1 hour) the house can use at most its own load; the rest goes to
    the battery, flex loads, export or is curtailed, none of which is direct use.
    Valued at that slot's full purchase price (spot incl. VAT + grid fee + tax).

    Call right after simulate() with the same cfg: total_load_kw() depends on the
    smart-load schedule that simulate() writes into cfg.
    """
    kwh = sek = 0.0
    for s in result.slots:
        if s.solar_kw <= 0:
            continue
        h = int(s.hour.split(":")[0])
        month = int(s.date.split("-")[1])
        direct = min(s.solar_kw, cfg.total_load_kw(h, month, s.date))
        kwh += direct
        sek += direct * s.total_cost_ore / 100
    return kwh, sek


def solar_flows(result, direct_kwh) -> dict:
    """Where the solar production went (kWh over the whole result).

    direct_kwh comes from solar_direct_use(). Battery = solar charged into the
    battery, flex = flexible loads (they only run on solar surplus), exported =
    solar sent to the grid (battery export in discharge slots is excluded),
    curtailed = what is left: produced but never used (zero-export inverter
    throttling).
    """
    produced = battery = flex = exported = 0.0
    for s in result.slots:
        produced += s.solar_kw  # hourly slots: kW == kWh
        battery += s.solar_charge_kwh
        flex += s.flex_consumed_kwh
        bat_export = s.energy_kwh if s.action == "discharge" else 0.0
        exported += max(0.0, s.grid_export_kwh - bat_export)
    curtailed = max(0.0, produced - direct_kwh - battery - flex - exported)
    return {"produced": produced, "direct": direct_kwh, "battery": battery,
            "flex": flex, "exported": exported, "curtailed": curtailed}


def standby_cost_per_year(standby_w, avg_price_ore) -> float:
    """SEK/yr for a constant standby draw (inverter + BMS) at an average price.

    standby_w × 8,760 h = standby_w × 8.76 kWh per year.
    """
    return standby_w * 8.76 * avg_price_ore / 100


def yearly_benefit(bat_part, solar_part, fixed_part, year, bat_fade, solar_deg) -> float:
    """Benefit (SEK) in year `year` (1-based), with wear evaluated mid-year.

    bat_part: battery value per year when new; it falls linearly by bat_fade
    (fraction of capacity per year). solar_part: solar direct use counted as
    value when new; panels degrade geometrically by solar_deg per year.
    fixed_part: unaffected by wear (−fuse fee delta − standby cost).
    """
    age = year - 0.5
    return (bat_part * max(0.0, 1.0 - bat_fade * age)
            + solar_part * (1.0 - solar_deg) ** age
            + fixed_part)


def lifetime_benefit(bat_part, solar_part, fixed_part, lifetime, bat_fade, solar_deg) -> float:
    """Sum of yearly_benefit over the lifetime; the last partial year is weighted
    by its fraction.

    bat_part may be a number or a function year -> battery value when new (used
    by the future scenarios, where the battery value changes from year to year).
    """
    bat_at = bat_part if callable(bat_part) else (lambda _yr: bat_part)
    total = 0.0
    for yr in range(1, int(math.ceil(lifetime)) + 1):
        weight = min(1.0, lifetime - (yr - 1))
        total += yearly_benefit(bat_at(yr), solar_part, fixed_part, yr, bat_fade, solar_deg) * weight
    return total


def payback_years(investment, bat_part, solar_part, fixed_part, bat_fade, solar_deg,
                  horizon=25, lifetime=None):
    """Years until the cumulative (worn) benefit equals the investment.

    Interpolated within the year. None if it isn't reached within `horizon`
    years (the solar lifetime).

    lifetime: battery lifetime in years. After it the battery is worn out, so
    its value and everything tied to it (standby cost, fuse fee delta) stop;
    only the panels keep paying. None = the battery never wears out.
    """
    if investment <= 0:
        return 0.0
    cum = 0.0
    for yr in range(1, horizon + 1):
        alive = 1.0 if lifetime is None else max(0.0, min(1.0, lifetime - (yr - 1)))
        b = (alive * yearly_benefit(bat_part, solar_part, fixed_part, yr, bat_fade, solar_deg)
             + (1.0 - alive) * yearly_benefit(0.0, solar_part, 0.0, yr, bat_fade, solar_deg))
        if b > 0 and cum + b >= investment:
            return yr - 1 + (investment - cum) / b
        cum += b
    return None


def value_at_level(values, level) -> float:
    """Value at `level`, linearly interpolated in {level: value} (clamped at the ends)."""
    levels = sorted(values)
    below = [v for v in levels if v <= level]
    above = [v for v in levels if v > level]
    if below and above:
        b, a = below[-1], above[0]
        frac = (level - b) / (a - b)
        return values[b] * (1 - frac) + values[a] * frac
    return values[below[-1]] if below else values[levels[0]]


def scenario_bat_part(bat_by_vol, target_vol, year, ramp_years=10) -> float:
    """Battery value (when new) in `year` of a future scenario: volatility moves
    linearly from today's (1.0) to target_vol over ramp_years, then stays there."""
    return value_at_level(bat_by_vol, 1.0 + (target_vol - 1.0) * min(year, ramp_years) / ramp_years)


def _effekt_monthly_peaks(result, tariff, cfg, solar_in_baseline):
    """Measured monthly peaks WITH and WITHOUT the investment, per month.

    Returns [(month, avg_without_kw, avg_with_kw)], one entry per "YYYY-MM" in the
    result. Operator rules: only tariff.is_peak_hour() hours count, weighted by
    tariff.kw_factor() (night discount), monthly peak = average of the top N daily
    peaks (one per day).

    solar_in_baseline: the panels exist anyway, so the "without" peak is load minus
    solar. Otherwise it is the raw load (solar's peak reduction belongs to the
    investment).
    """
    monthly_slots = defaultdict(list)
    for s in result.slots:
        monthly_slots[s.date[:7]].append(s)

    out = []
    for ym, slots in monthly_slots.items():
        daily_peaks_with = defaultdict(float)
        daily_peaks_without = defaultdict(float)

        for s in slots:
            if not tariff.is_peak_hour(s.date, s.hour):
                continue
            h = int(s.hour.split(":")[0])
            month = int(s.date.split("-")[1])
            load_kw = cfg.total_load_kw(h, month, s.date)
            net_kw = max(0.0, load_kw - s.solar_kw)
            factor = tariff.kw_factor(s.date, s.hour)

            without_kw = net_kw if solar_in_baseline else load_kw
            # Grid draw with the investment: solar covers the house first; surplus
            # (battery, flex, export, curtailment) never draws from the grid.
            if s.action == "discharge":
                with_kw = max(0.0, net_kw - s.power_kw)
            elif s.action == "charge":
                with_kw = net_kw + s.power_kw
            else:
                with_kw = net_kw

            daily_peaks_without[s.date] = max(daily_peaks_without[s.date], without_kw * factor)
            daily_peaks_with[s.date] = max(daily_peaks_with[s.date], with_kw * factor)

        n = tariff.top_n_peaks
        peaks_without = sorted(daily_peaks_without.values(), reverse=True)[:n]
        peaks_with = sorted(daily_peaks_with.values(), reverse=True)[:n]
        avg_without = sum(peaks_without) / len(peaks_without) if peaks_without else 0
        avg_with = sum(peaks_with) / len(peaks_with) if peaks_with else 0
        out.append((int(ym.split("-")[1]), avg_without, avg_with))
    return out


def _effekt_rate(tariff, month):
    return tariff.get_effekt_rate(month) if hasattr(tariff, "get_effekt_rate") else tariff.effekt_rate


def effekt_savings(result, tariff, cfg, num_days, solar_in_baseline=False) -> float:
    """Yearly change in effektavgift (peak demand charge) caused by the investment.

    Compares the monthly measured peak WITH the investment (grid draw after
    solar, battery charging and discharging) vs WITHOUT it. Positive = saving;
    negative = the battery's charging raised the peak and costs money.

    solar_in_baseline: the panels exist anyway (not part of the investment), so
    the "without" peak is load minus solar. Otherwise the "without" peak is the
    raw load and solar's peak reduction is credited to the investment.

    Peak rules: see _effekt_monthly_peaks(); priced with tariff.get_effekt_rate(month).

    Call right after simulate() with the same cfg (smart-load schedule).
    """
    # No clamp: a higher peak with the battery is a real extra cost
    total_saving = sum((without - with_) * _effekt_rate(tariff, month)
                       for month, without, with_ in
                       _effekt_monthly_peaks(result, tariff, cfg, solar_in_baseline))
    years = num_days / 365.25
    return total_saving / years if years > 0 else 0.0


def tariff_switch_saving(baseline_bills, current_tariff):
    """Yearly saving from moving from the household's current tariff to the cheapest one,
    WITHOUT investing (baseline_bills: {tariff name: bill SEK/yr without investing}).

    Returns (saving SEK/yr, cheapest tariff name), or None when the current tariff is
    unknown or not among the simulated ones. 0 when the current tariff is the cheapest.
    The investment result is measured against the cheapest tariff, so
    saving + net_benefit_yr is the household's total change versus today.
    """
    if not baseline_bills or current_tariff not in baseline_bills:
        return None
    cheapest = min(baseline_bills, key=baseline_bills.get)
    return baseline_bills[current_tariff] - baseline_bills[cheapest], cheapest


def baseline_bill(result, tariff, cfg, num_days, solar_in_baseline=False) -> float:
    """Yearly variable electricity cost (SEK) of the household WITHOUT the investment
    under `tariff`: what it would pay on that tariff if it didn't invest.

    Energy: every slot's load × that slot's full purchase price (total_cost_ore:
    spot incl. VAT + grid energy fee + energy tax). With solar_in_baseline (panels
    the household already has) only the load the panels don't cover is bought,
    max(0, load − solar). Plus, for an EffektTariff, the demand charge of the
    no-investment monthly peaks (same peak rules as effekt_savings()).

    The fixed subscription (fuse) fee is left out: it is the same for all of an
    operator's tariffs at a given fuse. Used to compare the operator's tariffs with
    each other, not as an absolute bill.

    Call right after simulate() with the same cfg (smart-load schedule).
    """
    energy = 0.0
    for s in result.slots:
        h = int(s.hour.split(":")[0])
        month = int(s.date.split("-")[1])
        load_kw = cfg.total_load_kw(h, month, s.date)
        if solar_in_baseline:
            load_kw = max(0.0, load_kw - s.solar_kw)
        energy += load_kw * s.total_cost_ore / 100  # hourly slots: kW == kWh
    demand = 0.0
    if isinstance(tariff, EffektTariff):
        demand = sum(without * _effekt_rate(tariff, month)
                     for month, without, _ in
                     _effekt_monthly_peaks(result, tariff, cfg, solar_in_baseline))
    years = num_days / 365.25
    return (energy + demand) / years if years > 0 else 0.0


def baseline_export_revenue(prices, cfg, tariff, solar) -> float:
    """Export revenue (SEK, whole period) the panels earn with NO battery.

    With existing panels and export enabled, this revenue is not created by the
    battery and must be subtracted from result.net_profit_sek.
    """
    from batteri import simulate
    no_bat = replace(cfg, capacity_kwh=0.0, max_charge_kw=0.0, max_discharge_kw=0.0,
                     _smart_schedule={})
    return simulate(prices, no_bat, tariff=tariff, solar=solar).total_export_revenue


def loan_schedule(principal, annual_rate_pct, loan_years, horizon_years) -> dict:
    """Annuity loan seen over a horizon (normally the battery lifetime).

    Returns monthly_payment, paid_in_horizon, interest_in_horizon and
    balance_at_horizon (debt still owed when the horizon ends; 0 if the loan
    is repaid before then).
    """
    n = max(0, loan_years) * 12
    if principal <= 0 or n <= 0:
        return {"monthly_payment": 0.0, "paid_in_horizon": 0.0,
                "interest_in_horizon": 0.0, "balance_at_horizon": 0.0}
    r = annual_rate_pct / 100 / 12
    if r > 0:
        pmt = principal * r / (1 - (1 + r) ** -n)
    else:
        pmt = principal / n
    k = min(n, max(0.0, horizon_years * 12))
    if k >= n:
        balance = 0.0
        paid = pmt * n
    else:
        if r > 0:
            growth = (1 + r) ** k
            balance = principal * growth - pmt * (growth - 1) / r
        else:
            balance = principal - pmt * k
        paid = pmt * k
    interest = paid - (principal - balance)
    return {"monthly_payment": pmt, "paid_in_horizon": paid,
            "interest_in_horizon": interest, "balance_at_horizon": balance}
