"""
Economic evaluation of simulation results (pure functions, no Streamlit).

app.py runs the simulations and calls these to turn a SimResult into the
headline numbers: solar direct use, effekttariff (peak demand) savings,
export revenue the panels would earn without a battery, and loan cost
over the battery lifetime.
"""

from collections import defaultdict
from dataclasses import replace


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


def effekt_savings(result, tariff, cfg, num_days, solar_in_baseline=False) -> float:
    """Yearly change in effektavgift (peak demand charge) caused by the investment.

    Compares the monthly measured peak WITH the investment (grid draw after
    solar, battery charging and discharging) vs WITHOUT it. Positive = saving;
    negative = the battery's charging raised the peak and costs money.

    solar_in_baseline: the panels exist anyway (not part of the investment), so
    the "without" peak is load minus solar. Otherwise the "without" peak is the
    raw load and solar's peak reduction is credited to the investment.

    Operator rules: only tariff.is_peak_hour() hours count, weighted by
    tariff.kw_factor() (night discount), monthly peak = average of the top N
    daily peaks (one per day), priced with tariff.get_effekt_rate(month).

    Call right after simulate() with the same cfg (smart-load schedule).
    """
    monthly_slots = defaultdict(list)
    for s in result.slots:
        monthly_slots[s.date[:7]].append(s)

    total_saving = 0.0
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

        month = int(ym.split("-")[1])
        rate = tariff.get_effekt_rate(month) if hasattr(tariff, "get_effekt_rate") else tariff.effekt_rate
        # No clamp: a higher peak with the battery is a real extra cost
        total_saving += (avg_without - avg_with) * rate

    years = num_days / 365.25
    return total_saving / years if years > 0 else 0.0


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
