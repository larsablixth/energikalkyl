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
