"""
Grid tariff models for Vattenfall Eldistribution 2026.

Two pricing models:
1. Tidstariff — higher transfer fee during peak hours (höglasttid)
2. Enkeltariff — same transfer fee all hours

Höglasttid (peak): Weekdays 06-22, months Jan, Feb, Mar, Nov, Dec.
Weekdays that are public holidays are NOT peak:
  nyårsdagen, trettondedag jul, långfredag, annandag påsk,
  julafton, juldagen, annandag jul, nyårsafton.

All other times are off-peak (övrig tid).

All prices include 25% VAT.
"""

from dataclasses import dataclass
from datetime import date

# Swedish public holidays that fall on weekdays and count as off-peak
# Returns set of (month, day) for fixed holidays; Easter varies by year.
def _swedish_holidays(year: int) -> set[date]:
    """Return Swedish public holidays relevant for tariff peak classification."""
    from datetime import timedelta
    holidays = {
        date(year, 1, 1),    # nyårsdagen
        date(year, 1, 6),    # trettondedag jul
        date(year, 12, 24),  # julafton
        date(year, 12, 25),  # juldagen
        date(year, 12, 26),  # annandag jul
        date(year, 12, 31),  # nyårsafton
    }
    # Easter calculation (Anonymous Gregorian algorithm)
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    easter = date(year, month, day)
    holidays.add(easter - timedelta(days=2))  # långfredag
    holidays.add(easter + timedelta(days=1))  # annandag påsk
    return holidays


def is_peak_hour(d: str, hour: str) -> bool:
    """Check if a given date+hour is höglasttid (peak)."""
    dt = date.fromisoformat(d)
    month = dt.month
    weekday = dt.weekday()  # 0=Monday, 6=Sunday
    h = int(hour.split(":")[0])

    # Peak months: Jan, Feb, Mar, Nov, Dec
    if month not in (1, 2, 3, 11, 12):
        return False

    # Must be weekday (mon-fri)
    if weekday >= 5:
        return False

    # Must be 06-22
    if not (6 <= h < 22):
        return False

    # Check if it's a public holiday
    if dt in _swedish_holidays(dt.year):
        return False

    return True


# Yearly fixed fee per fuse size (kr/år, inkl. moms, Vattenfall Eldistribution 2026)
FUSE_YEARLY_FEE: dict[float, float] = {
    16: 5775,
    20: 8085,
    25: 10125,
    35: 13890,
    50: 19945,
    63: 26875,
}


def get_fuse_fee_monthly(fuse_amps: float) -> float:
    """Get monthly fee for a fuse size. Returns 0 if unknown."""
    yearly = FUSE_YEARLY_FEE.get(fuse_amps, 0.0)
    return yearly / 12

def get_fuse_fee_yearly(fuse_amps: float) -> float:
    """Get yearly fee for a fuse size. Returns 0 if unknown."""
    return FUSE_YEARLY_FEE.get(fuse_amps, 0.0)


@dataclass
class Tidstariff:
    """Vattenfall Tidstariff 2026: two rates based on peak/off-peak."""
    # Överföringsavgift (öre/kWh, inkl. moms)
    peak: float = 76.50       # höglasttid: vinter vardag 06-22
    offpeak: float = 30.50    # övrig tid
    # Energiskatt (öre/kWh, inkl. moms)
    energy_tax: float = 54.88  # 2026: 43.90 öre × 1.25
    # Abonnemangsavgift
    fuse_amps: float = 25.0
    monthly_fee: float | None = None
    name: str = "Vattenfall Tidstariff 2026"

    def __post_init__(self):
        if self.monthly_fee is None:
            self.monthly_fee = get_fuse_fee_monthly(self.fuse_amps)

    def total_cost_ore(self, d: str, hour: str) -> float:
        """Total grid cost in öre/kWh for a given date and hour."""
        return self.transfer_fee_ore(d, hour) + self.energy_tax

    def transfer_fee_ore(self, d: str, hour: str) -> float:
        """Transfer fee only in öre/kWh."""
        return self.peak if is_peak_hour(d, hour) else self.offpeak


@dataclass
class FastTariff:
    """Vattenfall Enkeltariff 2026: same rate all hours."""
    # Överföringsavgift (öre/kWh, inkl. moms)
    flat_rate: float = 44.50
    # Energiskatt (öre/kWh, inkl. moms)
    energy_tax: float = 54.88
    # Abonnemangsavgift
    fuse_amps: float = 25.0
    monthly_fee: float | None = None
    name: str = "Vattenfall Enkeltariff 2026"

    def __post_init__(self):
        if self.monthly_fee is None:
            self.monthly_fee = get_fuse_fee_monthly(self.fuse_amps)

    def total_cost_ore(self, d: str, hour: str) -> float:
        """Total grid cost in öre/kWh for a given date and hour."""
        return self.flat_rate + self.energy_tax

    def transfer_fee_ore(self, d: str, hour: str) -> float:
        return self.flat_rate


