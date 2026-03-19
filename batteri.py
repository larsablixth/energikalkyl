"""
Battery profitability simulator.

Simulates a home battery that charges when electricity is cheap and
discharges when it is expensive, subject to:

- Battery capacity (kWh)
- Max charge/discharge power (kW)
- Grid fuse limit (ampere) — limits total power drawn from the grid
- Time-varying household load (base + EV charging etc.)
- Round-trip efficiency (%)
- Number of phases (1 or 3)
- Grid voltage (V)
- Grid tariff model (tidstariff or enkeltariff)
"""

from dataclasses import dataclass, field


@dataclass
class LoadSchedule:
    """
    A scheduled load that runs during specific hours.

    Example: EV charging 11 kW from 23:00 to 06:00
        LoadSchedule(name="Elbil", power_kw=11.0, start_hour=23, end_hour=6)
    """
    name: str
    power_kw: float
    start_hour: int   # 0-23
    end_hour: int     # 0-23 (wraps past midnight if end < start)

    def is_active(self, hour: int) -> bool:
        """Check if this load is active at the given hour."""
        if self.start_hour <= self.end_hour:
            return self.start_hour <= hour < self.end_hour
        else:
            # Wraps past midnight, e.g. 23-06
            return hour >= self.start_hour or hour < self.end_hour


@dataclass
class FlexibleLoad:
    """
    A flexible/dumpable load that preferentially runs on solar surplus or cheap grid power.

    Examples: pool heat pump, hot water tank, EV smart charging.
    These loads absorb surplus solar before the battery, reducing
    what's available for battery charging but also reducing grid export
    at low prices.
    """
    name: str
    power_kw: float           # power draw when running
    daily_kwh: float = 0.0    # target daily energy (0 = unlimited, runs whenever surplus)
    start_month: int = 1      # first active month
    end_month: int = 12       # last active month (inclusive)
    min_hour: int = 6         # earliest hour to run
    max_hour: int = 22        # latest hour to run

    def is_available(self, month: int, hour: int) -> bool:
        """Check if this load can run at the given month and hour."""
        if self.start_month <= self.end_month:
            if not (self.start_month <= month <= self.end_month):
                return False
        else:
            if not (month >= self.start_month or month <= self.end_month):
                return False
        return self.min_hour <= hour < self.max_hour


@dataclass
class BatteryConfig:
    capacity_kwh: float = 13.5        # e.g. Tesla Powerwall
    max_charge_kw: float = 5.0        # max charge rate
    max_discharge_kw: float = 5.0     # max discharge rate
    efficiency: float = 0.90          # round-trip efficiency
    fuse_amps: float = 25.0           # main fuse rating (max available: 35A)
    phases: int = 3                   # number of phases
    voltage: float = 230.0            # grid voltage
    base_load_kw: float = 1.5         # household base load (always on)
    scheduled_loads: list[LoadSchedule] = field(default_factory=list)
    hourly_load_profile: dict[int, float] | None = None  # actual kW per hour (0-23), overrides base+scheduled
    seasonal_load_profile: dict[int, dict[int, float]] | None = None  # month -> hour -> kW
    flexible_loads: list[FlexibleLoad] = field(default_factory=list)
    min_soc: float = 0.05             # minimum state of charge (fraction)
    max_soc: float = 0.95             # maximum state of charge (fraction)
    # Investment
    purchase_price: float = 0.0       # battery purchase price (SEK)
    installation_cost: float = 0.0    # installation cost (SEK)
    cycle_life: int = 8000            # rated cycles at ~70% SoH
    calendar_life_years: int = 15     # max calendar lifetime
    # Grid export
    export_price_factor: float = 1.0  # fraction of spot price received for export (1.0 = full spot)
    export_fee_ore: float = 5.0       # provider fee per exported kWh (öre)

    @property
    def grid_max_kw(self) -> float:
        """Max power from grid based on fuse size."""
        return self.fuse_amps * self.voltage * self.phases / 1000.0

    def total_load_kw(self, hour: int, month: int = None) -> float:
        """Total household load at a given hour (and optionally month)."""
        if self.seasonal_load_profile is not None and month is not None:
            return self.seasonal_load_profile.get(month, {}).get(hour, self.base_load_kw)
        if self.hourly_load_profile is not None:
            return self.hourly_load_profile.get(hour, self.base_load_kw)
        load = self.base_load_kw
        for s in self.scheduled_loads:
            if s.is_active(hour):
                load += s.power_kw
        return load

    def available_charge_kw(self, hour: int, month: int = None) -> float:
        """Max charging power considering fuse headroom at a given hour."""
        headroom = self.grid_max_kw - self.total_load_kw(hour, month)
        return min(self.max_charge_kw, max(0.0, headroom))

    @property
    def usable_kwh(self) -> float:
        return self.capacity_kwh * (self.max_soc - self.min_soc)

    def fuse_analysis(self) -> list[dict]:
        """
        Analyze fuse headroom per hour (and month if seasonal).
        Returns list of warnings about constrained hours.
        """
        warnings = []
        grid_max = self.grid_max_kw

        months = range(1, 13) if self.seasonal_load_profile else [None]
        months_sv = ["", "jan", "feb", "mar", "apr", "maj", "jun",
                     "jul", "aug", "sep", "okt", "nov", "dec"]

        for m in months:
            for h in range(24):
                load = self.total_load_kw(h, m)
                headroom = grid_max - load
                charge_possible = self.available_charge_kw(h, m)

                if load > grid_max:
                    period = f"{months_sv[m]} kl {h:02d}" if m else f"kl {h:02d}"
                    warnings.append({
                        "type": "overload",
                        "severity": "error",
                        "hour": h,
                        "month": m,
                        "period": period,
                        "load_kw": round(load, 1),
                        "grid_max_kw": round(grid_max, 1),
                        "over_kw": round(load - grid_max, 1),
                        "msg": f"ÖVERBELASTNING {period}: last {load:.1f} kW > säkring {grid_max:.1f} kW ({load-grid_max:.1f} kW för mycket)",
                    })
                elif charge_possible < 0.5:
                    period = f"{months_sv[m]} kl {h:02d}" if m else f"kl {h:02d}"
                    warnings.append({
                        "type": "no_charge",
                        "severity": "warning",
                        "hour": h,
                        "month": m,
                        "period": period,
                        "load_kw": round(load, 1),
                        "headroom_kw": round(headroom, 1),
                        "msg": f"Ingen laddkapacitet {period}: last {load:.1f} kW, {headroom:.1f} kW kvar (behöver minst 0.5 kW)",
                    })
                elif charge_possible < self.max_charge_kw * 0.5:
                    period = f"{months_sv[m]} kl {h:02d}" if m else f"kl {h:02d}"
                    warnings.append({
                        "type": "limited",
                        "severity": "info",
                        "hour": h,
                        "month": m,
                        "period": period,
                        "charge_kw": round(charge_possible, 1),
                        "max_kw": self.max_charge_kw,
                        "msg": f"Begränsad laddning {period}: {charge_possible:.1f} kW av {self.max_charge_kw:.0f} kW möjlig",
                    })

        return warnings


@dataclass
class SlotResult:
    date: str
    hour: str
    sek_per_kwh: float
    grid_fee_ore: float      # grid transfer fee + energy tax for this slot
    total_cost_ore: float    # spot + grid fee (total cost per kWh)
    action: str              # "charge", "discharge", "idle", "solar_charge"
    power_kw: float
    energy_kwh: float
    soc_before: float
    soc_after: float
    cost_sek: float          # cost of charging (spot + grid fee)
    saving_sek: float        # value of discharging (avoided spot + grid fee)
    solar_kw: float = 0.0    # solar production this slot
    solar_charge_kwh: float = 0.0  # energy charged from solar (free)
    flex_consumed_kwh: float = 0.0  # energy consumed by flexible loads from solar
    grid_export_kwh: float = 0.0   # surplus solar exported to grid
    export_revenue_sek: float = 0.0  # revenue from grid export


@dataclass
class SimResult:
    config: BatteryConfig
    tariff_name: str = ""
    slots: list[SlotResult] = field(default_factory=list)

    @property
    def total_charged_kwh(self) -> float:
        return sum(s.energy_kwh for s in self.slots if s.action == "charge")

    @property
    def total_discharged_kwh(self) -> float:
        return sum(s.energy_kwh for s in self.slots if s.action == "discharge")

    @property
    def total_charge_cost(self) -> float:
        return sum(s.cost_sek for s in self.slots if s.action == "charge")

    @property
    def total_discharge_value(self) -> float:
        return sum(s.saving_sek for s in self.slots if s.action == "discharge")

    @property
    def total_solar_charge_kwh(self) -> float:
        return sum(s.solar_charge_kwh for s in self.slots)

    @property
    def total_solar_production_kwh(self) -> float:
        return sum(s.solar_kw for s in self.slots)

    @property
    def total_flex_consumed_kwh(self) -> float:
        return sum(s.flex_consumed_kwh for s in self.slots)

    @property
    def total_grid_export_kwh(self) -> float:
        return sum(s.grid_export_kwh for s in self.slots)

    @property
    def total_export_revenue(self) -> float:
        return sum(s.export_revenue_sek for s in self.slots)

    @property
    def net_profit_sek(self) -> float:
        return self.total_discharge_value - self.total_charge_cost + self.total_export_revenue

    @property
    def num_cycles(self) -> float:
        if self.config.usable_kwh == 0:
            return 0
        return self.total_discharged_kwh / self.config.usable_kwh