@dataclass
class EffektTariff:
    """Power demand tariff (effekttariff) — charges based on peak kW demand.

    Monthly cost = fixed_fee + energy_rate × kWh + effekt_rate × peak_kW
    Peak kW = average of top N hourly peaks from different days during peak hours.
    """
    # Energy component (öre/kWh, inkl. moms) — much lower than tidstariff
    energy_rate: float = 7.0
    # Energiskatt (öre/kWh, inkl. moms)
    energy_tax: float = 54.88
    # Effektavgift (kr/kW/månad, inkl. moms)
    effekt_rate: float = 81.25
    # How many top peaks to average
    top_n_peaks: int = 3
    # Night discount (22-06): kW counted at this fraction
    night_discount: float = 0.5
    # Peak hours restriction (None = all hours like Ellevio)
    peak_months: tuple | None = None  # e.g. (1,2,3,11,12) for winter only
    peak_weekday_only: bool = False
    peak_hour_start: int = 0
    peak_hour_end: int = 24
    # Fixed fee
    fuse_amps: float = 25.0
    monthly_fee: float = 395.0  # Ellevio default for 16-25A
    name: str = "Effekttariff"

    def total_cost_ore(self, d: str, hour: str) -> float:
        """Energy cost component in öre/kWh (excludes the demand charge)."""
        return self.energy_rate + self.energy_tax

    def transfer_fee_ore(self, d: str, hour: str) -> float:
        return self.energy_rate

    def is_peak_hour(self, d: str, hour: str) -> bool:
        """Check if this hour counts toward peak demand measurement."""
        dt = date.fromisoformat(d)
        h = int(hour.split(":")[0])
        if self.peak_months and dt.month not in self.peak_months:
            return False
        if self.peak_weekday_only and dt.weekday() >= 5:
            return False
        if self.peak_weekday_only and dt in _swedish_holidays(dt.year):
            return False
        if not (self.peak_hour_start <= h < self.peak_hour_end):
            return False
        return True

    def kw_factor(self, d: str, hour: str) -> float:
        """How much a kW in this hour counts toward peak (1.0 or night_discount)."""
        h = int(hour.split(":")[0])
        if 22 <= h or h < 6:
            return self.night_discount
        return 1.0

    def monthly_demand_cost(self, peak_kw: float) -> float:
        """Monthly effektavgift given the measured peak kW."""
        return self.effekt_rate * peak_kw


# === Grid operator presets ===

GRID_OPERATORS = {
    "Vattenfall Eldistribution": {
        "tariffs": ["Tidstariff", "Enkeltariff"],
        "fuse_fees": {16: 5775, 20: 8085, 25: 10125, 35: 13890, 50: 19945, 63: 26875},
        "tidstariff": {"peak": 76.5, "offpeak": 30.5},
        "enkeltariff": {"flat_rate": 44.5},
        "effekttariff": None,  # not yet for private ≤63A
    },
    "Ellevio": {
        "tariffs": ["Effekttariff"],
        "fuse_fees": {16: 4740, 25: 4740, 35: 11880, 50: 18180, 63: 26100},
        "effekttariff": {
            "energy_rate": 7.0,
            "effekt_rate": 81.25,
            "top_n_peaks": 3,
            "night_discount": 0.5,
            "peak_months": None,  # all year
            "peak_weekday_only": False,
            "peak_hour_start": 0,
            "peak_hour_end": 24,
        },
    },
    "E.ON Energidistribution": {
        "tariffs": ["Tidstariff", "Enkeltariff"],
        "fuse_fees": {16: 4500, 20: 5700, 25: 7500, 35: 10200, 50: 15600, 63: 21000},
        "tidstariff": {"peak": 67.0, "offpeak": 22.5},
        "enkeltariff": {"flat_rate": 39.0},
        "effekttariff": None,
    },
    "Göteborg Energi": {
        "tariffs": ["Effekttariff", "Enkeltariff"],
        "fuse_fees": {16: 3900, 20: 5100, 25: 6600, 35: 9000, 50: 13200, 63: 18000},
        "effekttariff": {
            "energy_rate": 6.5,
            "effekt_rate": 135.0,
            "top_n_peaks": 3,
            "night_discount": 1.0,  # no night discount
            "peak_months": (11, 12, 1, 2, 3),
            "peak_weekday_only": True,
            "peak_hour_start": 7,
            "peak_hour_end": 20,
        },
        "enkeltariff": {"flat_rate": 23.0},
    },
    "Mälarenergi": {
        "tariffs": ["Effekttariff"],
        "fuse_fees": {16: 3600, 20: 4800, 25: 6000, 35: 8400, 50: 12000, 63: 16800},
        "effekttariff": {
            "energy_rate": 21.5,  # 17.2 × 1.25
            "effekt_rate": 59.25,  # 47.4 × 1.25
            "top_n_peaks": 1,  # single highest
            "night_discount": 1.0,
            "peak_months": None,
            "peak_weekday_only": True,
            "peak_hour_start": 7,
            "peak_hour_end": 19,
        },
    },
    "Jämtkraft (Jämtland)": {
        "tariffs": ["Enkeltariff"],
        "fuse_fees": {16: 5700, 20: 9340, 25: 11880, 35: 16940, 50: 24290, 63: 31380},
        "enkeltariff": {"flat_rate": 7.5},
        "effekttariff": None,
    },
    "SEOM (Sollentuna)": {
        "tariffs": ["Effekttariff"],
        # Flat grundavgift — 16-25A same tier, then steps up
        "fuse_fees": {16: 1780, 20: 1780, 25: 1780, 35: 3175, 50: 4475, 63: 5445},
        "effekttariff": {
            "energy_rate": 5.0,   # 5 öre/kWh inkl. moms
            "effekt_rate": 145.0,  # höglast Nov-Mar (72.5 låglast Apr-Okt)
            "top_n_peaks": 3,
            "night_discount": 1.0,  # no night discount — only weekday 07-19
            "peak_months": (11, 12, 1, 2, 3),
            "peak_weekday_only": True,
            "peak_hour_start": 7,
            "peak_hour_end": 19,
        },
    },
    "Anpassad": {
        "tariffs": ["Tidstariff", "Enkeltariff", "Effekttariff"],
        "fuse_fees": FUSE_YEARLY_FEE,
        "tidstariff": {"peak": 76.5, "offpeak": 30.5},
        "enkeltariff": {"flat_rate": 44.5},
        "effekttariff": {
            "energy_rate": 7.0,
            "effekt_rate": 81.25,
            "top_n_peaks": 3,
            "night_discount": 0.5,
            "peak_months": None,
            "peak_weekday_only": False,
            "peak_hour_start": 0,
            "peak_hour_end": 24,
        },
    },
}


def get_operator_fuse_fees(operator: str) -> dict[float, float]:
    """Get fuse fees for a grid operator."""
    op = GRID_OPERATORS.get(operator)
    if op:
        return op.get("fuse_fees", FUSE_YEARLY_FEE)
    return FUSE_YEARLY_FEE


def create_tariffs_for_operator(operator: str, fuse_amps: float = 25.0,
                                 energy_tax: float = 54.88) -> list:
    """Create tariff objects for a grid operator."""
    op = GRID_OPERATORS.get(operator, GRID_OPERATORS["Anpassad"])
    tariffs = []
    fees = op.get("fuse_fees", FUSE_YEARLY_FEE)
    monthly_fee = fees.get(fuse_amps, 0) / 12

    if "Tidstariff" in op["tariffs"] and "tidstariff" in op:
        t = op["tidstariff"]
        tariffs.append(Tidstariff(
            peak=t["peak"], offpeak=t["offpeak"], energy_tax=energy_tax,
            fuse_amps=fuse_amps, monthly_fee=monthly_fee,
            name=f"{operator} Tidstariff",
        ))

    if "Enkeltariff" in op["tariffs"] and "enkeltariff" in op:
        t = op["enkeltariff"]
        tariffs.append(FastTariff(
            flat_rate=t["flat_rate"], energy_tax=energy_tax,
            fuse_amps=fuse_amps, monthly_fee=monthly_fee,
            name=f"{operator} Enkeltariff",
        ))

    if "Effekttariff" in op["tariffs"] and op.get("effekttariff"):
        t = op["effekttariff"]
        tariffs.append(EffektTariff(
            energy_rate=t["energy_rate"], energy_tax=energy_tax,
            effekt_rate=t["effekt_rate"], top_n_peaks=t["top_n_peaks"],
            night_discount=t["night_discount"],
            peak_months=t.get("peak_months"),
            peak_weekday_only=t.get("peak_weekday_only", False),
            peak_hour_start=t.get("peak_hour_start", 0),
            peak_hour_end=t.get("peak_hour_end", 24),
            fuse_amps=fuse_amps, monthly_fee=monthly_fee,
            name=f"{operator} Effekttariff",
        ))

    return tariffs


def print_tariff_info(tariff):
    """Print tariff details."""
    print(f"\n  Nätavgiftsmodell:  {tariff.name}")
    if isinstance(tariff, Tidstariff):
        print(f"  Höglasttid (vinter vardag 06-22):       {tariff.peak:.2f} öre/kWh")
        print(f"  Övrig tid:                              {tariff.offpeak:.2f} öre/kWh")
    elif isinstance(tariff, FastTariff):
        print(f"  Överföringsavgift (alla timmar):        {tariff.flat_rate:.2f} öre/kWh")
    print(f"  Energiskatt (inkl. moms):               {tariff.energy_tax:.2f} öre/kWh")
    print(f"  Säkring:           {tariff.fuse_amps:.0f}A")
    print(f"  Abonnemang:        {tariff.monthly_fee:.2f} kr/mån ({get_fuse_fee_yearly(tariff.fuse_amps):.0f} kr/år)")


def print_fuse_comparison():
    """Print a comparison of all fuse sizes and their fees."""
    print(f"\n  Abonnemangsavgifter — Vattenfall Eldistribution 2026:")
    print(f"  {'Säkring':>10} {'Kr/mån':>10} {'Kr/år':>10}")
    print(f"  {'-'*32}")
    for amps in sorted(FUSE_YEARLY_FEE.keys()):
        yearly = FUSE_YEARLY_FEE[amps]
        print(f"  {amps:>8.0f}A {yearly/12:>10.2f} {yearly:>10.0f}")