def simulate(prices: list[dict], config: BatteryConfig, tariff=None, solar=None) -> SimResult:
    """
    Run a greedy day-by-day battery simulation.

    Strategy: for each day, rank slots by effective cost (considering solar).
    1. Solar surplus charges the battery for free (no grid cost).
    2. Remaining capacity charges during cheapest grid slots.
    3. Discharge during most expensive slots.

    prices: list of dicts with keys date, hour, sek_per_kwh
    tariff: a Tidstariff or FastTariff instance (or None for spot-only)
    solar: a SolarConfig instance (or None for no solar)
    """
    result = SimResult(config=config, tariff_name=tariff.name if tariff else "Ingen (enbart spotpris)")
    soc = config.capacity_kwh * config.min_soc  # start empty

    slot_duration_h = _detect_slot_duration(prices)

    # Solar production function
    if solar:
        from solar import get_solar_for_slot
        def _solar_kw(date_str, hour_str):
            return get_solar_for_slot(date_str, hour_str, solar)
    else:
        def _solar_kw(date_str, hour_str):
            return 0.0

    # Group prices by date
    days: dict[str, list[dict]] = {}
    for row in prices:
        d = row["date"]
        days.setdefault(d, []).append(row)

    for day_date in sorted(days.keys()):
        day_prices = days[day_date]

        # Calculate total cost per slot (spot + grid fee)
        slot_costs = []
        for i, p in enumerate(day_prices):
            spot_ore = float(p["sek_per_kwh"]) * 100
            grid_ore = tariff.total_cost_ore(p["date"], p["hour"]) if tariff else 0
            total_ore = spot_ore + grid_ore
            solar_kw = _solar_kw(p["date"], p["hour"])
            h = int(p["hour"].split(":")[0])
            month = int(p["date"].split("-")[1])
            load_kw = config.total_load_kw(h, month)
            solar_surplus_kw = max(0, solar_kw - load_kw)
            # Effective cost is lower when solar surplus can charge for free
            slot_costs.append((i, total_ore, spot_ore, grid_ore, solar_surplus_kw))

        # Smart multi-cycle charge/discharge scheduling:
        # With day-ahead prices known at 13:00, we have perfect foresight.
        # On volatile days (winter), multiple charge-discharge cycles per day
        # can capture more of the price spread.
        #
        # Strategy: find profitable charge-discharge pairs where the spread
        # covers the round-trip efficiency loss.

        n_slots = len(slot_costs)
        slot_cost_map = {idx: (total_ore, spot_ore, grid_ore) for idx, total_ore, spot_ore, grid_ore, _ in slot_costs}

        # Sort all slots by price
        sorted_by_cost = sorted(slot_costs, key=lambda x: x[1])

        # Calculate break-even spread: need at least (1/efficiency - 1) margin
        min_spread_factor = 1.0 / config.efficiency  # e.g. 1.075 for 93% efficiency

        # Greedy multi-cycle: pair cheapest unused charge slot with most expensive
        # unused discharge slot, as long as the spread is profitable
        charge_indices = set()
        discharge_indices = set()

        cheap_slots = list(sorted_by_cost)  # cheapest first
        expensive_slots = list(reversed(sorted_by_cost))  # most expensive first

        total_charge_possible = 0.0
        total_discharge_possible = 0.0
        max_cycles = 3  # limit to avoid unrealistic cycling

        # Estimate how much solar surplus will charge the battery today
        # so we don't fill up with grid power and waste free solar
        expected_solar_charge = sum(
            min(surplus, config.max_charge_kw) * slot_duration_h
            for _, _, _, _, surplus in slot_costs if surplus > 0.01
        )
        expected_solar_charge = min(expected_solar_charge, config.usable_kwh)

        for cycle in range(max_cycles):
            # Find next batch of cheap slots to fill battery
            cycle_charge = set()
            cycle_charge_energy = 0.0
            # Leave room for expected free solar charging
            energy_needed = max(0, config.usable_kwh - expected_solar_charge) / config.efficiency

            for idx, total_ore, spot_ore, grid_ore, solar_surplus in cheap_slots:
                if idx in charge_indices or idx in discharge_indices:
                    continue
                if cycle_charge_energy >= energy_needed:
                    break
                h = int(day_prices[idx]["hour"].split(":")[0])
                month = int(day_prices[idx]["date"].split("-")[1])
                avail_kw = config.available_charge_kw(h, month)
                if avail_kw > 0.1:
                    cycle_charge.add(idx)
                    cycle_charge_energy += avail_kw * slot_duration_h

            if not cycle_charge:
                break

            # Find matching expensive discharge slots
            cycle_discharge = set()
            cycle_discharge_energy = 0.0

            for idx, total_ore, spot_ore, grid_ore, solar_surplus in expensive_slots:
                if idx in charge_indices or idx in discharge_indices or idx in cycle_charge:
                    continue
                if cycle_discharge_energy >= config.usable_kwh:
                    break
                cycle_discharge.add(idx)
                cycle_discharge_energy += config.max_discharge_kw * slot_duration_h

            if not cycle_discharge:
                break

            # Check if this cycle is profitable
            # Need both: efficiency margin AND minimum absolute spread
            avg_charge_price = sum(slot_cost_map[i][0] for i in cycle_charge) / len(cycle_charge)
            avg_discharge_price = sum(slot_cost_map[i][0] for i in cycle_discharge) / len(cycle_discharge)
            absolute_spread = avg_discharge_price - avg_charge_price
            min_absolute_spread = 20  # öre/kWh — don't cycle for tiny spreads

            if (avg_discharge_price > avg_charge_price * min_spread_factor
                    and absolute_spread > min_absolute_spread):
                charge_indices.update(cycle_charge)
                discharge_indices.update(cycle_discharge)
            else:
                break  # No more profitable cycles

        # Fallback: if no profitable cycles found, use simple cheapest/expensive split
        if not charge_indices:
            for idx, total_ore, spot_ore, grid_ore, solar_surplus in sorted_by_cost[:n_slots // 4]:
                h = int(day_prices[idx]["hour"].split(":")[0])
                month = int(day_prices[idx]["date"].split("-")[1])
                if config.available_charge_kw(h, month) > 0.1:
                    charge_indices.add(idx)
            for idx, total_ore, spot_ore, grid_ore, solar_surplus in sorted_by_cost[-(n_slots // 4):]:
                if idx not in charge_indices:
                    discharge_indices.add(idx)

        avg_total = sum(tc for _, tc, _, _, _ in slot_costs) / len(slot_costs) if slot_costs else 0

        # Track daily flexible load energy
        flex_daily_used: dict[str, float] = {fl.name: 0.0 for fl in config.flexible_loads}

        for i, row in enumerate(day_prices):
            spot_ore = float(row["sek_per_kwh"]) * 100
            grid_ore = tariff.total_cost_ore(row["date"], row["hour"]) if tariff else 0
            total_ore = spot_ore + grid_ore
            h = int(row["hour"].split(":")[0])
            month = int(row["date"].split("-")[1])
            solar_kw = _solar_kw(row["date"], row["hour"])
            load_kw = config.total_load_kw(h, month)
            solar_surplus_kw = max(0, solar_kw - load_kw)
            soc_before = soc

            # --- Step 0: Flexible loads absorb solar surplus first ---
            flex_consumed_kw = 0.0
            for fl in config.flexible_loads:
                if not fl.is_available(month, h):
                    continue
                if fl.daily_kwh > 0 and flex_daily_used[fl.name] >= fl.daily_kwh:
                    continue  # daily target met
                if solar_surplus_kw - flex_consumed_kw > 0.1:
                    absorbed = min(fl.power_kw, solar_surplus_kw - flex_consumed_kw)
                    flex_consumed_kw += absorbed
                    flex_daily_used[fl.name] += absorbed * slot_duration_h

            solar_surplus_kw = max(0, solar_surplus_kw - flex_consumed_kw)

            # --- Step 1: Charge from remaining solar surplus (it's free) ---
            solar_charge_kwh = 0.0
            if solar_surplus_kw > 0.001:
                # Solar surplus charges battery (limited by battery charge rate and room)
                solar_charge_power = min(solar_surplus_kw, config.max_charge_kw)
                solar_energy = solar_charge_power * slot_duration_h
                room = (config.capacity_kwh * config.max_soc) - soc
                solar_energy = min(solar_energy, room)
                if solar_energy > 0.001:
                    soc += solar_energy
                    solar_charge_kwh = solar_energy

            # Calculate remaining surplus after battery + flex → export to grid
            remaining_surplus_kw = solar_surplus_kw - (solar_charge_kwh / slot_duration_h if slot_duration_h > 0 else 0)
            grid_export_kwh = max(0, remaining_surplus_kw * slot_duration_h)
            export_revenue = 0.0
            if grid_export_kwh > 0.001:
                # Export revenue: spot price × factor - provider fee
                export_ore = spot_ore * config.export_price_factor - config.export_fee_ore
                export_revenue = grid_export_kwh * max(0, export_ore) / 100

            # --- Step 2: Grid charge during cheap slots (if room left) ---
            if i in charge_indices and total_ore < avg_total:
                grid_charge_kw = config.available_charge_kw(h, month)
                # Reduce grid charge by any solar already charging
                if solar_charge_kwh > 0:
                    grid_charge_kw = max(0, grid_charge_kw - solar_charge_kwh / slot_duration_h)
                max_energy = grid_charge_kw * slot_duration_h
                room = (config.capacity_kwh * config.max_soc) - soc
                energy = min(max_energy, room)
                if energy > 0.001:
                    soc += energy
                    cost = energy * total_ore / 100  # SEK
                    result.slots.append(SlotResult(
                        date=row["date"], hour=row["hour"],
                        sek_per_kwh=float(row["sek_per_kwh"]),
                        grid_fee_ore=round(grid_ore, 2),
                        total_cost_ore=round(total_ore, 2),
                        action="charge",
                        power_kw=energy / slot_duration_h,
                        energy_kwh=round(energy, 4),
                        soc_before=round(soc_before, 4),
                        soc_after=round(soc, 4),
                        cost_sek=round(cost, 4),
                        saving_sek=0.0,
                        solar_kw=round(solar_kw, 4),
                        solar_charge_kwh=round(solar_charge_kwh, 4),
                        flex_consumed_kwh=round(flex_consumed_kw * slot_duration_h, 4),
                        grid_export_kwh=round(grid_export_kwh, 4),
                        export_revenue_sek=round(export_revenue, 4),
                    ))
                    continue

            # --- Step 3: Discharge during expensive slots ---
            if i in discharge_indices and total_ore > avg_total:
                max_energy = config.max_discharge_kw * slot_duration_h
                available = soc - (config.capacity_kwh * config.min_soc)
                deliverable = available * config.efficiency
                energy_out = min(max_energy, deliverable)
                if energy_out > 0.001:
                    drained = energy_out / config.efficiency
                    soc -= drained
                    value = energy_out * total_ore / 100  # SEK
                    result.slots.append(SlotResult(
                        date=row["date"], hour=row["hour"],
                        sek_per_kwh=float(row["sek_per_kwh"]),
                        grid_fee_ore=round(grid_ore, 2),
                        total_cost_ore=round(total_ore, 2),
                        action="discharge",
                        power_kw=energy_out / slot_duration_h,
                        energy_kwh=round(energy_out, 4),
                        soc_before=round(soc_before, 4),
                        soc_after=round(soc, 4),
                        cost_sek=0.0,
                        saving_sek=round(value, 4),
                        solar_kw=round(solar_kw, 4),
                        solar_charge_kwh=round(solar_charge_kwh, 4),
                        flex_consumed_kwh=round(flex_consumed_kw * slot_duration_h, 4),
                        grid_export_kwh=round(grid_export_kwh, 4),
                        export_revenue_sek=round(export_revenue, 4),
                    ))
                    continue

            # --- Idle (but may still have solar charging / export) ---
            action = "solar_charge" if solar_charge_kwh > 0.001 else "idle"
            result.slots.append(SlotResult(
                date=row["date"], hour=row["hour"],
                sek_per_kwh=float(row["sek_per_kwh"]),
                grid_fee_ore=round(grid_ore, 2),
                total_cost_ore=round(total_ore, 2),
                action=action,
                power_kw=solar_charge_kwh / slot_duration_h if solar_charge_kwh > 0 else 0.0,
                energy_kwh=round(solar_charge_kwh, 4),
                soc_before=round(soc_before, 4),
                soc_after=round(soc, 4),
                cost_sek=0.0,
                saving_sek=0.0,
                solar_kw=round(solar_kw, 4),
                solar_charge_kwh=round(solar_charge_kwh, 4),
                flex_consumed_kwh=round(flex_consumed_kw * slot_duration_h, 4),
                grid_export_kwh=round(grid_export_kwh, 4),
                export_revenue_sek=round(export_revenue, 4),
            ))

    return result


def _detect_slot_duration(prices: list[dict]) -> float:
    """Detect if data is 15-min or 60-min resolution."""
    if len(prices) < 2:
        return 1.0
    hours_seen = set()
    for row in prices:
        if row["date"] == prices[0]["date"]:
            hours_seen.add(row["hour"])
    if len(hours_seen) > 24:
        return 0.25
    return 1.0


def print_summary(result: SimResult, tariff=None, base_fuse_amps: float | None = None, solar=None):
    """Print a human-readable summary of the simulation."""
    c = result.config
    print("\n" + "=" * 70)
    print("  BATTERISIMULERING — RESULTAT")
    print("=" * 70)
    print(f"  Batteri:          {c.capacity_kwh} kWh (användbart: {c.usable_kwh:.1f} kWh)")
    print(f"  Laddning max:     {c.max_charge_kw} kW / Urladdning max: {c.max_discharge_kw} kW")
    print(f"  Verkningsgrad:    {c.efficiency*100:.0f}% (tur-retur)")
    print(f"  Säkring:          {c.fuse_amps}A / {c.phases}-fas → {c.grid_max_kw:.1f} kW max från nät")
    if c.seasonal_load_profile is not None:
        all_loads = [kw for m in c.seasonal_load_profile.values() for kw in m.values()]
        avg_load = sum(all_loads) / len(all_loads) if all_loads else 0
        print(f"  Förbrukningsprofil: Tibber (säsongsanpassad)")
        print(f"  Last:             {min(all_loads):.1f}–{max(all_loads):.1f} kW (medel: {avg_load:.1f} kW)")
    elif c.hourly_load_profile is not None:
        avg_load = sum(c.hourly_load_profile.values()) / 24
        max_load = max(c.hourly_load_profile.values())
        min_load = min(c.hourly_load_profile.values())
        print(f"  Förbrukningsprofil: Tibber (verklig)")
        print(f"  Last:             {min_load:.1f}–{max_load:.1f} kW (medel: {avg_load:.1f} kW)")
    else:
        print(f"  Grundförbrukning: {c.base_load_kw} kW (alltid)")
        if c.scheduled_loads:
            for load in c.scheduled_loads:
                if load.start_hour <= load.end_hour:
                    time_str = f"{load.start_hour:02d}-{load.end_hour:02d}"
                else:
                    time_str = f"{load.start_hour:02d}-{load.end_hour:02d} (över midnatt)"
                print(f"  Schemalagd last:  {load.name}: {load.power_kw} kW, kl {time_str}")
    min_avail = min(c.available_charge_kw(h) for h in range(24))
    max_avail = max(c.available_charge_kw(h) for h in range(24))
    if min_avail == max_avail:
        print(f"  Laddkapacitet:    {max_avail:.1f} kW")
    else:
        print(f"  Laddkapacitet:    {min_avail:.1f}–{max_avail:.1f} kW (beroende på tid)")
    if c.flexible_loads:
        for fl in c.flexible_loads:
            months_str = ""
            if fl.start_month != 1 or fl.end_month != 12:
                m_names = ["", "jan", "feb", "mar", "apr", "maj", "jun",
                           "jul", "aug", "sep", "okt", "nov", "dec"]
                months_str = f", {m_names[fl.start_month]}-{m_names[fl.end_month]}"
            daily_str = f", max {fl.daily_kwh:.0f} kWh/dag" if fl.daily_kwh > 0 else ""
            print(f"  Flexibel last:    {fl.name}: {fl.power_kw} kW, kl {fl.min_hour:02d}-{fl.max_hour:02d}{months_str}{daily_str}")
    # Fuse warnings
    fuse_warnings = c.fuse_analysis()
    errors = [w for w in fuse_warnings if w["severity"] == "error"]
    no_charge = [w for w in fuse_warnings if w["severity"] == "warning"]
    limited = [w for w in fuse_warnings if w["severity"] == "info"]

    if errors:
        print()
        print("  *** VARNING: SÄKRINGEN ÄR FÖR LITEN ***")
        for w in errors[:5]:
            print(f"  !!! {w['msg']}")
        if len(errors) > 5:
            print(f"  !!! ... och {len(errors)-5} fler överbelastningstillfällen")
        print()

    if no_charge:
        unique_hours = sorted(set(w["hour"] for w in no_charge))
        print(f"  OBS: Ingen batteriladdning möjlig kl {', '.join(f'{h:02d}' for h in unique_hours)}")
        print(f"       (hushållslasten använder all säkringskapacitet)")

    if limited and not errors and not no_charge:
        unique_hours = sorted(set(w["hour"] for w in limited))
        print(f"  OBS: Begränsad laddning kl {', '.join(f'{h:02d}' for h in unique_hours)}")

    if solar:
        from solar import print_solar_info
        print_solar_info(solar)
    print(f"  Nätavgiftsmodell: {result.tariff_name}")

    # Fuse fee info
    monthly_fee = tariff.monthly_fee if tariff and hasattr(tariff, "monthly_fee") else 0
    if monthly_fee > 0:
        print(f"  Abonnemang:       {monthly_fee:.2f} kr/mån ({c.fuse_amps:.0f}A)")

    # If upgrading from a smaller fuse, show the incremental cost
    upgrade_monthly = 0
    if base_fuse_amps is not None and tariff and base_fuse_amps != c.fuse_amps:
        from tariff import get_fuse_fee_monthly
        base_fee = get_fuse_fee_monthly(base_fuse_amps)
        upgrade_monthly = monthly_fee - base_fee
        print(f"  Nuvarande säkring:{base_fuse_amps:.0f}A ({base_fee:.2f} kr/mån)")
        print(f"  Merkostnad uppgr: {upgrade_monthly:.2f} kr/mån ({upgrade_monthly*12:.0f} kr/år)")

    print("-" * 70)

    days = set()
    for s in result.slots:
        days.add(s.date)
    num_days = len(days)
    num_months = num_days / 30.44

    print(f"  Period:           {num_days} dagar ({num_months:.1f} månader)")
    print(f"  Laddat totalt:    {result.total_charged_kwh:.1f} kWh")
    print(f"  Urladdat totalt:  {result.total_discharged_kwh:.1f} kWh")
    print(f"  Antal cykler:     {result.num_cycles:.1f}")
    if result.total_solar_charge_kwh > 0:
        print(f"  Solladdat:        {result.total_solar_charge_kwh:.1f} kWh (gratis)")
    if result.total_flex_consumed_kwh > 0:
        print(f"  Flex-förbrukning: {result.total_flex_consumed_kwh:.1f} kWh (solöverskott → pool etc.)")
    if result.total_grid_export_kwh > 0:
        print(f"  Sålt till nät:    {result.total_grid_export_kwh:.1f} kWh → {result.total_export_revenue:.0f} SEK")
    print(f"  Laddkostnad:      {result.total_charge_cost:.2f} SEK (spot + nätavgift)")
    print(f"  Urladdningsvärde: {result.total_discharge_value:.2f} SEK (undvikt spot + nätavgift)")
    print("-" * 70)

    arbitrage_profit = result.net_profit_sek
    print(f"  Arbitragevinst:   {arbitrage_profit:.2f} SEK")

    if upgrade_monthly > 0:
        total_upgrade_cost = upgrade_monthly * num_months
        net = arbitrage_profit - total_upgrade_cost
        print(f"  Merkostnad säkringsuppgradering: -{total_upgrade_cost:.0f} SEK")
        print(f"  NETTO (efter uppgradering): {net:.2f} SEK")
    else:
        net = arbitrage_profit
        print(f"  NETTORESULTAT:    {net:.2f} SEK")

    if num_days > 0:
        per_day = net / num_days
        per_month = per_day * 30.44
        per_year = per_day * 365.25
        print(f"  Per dag:          {per_day:.2f} SEK")
        print(f"  Per månad:        {per_month:.0f} SEK")
        print(f"  Uppskattning/år:  {per_year:.0f} SEK")

    # --- ROI / Payback ---
    bat_investment = c.purchase_price + c.installation_cost
    solar_investment = 0
    if solar:
        solar_investment = solar.purchase_price + solar.installation_cost

    total_investment = bat_investment + solar_investment

    if total_investment > 0 and num_days > 0:
        print()
        print("=" * 70)
        print("  INVESTERINGSKALKYL")
        print("=" * 70)

        if bat_investment > 0:
            print(f"  Batteri:")
            print(f"    Inköp:          {c.purchase_price:,.0f} SEK")
            if c.installation_cost > 0:
                print(f"    Installation:   {c.installation_cost:,.0f} SEK")
            print(f"    Delsumma:       {bat_investment:,.0f} SEK")

        if solar_investment > 0:
            print(f"  Solceller:")
            print(f"    Inköp:          {solar.purchase_price:,.0f} SEK")
            if solar.installation_cost > 0:
                print(f"    Installation:   {solar.installation_cost:,.0f} SEK")
            print(f"    Delsumma:       {solar_investment:,.0f} SEK")

        print(f"  Total investering:{total_investment:,.0f} SEK")
        print("-" * 70)

        # Battery lifetime
        cycles_per_year = result.num_cycles / (num_days / 365.25) if num_days > 0 else 0
        if cycles_per_year > 0:
            cycle_lifetime_years = c.cycle_life / cycles_per_year
        else:
            cycle_lifetime_years = c.calendar_life_years
        bat_lifetime = min(cycle_lifetime_years, c.calendar_life_years)

        print(f"  Batteri:")
        print(f"    Cykler/år:      {cycles_per_year:.0f}")
        print(f"    Cykellivslängd: {c.cycle_life} cykler → {cycle_lifetime_years:.1f} år")
        print(f"    Livslängd:      {bat_lifetime:.1f} år")

        if solar:
            from solar import estimate_lifetime_production
            lifetime_kwh = estimate_lifetime_production(solar)
            yearly_kwh = lifetime_kwh / solar.lifetime_years
            print(f"  Solceller:")
            print(f"    Livslängd:      {solar.lifetime_years} år")
            print(f"    Degradering:    {solar.degradation_per_year*100:.1f}%/år")
            print(f"    Totalproduktion:{lifetime_kwh:,.0f} kWh över {solar.lifetime_years} år")
            if solar_investment > 0:
                solar_cost_per_kwh = solar_investment / lifetime_kwh
                print(f"    Kostnad/kWh:    {solar_cost_per_kwh*100:.1f} öre/kWh (sol-avskrivning)")

        print("-" * 70)

        # Use shorter lifetime for combined payback
        effective_lifetime = bat_lifetime
        if solar:
            effective_lifetime = min(bat_lifetime, solar.lifetime_years)

        # Payback
        if per_year > 0:
            payback_years = total_investment / per_year
            print(f"  Återbetalningstid: {payback_years:.1f} år")
            if payback_years <= effective_lifetime:
                print(f"  ✓ Återbetald inom livslängden")
            else:
                print(f"  ✗ Återbetalas EJ inom livslängden ({payback_years:.1f} > {effective_lifetime:.1f} år)")
        else:
            payback_years = float("inf")
            print(f"  Återbetalningstid: Aldrig (nettoresultat <= 0)")

        # Total profit over lifetime
        total_lifetime_profit = per_year * effective_lifetime - total_investment
        print(f"  Total vinst under livslängd: {total_lifetime_profit:,.0f} SEK")

        # ROI
        roi = (total_lifetime_profit / total_investment) * 100
        print(f"  ROI:              {roi:.1f}%")

        # Cost per kWh cycled (battery only)
        if bat_investment > 0:
            total_kwh_lifetime = result.total_discharged_kwh / num_days * 365.25 * bat_lifetime
            if total_kwh_lifetime > 0:
                cost_per_kwh = bat_investment / total_kwh_lifetime
                print(f"  Batteri öre/kWh:  {cost_per_kwh*100:.1f} öre/kWh (batteri-avskrivning)")

    print("=" * 70)


def print_daily_breakdown(result: SimResult):
    """Print per-day summary."""
    days: dict[str, list[SlotResult]] = {}
    for s in result.slots:
        days.setdefault(s.date, []).append(s)

    print(f"\n{'Datum':<12} {'Laddat':>10} {'Urladdat':>10} {'Kostnad':>10} {'Värde':>10} {'Vinst':>10}")
    print("-" * 65)
    for d in sorted(days.keys()):
        slots = days[d]
        charged = sum(s.energy_kwh for s in slots if s.action == "charge")
        discharged = sum(s.energy_kwh for s in slots if s.action == "discharge")
        cost = sum(s.cost_sek for s in slots if s.action == "charge")
        value = sum(s.saving_sek for s in slots if s.action == "discharge")
        profit = value - cost
        print(f"{d:<12} {charged:>8.2f}kWh {discharged:>8.2f}kWh {cost:>9.2f}kr {value:>9.2f}kr {profit:>9.2f}kr")
