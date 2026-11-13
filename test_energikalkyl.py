import os
"""
Test suite for Energikalkyl — core modules.

Tests cover:
- tariff.py: peak hour detection, holiday handling, tariff calculations, grid operators
- heating.py: COP models, heating demand, air-to-air, cooling
- solar.py: production model, hourly factors, real data fallback, scaling
- batteri.py: LoadSchedule, FlexibleLoad, BatteryConfig, simulate()

Run: python -m pytest test_energikalkyl.py -v
"""

import math
import pytest
from datetime import date


# ============================================================
# tariff.py tests
# ============================================================

class TestSwedishHolidays:
    def test_fixed_holidays_present(self):
        from tariff import _swedish_holidays
        holidays = _swedish_holidays(2026)
        assert date(2026, 1, 1) in holidays   # nyårsdagen
        assert date(2026, 1, 6) in holidays   # trettondedag jul
        assert date(2026, 12, 24) in holidays # julafton
        assert date(2026, 12, 25) in holidays # juldagen
        assert date(2026, 12, 26) in holidays # annandag jul
        assert date(2026, 12, 31) in holidays # nyårsafton

    def test_easter_2026(self):
        """Easter 2026 is April 5."""
        from tariff import _swedish_holidays
        holidays = _swedish_holidays(2026)
        assert date(2026, 4, 3) in holidays   # långfredag
        assert date(2026, 4, 6) in holidays   # annandag påsk

    def test_easter_2025(self):
        """Easter 2025 is April 20."""
        from tariff import _swedish_holidays
        holidays = _swedish_holidays(2025)
        assert date(2025, 4, 18) in holidays  # långfredag
        assert date(2025, 4, 21) in holidays  # annandag påsk


class TestIsPeakHour:
    def test_winter_weekday_daytime_is_peak(self):
        from tariff import is_peak_hour
        # 2026-01-05 is Monday, January
        assert is_peak_hour("2026-01-05", "10:00") is True
        assert is_peak_hour("2026-01-05", "06:00") is True
        assert is_peak_hour("2026-01-05", "21:00") is True

    def test_winter_weekday_night_is_not_peak(self):
        from tariff import is_peak_hour
        assert is_peak_hour("2026-01-05", "05:00") is False
        assert is_peak_hour("2026-01-05", "22:00") is False

    def test_summer_is_not_peak(self):
        from tariff import is_peak_hour
        # June, Wednesday
        assert is_peak_hour("2026-06-03", "12:00") is False

    def test_weekend_is_not_peak(self):
        from tariff import is_peak_hour
        # 2026-01-03 is Saturday
        assert is_peak_hour("2026-01-03", "12:00") is False

    def test_holiday_is_not_peak(self):
        from tariff import is_peak_hour
        # New Year's Day 2026 is Thursday
        assert is_peak_hour("2026-01-01", "12:00") is False

    def test_april_is_not_peak(self):
        from tariff import is_peak_hour
        assert is_peak_hour("2026-04-07", "12:00") is False


class TestTidstariff:
    def test_peak_cost(self):
        from tariff import Tidstariff
        t = Tidstariff()
        cost = t.total_cost_ore("2026-01-05", "10:00")
        assert cost == 76.5 + 45.0

    def test_offpeak_cost(self):
        from tariff import Tidstariff
        t = Tidstariff()
        cost = t.total_cost_ore("2026-01-05", "02:00")
        assert cost == 30.5 + 45.0

    def test_transfer_fee_peak(self):
        from tariff import Tidstariff
        t = Tidstariff()
        assert t.transfer_fee_ore("2026-01-05", "10:00") == 76.5

    def test_transfer_fee_offpeak(self):
        from tariff import Tidstariff
        t = Tidstariff()
        assert t.transfer_fee_ore("2026-01-05", "02:00") == 30.5


class TestFastTariff:
    def test_flat_rate_all_hours(self):
        from tariff import FastTariff
        t = FastTariff()
        # Same cost peak and off-peak
        assert t.total_cost_ore("2026-01-05", "10:00") == t.total_cost_ore("2026-07-15", "03:00")
        assert t.total_cost_ore("2026-01-05", "10:00") == 44.5 + 45.0


class TestEffektTariff:
    def test_energy_cost(self):
        from tariff import EffektTariff
        t = EffektTariff()
        assert t.total_cost_ore("2026-01-05", "10:00") == 7.0 + 45.0

    def test_kw_factor_night(self):
        from tariff import EffektTariff
        t = EffektTariff(night_discount=0.5)
        assert t.kw_factor("2026-01-05", "23:00") == 0.5
        assert t.kw_factor("2026-01-05", "03:00") == 0.5

    def test_kw_factor_day(self):
        from tariff import EffektTariff
        t = EffektTariff(night_discount=0.5)
        assert t.kw_factor("2026-01-05", "12:00") == 1.0

    def test_seasonal_effekt_rate(self):
        from tariff import EffektTariff
        t = EffektTariff(
            effekt_rate=145.0,
            low_season_rate=72.5,
            peak_months=(11, 12, 1, 2, 3),
        )
        assert t.get_effekt_rate(1) == 145.0   # winter
        assert t.get_effekt_rate(7) == 72.5     # summer

    def test_monthly_demand_cost(self):
        from tariff import EffektTariff
        t = EffektTariff(effekt_rate=81.25)
        assert t.monthly_demand_cost(10.0) == 812.5


class TestFuseFees:
    def test_known_fuse_sizes(self):
        from tariff import get_fuse_fee_yearly, get_fuse_fee_monthly
        assert get_fuse_fee_yearly(25) == 10125
        assert abs(get_fuse_fee_monthly(25) - 10125 / 12) < 0.01

    def test_unknown_fuse_returns_zero(self):
        from tariff import get_fuse_fee_yearly
        assert get_fuse_fee_yearly(100) == 0


class TestGridOperators:
    def test_all_operators_present(self):
        from tariff import GRID_OPERATORS
        expected = [
            "Vattenfall Eldistribution", "Ellevio", "E.ON Energidistribution",
            "Göteborg Energi", "Mälarenergi", "Jämtkraft (Jämtland)",
            "SEOM (Sollentuna)", "Anpassad",
        ]
        for op in expected:
            assert op in GRID_OPERATORS

    def test_create_tariffs_vattenfall(self):
        from tariff import create_tariffs_for_operator, Tidstariff, FastTariff
        tariffs = create_tariffs_for_operator("Vattenfall Eldistribution", 25)
        assert len(tariffs) == 2
        types = {type(t) for t in tariffs}
        assert Tidstariff in types
        assert FastTariff in types

    def test_create_tariffs_ellevio(self):
        from tariff import create_tariffs_for_operator, EffektTariff
        tariffs = create_tariffs_for_operator("Ellevio", 25)
        assert len(tariffs) == 1
        assert isinstance(tariffs[0], EffektTariff)

    def test_create_tariffs_seom(self):
        from tariff import create_tariffs_for_operator, EffektTariff
        tariffs = create_tariffs_for_operator("SEOM (Sollentuna)", 25)
        assert len(tariffs) == 1
        t = tariffs[0]
        assert isinstance(t, EffektTariff)
        assert t.effekt_rate == 145.0
        assert t.low_season_rate == 72.5


# ============================================================
# heating.py tests
# ============================================================

class TestHeatingModel:
    def test_heating_demand_at_zero(self):
        from heating import heating_demand_kw, HeatingConfig
        config = HeatingConfig(h_loss=0.160, t_indoor=21.0)
        demand = heating_demand_kw(0.0, config)
        assert abs(demand - 0.160 * 21) < 0.001

    def test_heating_demand_above_indoor(self):
        from heating import heating_demand_kw, HeatingConfig
        config = HeatingConfig()
        assert heating_demand_kw(25.0, config) == 0.0

    def test_cop_ground_source(self):
        from heating import cop_ground_source, HeatingConfig
        config = HeatingConfig(cop_base=3.4, cop_slope=0.056)
        cop = cop_ground_source(0.0, config)
        assert cop == 3.4
        cop_10 = cop_ground_source(10.0, config)
        assert abs(cop_10 - (3.4 + 0.056 * 10)) < 0.001

    def test_cop_minimum(self):
        from heating import cop_ground_source, HeatingConfig
        config = HeatingConfig(cop_base=3.4, cop_slope=0.056, cop_min=1.0)
        cop = cop_ground_source(-100.0, config)
        assert cop == 1.0

    def test_heating_electricity_warm_day(self):
        from heating import heating_electricity_kw, HeatingConfig
        config = HeatingConfig(aa_enabled=False)
        elec = heating_electricity_kw(25.0, config)
        assert elec == 0.0

    def test_heating_electricity_cold_day(self):
        from heating import heating_electricity_kw, HeatingConfig
        config = HeatingConfig(h_loss=0.160, hp_max_heat_kw=6.0, aa_enabled=False)
        elec = heating_electricity_kw(-10.0, config)
        assert elec > 0

    def test_elpatron_kicks_in(self):
        from heating import heating_electricity_kw, HeatingConfig
        config = HeatingConfig(h_loss=0.5, hp_max_heat_kw=2.0, elpatron_kw=3.0, aa_enabled=False)
        # At -10°C: demand = 0.5 * 31 = 15.5 kW, HP can do 2 kW thermal
        elec = heating_electricity_kw(-10.0, config)
        assert elec > 2.0  # must include elpatron


class TestCooling:
    def test_no_cooling_without_aa(self):
        from heating import cooling_electricity_kw, HeatingConfig
        config = HeatingConfig(aa_enabled=False)
        assert cooling_electricity_kw(30.0, config) == 0.0

    def test_no_cooling_below_threshold(self):
        from heating import cooling_electricity_kw, HeatingConfig
        config = HeatingConfig(aa_enabled=True, aa_cool_threshold=24.0)
        assert cooling_electricity_kw(20.0, config) == 0.0

    def test_cooling_above_threshold(self):
        from heating import cooling_electricity_kw, HeatingConfig
        config = HeatingConfig(aa_enabled=True, aa_cool_threshold=24.0, aa_cop_cool=4.2)
        elec = cooling_electricity_kw(28.0, config)
        expected = min(config.aa_max_cool_kw, 0.1 * 4) / 4.2
        assert abs(elec - expected) < 0.001


class TestAirToAir:
    def test_cop_air_to_air(self):
        from heating import cop_air_to_air, HeatingConfig
        config = HeatingConfig()
        # At 7°C reference point
        cop = cop_air_to_air(7.0, config)
        assert abs(cop - config.aa_cop_heat_base) < 0.001

    def test_aa_heating_reduces_primary(self):
        from heating import heating_electricity_kw, HeatingConfig
        config_no_aa = HeatingConfig(h_loss=0.160, aa_enabled=False)
        config_aa = HeatingConfig(h_loss=0.160, aa_enabled=True)
        # At 5°C (above aa_min_temp=1°C), AA should help
        elec_no_aa = heating_electricity_kw(5.0, config_no_aa)
        elec_aa = heating_electricity_kw(5.0, config_aa)
        # With AA supplement, total electricity should be lower (higher effective COP)
        assert elec_aa < elec_no_aa


# ============================================================
# solar.py tests
# ============================================================

class TestSolarModel:
    def test_hourly_factors_sum_to_one(self):
        from solar import hourly_production_factors
        for month in range(1, 13):
            factors = hourly_production_factors(month)
            total = sum(factors.values())
            assert abs(total - 1.0) < 0.01, f"Month {month}: factors sum to {total}"

    def test_no_production_at_night(self):
        from solar import get_solar_production, SolarConfig
        config = SolarConfig(capacity_kwp=10.0)
        # Midnight in all months
        for month in range(1, 13):
            assert get_solar_production(month, 0, config) == 0.0

    def test_production_peaks_midday(self):
        from solar import get_solar_production, SolarConfig
        config = SolarConfig(capacity_kwp=10.0)
        # June: production at noon > morning
        noon = get_solar_production(6, 12, config)
        morning = get_solar_production(6, 7, config)
        assert noon > morning

    def test_summer_more_than_winter(self):
        from solar import get_solar_production, SolarConfig
        config = SolarConfig(capacity_kwp=10.0)
        june_noon = get_solar_production(6, 12, config)
        dec_noon = get_solar_production(12, 12, config)
        assert june_noon > dec_noon * 3

    def test_yearly_production_estimate(self):
        from solar import estimate_yearly_production, SolarConfig
        config = SolarConfig(capacity_kwp=10.0, performance_ratio=0.85)
        yearly = estimate_yearly_production(config)
        # Stockholm ~10 kWp should produce roughly 7,000-12,000 kWh/yr
        assert 5000 < yearly < 15000

    def test_lifetime_production_with_degradation(self):
        from solar import estimate_yearly_production, estimate_lifetime_production, SolarConfig
        config = SolarConfig(capacity_kwp=10.0, lifetime_years=25, degradation_per_year=0.005)
        yearly = estimate_yearly_production(config)
        lifetime = estimate_lifetime_production(config)
        # Should be less than yearly × 25 (due to degradation)
        assert lifetime < yearly * 25
        assert lifetime > yearly * 20  # but not too much less


class TestSolarRealData:
    def test_real_production_overrides_model(self):
        from solar import get_solar_for_slot, SolarConfig
        config = SolarConfig(
            capacity_kwp=10.0,
            real_production={"2026-06-15 12:00": 8.5}
        )
        result = get_solar_for_slot("2026-06-15", "12:00", config)
        assert result == 8.5

    def test_fallback_to_model_without_real(self):
        from solar import get_solar_for_slot, SolarConfig
        config = SolarConfig(capacity_kwp=10.0)
        result = get_solar_for_slot("2026-06-15", "12:00", config)
        assert result > 0

    def test_monthly_scaling(self):
        from solar import get_solar_for_slot, SolarConfig, MONTHLY_KWH_PER_KWP
        # Double the model's June production via real_monthly_kwh
        model_june = MONTHLY_KWH_PER_KWP[6] * 10.0 * 0.85
        config_model = SolarConfig(capacity_kwp=10.0)
        config_scaled = SolarConfig(
            capacity_kwp=10.0,
            real_monthly_kwh={6: model_june * 2}
        )
        model_val = get_solar_for_slot("2026-06-15", "12:00", config_model)
        scaled_val = get_solar_for_slot("2026-06-15", "12:00", config_scaled)
        assert abs(scaled_val - model_val * 2) < 0.01


# ============================================================
# batteri.py tests
# ============================================================

class TestLoadSchedule:
    def test_is_in_window_normal(self):
        from batteri import LoadSchedule
        ls = LoadSchedule("test", 11.0, 8, 16)
        assert ls.is_in_window(10) is True
        assert ls.is_in_window(7) is False
        assert ls.is_in_window(16) is False

    def test_is_in_window_wrapping(self):
        from batteri import LoadSchedule
        ls = LoadSchedule("EV", 11.0, 18, 7)
        assert ls.is_in_window(20) is True
        assert ls.is_in_window(3) is True
        assert ls.is_in_window(10) is False

    def test_smart_load_not_active_fixed(self):
        from batteri import LoadSchedule
        ls = LoadSchedule("EV", 11.0, 18, 7, daily_kwh=30, smart=True)
        assert ls.is_active(20) is False  # smart loads not active via is_active

    def test_hours_needed(self):
        from batteri import LoadSchedule
        ls = LoadSchedule("EV", 11.0, 18, 7, daily_kwh=30, smart=True)
        assert ls.hours_needed() == 3  # ceil(30/11) = 3


class TestFlexibleLoad:
    def test_availability_summer_only(self):
        from batteri import FlexibleLoad
        pool = FlexibleLoad("Pool", 3.0, start_month=5, end_month=9, min_hour=8, max_hour=20)
        assert pool.is_available(7, 12) is True
        assert pool.is_available(1, 12) is False
        assert pool.is_available(7, 22) is False

    def test_availability_year_round(self):
        from batteri import FlexibleLoad
        hw = FlexibleLoad("Varmvatten", 3.0, start_month=1, end_month=12)
        assert hw.is_available(1, 12) is True
        assert hw.is_available(7, 12) is True


class TestBatteryConfig:
    def test_grid_max_kw_3phase(self):
        from batteri import BatteryConfig
        config = BatteryConfig(fuse_amps=25, phases=3, voltage=230, phase_balance_factor=0.7)
        expected = 25 * 230 * 3 / 1000 * 0.7
        assert abs(config.grid_max_kw - expected) < 0.01

    def test_grid_max_kw_1phase(self):
        from batteri import BatteryConfig
        config = BatteryConfig(fuse_amps=25, phases=1, voltage=230)
        expected = 25 * 230 / 1000
        assert abs(config.grid_max_kw - expected) < 0.01

    def test_usable_kwh(self):
        from batteri import BatteryConfig
        config = BatteryConfig(capacity_kwh=32.0, min_soc=0.05, max_soc=0.95)
        assert abs(config.usable_kwh - 32.0 * 0.9) < 0.01

    def test_total_load_with_scheduled(self):
        from batteri import BatteryConfig, LoadSchedule
        ev = LoadSchedule("EV", 11.0, 23, 3, smart=False)
        config = BatteryConfig(base_load_kw=1.5, scheduled_loads=[ev])
        assert config.total_load_kw(0) == 12.5   # base + EV
        assert config.total_load_kw(12) == 1.5    # base only

    def test_available_charge_kw(self):
        from batteri import BatteryConfig
        config = BatteryConfig(
            fuse_amps=20, phases=3, voltage=230,
            base_load_kw=2.0, max_charge_kw=5.0,
            phase_balance_factor=1.0,
        )
        headroom = 20 * 230 * 3 / 1000 - 2.0
        expected = min(5.0, headroom)
        assert abs(config.available_charge_kw(12) - expected) < 0.01

    def test_daily_load_override(self):
        from batteri import BatteryConfig
        config = BatteryConfig(
            base_load_kw=1.5,
            daily_load_override={"2026-01-05": {10: 3.5, 14: 2.0}},
        )
        assert config.total_load_kw(10, 1, "2026-01-05") == 3.5
        assert config.total_load_kw(14, 1, "2026-01-05") == 2.0
        # Hour not in override falls back to base_load_kw
        assert config.total_load_kw(0, 1, "2026-01-05") == 1.5


class TestSimulate:
    """Integration tests for the simulate function."""

    def _make_prices(self, n_days=1, base_price=0.50):
        """Generate synthetic price data for testing."""
        prices = []
        for day in range(n_days):
            d = f"2026-01-{5+day:02d}"
            for hour in range(24):
                # Create a clear price spread: very cheap at night, very expensive during day
                # Needs >20 öre absolute spread after grid fees to trigger cycling
                if 1 <= hour <= 5:
                    price = base_price * 0.2  # very cheap (10 öre at base 0.50)
                elif 8 <= hour <= 18:
                    price = base_price * 4.0  # very expensive (200 öre at base 0.50)
                else:
                    price = base_price
                prices.append({
                    "date": d,
                    "hour": f"{hour:02d}:00",
                    "sek_per_kwh": price,
                })
        return prices

    def test_simulate_basic(self):
        from batteri import simulate, BatteryConfig
        from tariff import Tidstariff
        prices = self._make_prices(n_days=3)
        config = BatteryConfig(capacity_kwh=10.0, max_charge_kw=5.0, max_discharge_kw=5.0)
        tariff = Tidstariff()
        result = simulate(prices, config, tariff)
        assert result.total_charged_kwh > 0
        assert result.total_discharged_kwh > 0
        assert result.net_profit_sek > 0

    def test_simulate_no_tariff(self):
        from batteri import simulate, BatteryConfig
        prices = self._make_prices(n_days=2)
        config = BatteryConfig(capacity_kwh=10.0)
        result = simulate(prices, config, tariff=None)
        # Should still work with spot-only pricing
        assert len(result.slots) > 0

    def test_simulate_with_solar(self):
        from batteri import simulate, BatteryConfig
        from tariff import Tidstariff
        from solar import SolarConfig
        prices = self._make_prices(n_days=2)
        config = BatteryConfig(capacity_kwh=10.0)
        solar = SolarConfig(capacity_kwp=10.0)
        result = simulate(prices, config, Tidstariff(), solar)
        assert result.total_solar_charge_kwh >= 0

    def test_simulate_profit_positive_with_spread(self):
        """With clear price spread, battery should make money."""
        from batteri import simulate, BatteryConfig
        from tariff import FastTariff
        prices = self._make_prices(n_days=7, base_price=1.0)
        config = BatteryConfig(
            capacity_kwh=32.0,
            max_charge_kw=10.0,
            max_discharge_kw=10.0,
            efficiency=0.90,
            fuse_amps=25,
        )
        result = simulate(prices, config, FastTariff())
        assert result.net_profit_sek > 0

    def test_simulate_zero_spread_no_profit(self):
        """With flat prices, battery shouldn't cycle (no profitable spread)."""
        from batteri import simulate, BatteryConfig
        # All hours same price
        prices = []
        for day in range(3):
            d = f"2026-01-{5+day:02d}"
            for hour in range(24):
                prices.append({
                    "date": d,
                    "hour": f"{hour:02d}:00",
                    "sek_per_kwh": 0.50,
                })
        config = BatteryConfig(capacity_kwh=10.0)
        result = simulate(prices, config, None)
        assert result.total_charged_kwh == 0

    def test_sim_result_properties(self):
        from batteri import SimResult, BatteryConfig, SlotResult
        config = BatteryConfig(capacity_kwh=10.0)
        result = SimResult(config=config, tariff_name="test")
        result.slots = [
            SlotResult(date="2026-01-05", hour="02:00", sek_per_kwh=0.25,
                       grid_fee_ore=30.5, total_cost_ore=55.5,
                       action="charge", power_kw=5.0, energy_kwh=5.0,
                       soc_before=0.5, soc_after=3.0, cost_sek=1.25, saving_sek=0.0),
            SlotResult(date="2026-01-05", hour="14:00", sek_per_kwh=1.00,
                       grid_fee_ore=76.5, total_cost_ore=121.5,
                       action="discharge", power_kw=5.0, energy_kwh=4.5,
                       soc_before=7.0, soc_after=2.5, cost_sek=0.0, saving_sek=4.50),
        ]
        assert result.total_charged_kwh == 5.0
        assert result.total_discharged_kwh == 4.5
        assert result.total_charge_cost == 1.25
        assert result.total_discharge_value == 4.50
        assert abs(result.net_profit_sek - (4.50 - 1.25)) < 0.01

    def test_simulate_with_enkeltariff(self):
        from batteri import simulate, BatteryConfig
        from tariff import FastTariff
        prices = self._make_prices(n_days=3)
        config = BatteryConfig(capacity_kwh=16.0, max_charge_kw=5.0, max_discharge_kw=5.0)
        result = simulate(prices, config, FastTariff())
        assert len(result.slots) == 72  # 3 days × 24 hours

    def test_simulate_with_effekttariff(self):
        from batteri import simulate, BatteryConfig
        from tariff import EffektTariff
        prices = self._make_prices(n_days=3)
        config = BatteryConfig(capacity_kwh=16.0)
        result = simulate(prices, config, EffektTariff())
        assert len(result.slots) == 72

    def test_simulate_with_smart_ev(self):
        from batteri import simulate, BatteryConfig, LoadSchedule
        from tariff import Tidstariff
        ev = LoadSchedule("EV", 11.0, 18, 7, daily_kwh=30.0, smart=True)
        config = BatteryConfig(
            capacity_kwh=32.0,
            max_charge_kw=10.0,
            max_discharge_kw=10.0,
            scheduled_loads=[ev],
        )
        prices = self._make_prices(n_days=3)
        result = simulate(prices, config, Tidstariff())
        assert len(result.slots) == 72


    def test_quarter_hour_prices_averaged_to_hourly(self):
        """15-min prices (from Oct 2025) must not count as full hours."""
        from batteri import to_hourly, simulate, BatteryConfig
        rows = []
        for hour in range(24):
            for q, p in enumerate((0.4, 0.6, 0.8, 1.0)):
                rows.append({"date": "2025-12-01", "hour": f"{hour:02d}:{q * 15:02d}",
                             "sek_per_kwh": p + (2.0 if hour == 18 else 0.0)})
        hourly = to_hourly(rows)
        assert len(hourly) == 24
        assert hourly[0]["hour"] == "00:00"
        assert abs(hourly[0]["sek_per_kwh"] - 0.7) < 1e-9
        # Mixed series: an hourly day before the quarter-hour day
        mixed = [{"date": "2025-09-30", "hour": f"{h:02d}:00", "sek_per_kwh": 0.5}
                 for h in range(24)] + rows
        config = BatteryConfig(capacity_kwh=32.0, max_charge_kw=5.0, max_discharge_kw=5.0)
        r = simulate(mixed, config, None)
        assert len(r.slots) == 48
        assert max(s.energy_kwh for s in r.slots) <= 5.0 + 1e-6

    def test_battery_saves_energy_for_evening_peak(self):
        """Discharge must happen at the day's peak, not drain earlier."""
        from batteri import simulate, BatteryConfig
        prices = [{"date": "2026-01-07", "hour": f"{h:02d}:00",
                   "sek_per_kwh": 0.2 if h < 4 else (3.0 if h == 18 else 1.0)}
                  for h in range(24)]
        config = BatteryConfig(capacity_kwh=32.0, max_charge_kw=15.0, max_discharge_kw=15.0,
                               export_price_factor=1.0)
        result = simulate(prices, config, None)
        peak = [s for s in result.slots if s.hour == "18:00"][0]
        assert peak.action == "discharge"
        assert abs(peak.energy_kwh - 15.0) < 0.01

    def test_zero_export_discharge_capped_at_house_load(self):
        """Without export, the battery can't deliver more than the house uses."""
        from batteri import simulate, BatteryConfig
        prices = [{"date": "2026-01-07", "hour": f"{h:02d}:00",
                   "sek_per_kwh": 0.2 if h < 4 else (3.0 if h == 18 else 1.0)}
                  for h in range(24)]
        config = BatteryConfig(capacity_kwh=32.0, max_charge_kw=15.0, max_discharge_kw=15.0,
                               base_load_kw=2.0, export_price_factor=0.0)
        result = simulate(prices, config, None)
        discharges = [s for s in result.slots if s.action == "discharge"]
        assert discharges
        assert all(s.energy_kwh <= 2.0 + 1e-6 for s in discharges)
        peak = [s for s in result.slots if s.hour == "18:00"][0]
        assert peak.action == "discharge"

    def test_no_loss_making_trades_on_small_spread(self):
        """Tiny spreads below efficiency loss must not trigger cycling."""
        from batteri import simulate, BatteryConfig
        prices = [{"date": "2026-01-07", "hour": f"{h:02d}:00",
                   "sek_per_kwh": 1.0 + h * 0.001} for h in range(24)]
        result = simulate(prices, BatteryConfig(capacity_kwh=10.0), None)
        assert result.total_charged_kwh == 0
        assert result.net_profit_sek >= 0

    def test_spot_price_includes_vat_when_buying(self):
        from batteri import simulate, BatteryConfig
        prices = [{"date": "2026-01-07", "hour": f"{h:02d}:00",
                   "sek_per_kwh": 0.5 if h < 4 else 2.0} for h in range(24)]
        result = simulate(prices, BatteryConfig(capacity_kwh=10.0), None)
        charge = [s for s in result.slots if s.action == "charge"][0]
        assert abs(charge.total_cost_ore - 62.5) < 0.01


# ============================================================
# Cross-module integration tests
# ============================================================

class TestIntegration:
    def test_tariff_with_battery_config(self):
        """Battery config fuse fees should match tariff module."""
        from batteri import BatteryConfig
        from tariff import get_fuse_fee_yearly
        config = BatteryConfig(fuse_amps=25)
        fee = get_fuse_fee_yearly(config.fuse_amps)
        assert fee == 10125

    def test_solar_feeds_into_simulation(self):
        """Solar production should reduce grid charging."""
        from batteri import simulate, BatteryConfig
        from tariff import Tidstariff
        from solar import SolarConfig

        prices = []
        for hour in range(24):
            prices.append({
                "date": "2026-06-15",
                "hour": f"{hour:02d}:00",
                "sek_per_kwh": 0.30 if 1 <= hour <= 5 else 0.80,
            })

        config = BatteryConfig(capacity_kwh=10.0, max_charge_kw=5.0, max_discharge_kw=5.0)
        tariff = Tidstariff()

        # Without solar
        r_no_solar = simulate(prices, config, tariff, solar=None)
        # With solar
        solar = SolarConfig(capacity_kwp=10.0)
        r_solar = simulate(prices, config, tariff, solar=solar)

        # Solar should provide some free charging
        assert r_solar.total_solar_charge_kwh >= 0


# ============================================================
# financial.py tests
# ============================================================

class TestNPV:
    def test_zero_discount_equals_sum(self):
        """With 0% discount rate, NPV = sum of cashflows."""
        from financial import npv
        cashflows = [-1000, 300, 300, 300, 300]
        assert abs(npv(cashflows, 0.0) - 200.0) < 1e-9

    def test_positive_discount_reduces_npv(self):
        """Higher discount rate reduces NPV of a positive cashflow stream."""
        from financial import npv
        cashflows = [-1000, 300, 300, 300, 300]
        npv_0 = npv(cashflows, 0.0)
        npv_5 = npv(cashflows, 0.05)
        npv_10 = npv(cashflows, 0.10)
        assert npv_0 > npv_5 > npv_10

    def test_known_value(self):
        """Hand-calculated: -100 + 110/1.10 = 0."""
        from financial import npv
        assert abs(npv([-100, 110], 0.10)) < 1e-9

    def test_investment_only_is_negative(self):
        """Just an investment with no returns has NPV equal to -investment."""
        from financial import npv
        assert npv([-1000], 0.05) == -1000


class TestIRR:
    def test_simple_case(self):
        """Known answer: [-1000, 500, 500, 500] has IRR ≈ 23.375%."""
        from financial import irr
        result = irr([-1000, 500, 500, 500])
        assert result is not None
        assert abs(result - 0.23375) < 0.001

    def test_break_even(self):
        """[-100, 110] has IRR = 10% exactly."""
        from financial import irr
        result = irr([-100, 110])
        assert result is not None
        assert abs(result - 0.10) < 1e-6

    def test_irr_satisfies_npv_zero(self):
        """By definition, NPV at the IRR should be zero."""
        from financial import irr, npv
        cashflows = [-5000, 1200, 1500, 1800, 2000]
        r = irr(cashflows)
        assert r is not None
        assert abs(npv(cashflows, r)) < 1e-4

    def test_no_positive_returns(self):
        """All-negative cashflows have no IRR."""
        from financial import irr
        assert irr([-100, -50, -50]) is None

    def test_no_negative_investment(self):
        """All-positive cashflows have no IRR."""
        from financial import irr
        assert irr([100, 50, 50]) is None


class TestDiscountedPayback:
    def test_payback_within_horizon(self):
        """Investment of 1000, 500/year: undiscounted payback is 2 years."""
        from financial import discounted_payback
        # At 0% discount, payback is exactly 2 years
        result = discounted_payback([-1000, 500, 500, 500], 0.0)
        assert result is not None
        assert abs(result - 2.0) < 1e-6

    def test_discounting_extends_payback(self):
        """Higher discount rate pushes payback further out."""
        from financial import discounted_payback
        cashflows = [-1000, 300, 300, 300, 300, 300]
        pb_0 = discounted_payback(cashflows, 0.0)
        pb_10 = discounted_payback(cashflows, 0.10)
        assert pb_0 is not None and pb_10 is not None
        assert pb_10 > pb_0

    def test_never_pays_back(self):
        """Cashflows too small to ever recover investment."""
        from financial import discounted_payback
        assert discounted_payback([-1000, 10, 10, 10], 0.05) is None


class TestBuildCashflows:
    def test_length(self):
        """Cashflow length = horizon + 1 (year 0 + years 1..N)."""
        from financial import FinancialAssumptions, build_cashflows
        a = FinancialAssumptions(analysis_horizon_years=10, standby_draw_w=0,
                                  annual_capacity_degradation=0)
        cf = build_cashflows(10000, 2000, a)
        assert len(cf) == 11

    def test_year_zero_is_investment(self):
        """Index 0 should be negative investment."""
        from financial import FinancialAssumptions, build_cashflows
        a = FinancialAssumptions(standby_draw_w=0, annual_capacity_degradation=0,
                                  analysis_horizon_years=5)
        cf = build_cashflows(10000, 1000, a)
        assert cf[0] == -10000

    def test_flat_no_degradation_no_standby(self):
        """With no degradation and no standby, years 1..N should all equal savings."""
        from financial import FinancialAssumptions, build_cashflows
        a = FinancialAssumptions(
            analysis_horizon_years=5,
            electricity_price_inflation=0.0,
            annual_capacity_degradation=0.0,
            standby_draw_w=0.0,
            annual_maintenance_sek=0.0,
            residual_value_fraction=0.0,
        )
        cf = build_cashflows(10000, 2000, a)
        for year_cf in cf[1:]:
            assert abs(year_cf - 2000) < 1e-9

    def test_degradation_reduces_later_years(self):
        """With degradation, year 5 earns less than year 1."""
        from financial import FinancialAssumptions, build_cashflows
        a = FinancialAssumptions(
            analysis_horizon_years=10,
            annual_capacity_degradation=0.02,
            standby_draw_w=0.0,
        )
        cf = build_cashflows(10000, 2000, a)
        assert cf[1] > cf[5] > cf[10]

    def test_standby_reduces_net(self):
        """Standby draw should reduce net annual cashflow."""
        from financial import FinancialAssumptions, build_cashflows
        no_standby = FinancialAssumptions(
            analysis_horizon_years=5, standby_draw_w=0,
            annual_capacity_degradation=0,
        )
        with_standby = FinancialAssumptions(
            analysis_horizon_years=5, standby_draw_w=50,
            standby_price_sek_per_kwh=2.0,
            annual_capacity_degradation=0,
        )
        cf_no = build_cashflows(10000, 3000, no_standby)
        cf_yes = build_cashflows(10000, 3000, with_standby)
        # ~50 W * 8760 h * 2 SEK = 876 SEK/year cost
        assert abs((cf_no[1] - cf_yes[1]) - 876) < 1.0


class TestAnalyze:
    def test_profitable_investment(self):
        """Investment that should be clearly profitable."""
        from financial import FinancialAssumptions, analyze
        a = FinancialAssumptions(
            discount_rate=0.04,
            analysis_horizon_years=15,
            standby_draw_w=0,
            annual_capacity_degradation=0,
        )
        # 50k investment, 8k/year savings over 15 years = clearly profitable
        result = analyze(50000, 8000, a)
        assert result.npv_sek > 0
        assert result.irr is not None
        assert result.irr > 0.04  # Better than discount rate
        assert result.simple_payback_years is not None
        assert result.simple_payback_years < 15

    def test_unprofitable_investment(self):
        """Investment too expensive to be worth it."""
        from financial import FinancialAssumptions, analyze
        a = FinancialAssumptions(
            discount_rate=0.04,
            analysis_horizon_years=15,
        )
        # 200k investment, 5k/year — won't pay back within horizon
        result = analyze(200000, 5000, a)
        assert result.npv_sek < 0

    def test_verdict_format(self):
        """Verdict should contain NPV indication."""
        from financial import FinancialAssumptions, analyze
        result = analyze(50000, 8000, FinancialAssumptions(standby_draw_w=0))
        assert "NPV" in result.verdict


# ============================================================
# scenarios.py tests
# ============================================================

class TestScenarios:
    def _build_prices(self, years: list[int], spread: float = 0.5):
        """Build synthetic hourly prices for specified years."""
        from datetime import date, timedelta
        prices = []
        for y in years:
            start = date(y, 1, 1)
            # 365 days of data
            for d in range(365):
                current = start + timedelta(days=d)
                date_str = current.isoformat()
                for h in range(24):
                    # Simple diurnal pattern: cheap at night, expensive 17-19
                    if 17 <= h <= 19:
                        price = 1.0 + spread
                    elif 2 <= h <= 5:
                        price = 1.0 - spread
                    else:
                        price = 1.0
                    prices.append({
                        "date": date_str,
                        "hour": f"{h:02d}:00",
                        "sek_per_kwh": price,
                    })
        return prices

    def test_splits_by_year(self):
        """Scenario runner should produce one result per year."""
        from scenarios import run_yearly_scenarios
        from batteri import BatteryConfig, simulate
        prices = self._build_prices([2022, 2023, 2024])
        config = BatteryConfig(
            capacity_kwh=10, max_charge_kw=3, max_discharge_kw=3,
            purchase_price=50000, base_load_kw=0.5,
        )
        summary = run_yearly_scenarios(prices, simulate, config)
        assert len(summary.years) == 3
        assert {s.year for s in summary.years} == {2022, 2023, 2024}

    def test_skips_sparse_years(self):
        """Years with <180 days should be dropped."""
        from scenarios import run_yearly_scenarios
        from batteri import BatteryConfig, simulate
        # 2024 has full year, 2025 has only 10 days
        prices = self._build_prices([2024])
        # Add a handful of 2025 days
        from datetime import date, timedelta
        start_2025 = date(2025, 1, 1)
        for d in range(10):
            current = start_2025 + timedelta(days=d)
            for h in range(24):
                prices.append({"date": current.isoformat(), "hour": f"{h:02d}:00",
                               "sek_per_kwh": 1.0})
        config = BatteryConfig(
            capacity_kwh=10, max_charge_kw=3, max_discharge_kw=3,
            base_load_kw=0.5,
        )
        summary = run_yearly_scenarios(prices, simulate, config)
        years_seen = {s.year for s in summary.years}
        assert 2024 in years_seen
        assert 2025 not in years_seen

    def test_summary_statistics(self):
        """Summary stats should be consistent."""
        from scenarios import ScenarioSummary, YearlyScenario
        summary = ScenarioSummary(years=[
            YearlyScenario(year=2020, num_days=365, annual_savings_sek=1000,
                           cycles=100, avg_spot_ore_per_kwh=50, avg_spread_ore_per_kwh=20),
            YearlyScenario(year=2021, num_days=365, annual_savings_sek=2000,
                           cycles=150, avg_spot_ore_per_kwh=80, avg_spread_ore_per_kwh=30),
            YearlyScenario(year=2022, num_days=365, annual_savings_sek=5000,
                           cycles=250, avg_spot_ore_per_kwh=150, avg_spread_ore_per_kwh=80),
        ])
        assert summary.min_savings == 1000
        assert summary.max_savings == 5000
        assert summary.median_savings == 2000
        # P25 should be between min and median
        p25 = summary.percentile(0.25)
        assert 1000 <= p25 <= 2000


# ============================================================
# economics.py tests + effekt-aware charging + smart load energy
# ============================================================

def _slot(d, hour, action="idle", power=0.0, solar=0.0, cost_ore=100.0):
    from batteri import SlotResult
    return SlotResult(date=d, hour=hour, sek_per_kwh=0.5, grid_fee_ore=0.0,
                      total_cost_ore=cost_ore, action=action, power_kw=power,
                      energy_kwh=power, soc_before=0.0, soc_after=0.0,
                      cost_sek=0.0, saving_sek=0.0, solar_kw=solar)


def _seom_like():
    from tariff import EffektTariff
    return EffektTariff(energy_rate=5.0, effekt_rate=145.0, low_season_rate=72.5,
                        top_n_peaks=3, night_discount=1.0, peak_months=(11, 12, 1, 2, 3),
                        peak_weekday_only=True, peak_hour_start=7, peak_hour_end=19)


class TestSolarDirectUse:
    def test_capped_at_house_load(self):
        """Surplus solar (battery, export or curtailed) is not direct use."""
        from batteri import SimResult, BatteryConfig
        from economics import solar_direct_use
        cfg = BatteryConfig(base_load_kw=2.0)
        r = SimResult(config=cfg)
        r.slots = [_slot("2026-06-15", "12:00", solar=5.0, cost_ore=100.0),
                   _slot("2026-06-15", "18:00", solar=1.0, cost_ore=200.0),
                   _slot("2026-06-15", "23:00", solar=0.0, cost_ore=300.0)]
        kwh, sek = solar_direct_use(r, cfg)
        assert abs(kwh - 3.0) < 1e-9          # 2 (capped) + 1
        assert abs(sek - (2.0 * 1.0 + 1.0 * 2.0)) < 1e-9  # each at its own slot price

    def test_independent_of_battery_size(self):
        from batteri import simulate, BatteryConfig
        from tariff import Tidstariff
        from solar import SolarConfig
        from economics import solar_direct_use
        prices = [{"date": "2026-06-15", "hour": f"{h:02d}:00",
                   "sek_per_kwh": 0.3 if h < 6 else 1.0} for h in range(24)]
        vals = []
        for cap in (5.0, 32.0):
            cfg = BatteryConfig(capacity_kwh=cap, export_price_factor=0.0)
            r = simulate(prices, cfg, Tidstariff(), SolarConfig(capacity_kwp=15.0))
            vals.append(solar_direct_use(r, cfg))
        assert abs(vals[0][0] - vals[1][0]) < 1e-6
        assert abs(vals[0][1] - vals[1][1]) < 1e-6


class TestEffektSavings:
    def test_higher_peak_is_negative(self):
        """Charging that raises the monthly peak costs money (no clamp at zero)."""
        from batteri import SimResult, BatteryConfig
        from economics import effekt_savings
        tf = _seom_like()
        cfg = BatteryConfig(base_load_kw=2.0)
        r = SimResult(config=cfg)
        # Mon-Wed January: charging 5 kW at 10:00 on top of 2 kW load
        r.slots = [_slot(f"2026-01-0{d}", "10:00", "charge", 5.0) for d in (5, 6, 7)]
        val = effekt_savings(r, tf, cfg, num_days=365.25)
        assert abs(val - (-5.0 * 145.0)) < 1e-6

    def test_discharge_lowers_peak(self):
        from batteri import SimResult, BatteryConfig
        from economics import effekt_savings
        tf = _seom_like()
        cfg = BatteryConfig(base_load_kw=4.0)
        r = SimResult(config=cfg)
        r.slots = [_slot(f"2026-01-0{d}", "17:00", "discharge", 3.0) for d in (5, 6, 7)]
        assert abs(effekt_savings(r, tf, cfg, num_days=365.25) - 3.0 * 145.0) < 1e-6

    def test_solar_in_baseline(self):
        """Existing panels: solar's own peak reduction is not credited to the battery."""
        from batteri import SimResult, BatteryConfig
        from economics import effekt_savings
        tf = _seom_like()
        cfg = BatteryConfig(base_load_kw=4.0)
        r = SimResult(config=cfg)
        r.slots = [_slot(f"2026-01-0{d}", "12:00", solar=1.0) for d in (5, 6, 7)]
        assert abs(effekt_savings(r, tf, cfg, 365.25) - 145.0) < 1e-6
        assert abs(effekt_savings(r, tf, cfg, 365.25, solar_in_baseline=True)) < 1e-9


class TestEffektAwareCharging:
    def _prices(self):
        # Mon 5 - Fri 9 Jan 2026: cheap midday (inside SEOM peak hours 07-19),
        # expensive evening (outside)
        rows = []
        for d in range(5, 10):
            for h in range(24):
                p = 0.10 if 10 <= h <= 12 else (3.0 if h in (20, 21) else 1.0)
                rows.append({"date": f"2026-01-{d:02d}", "hour": f"{h:02d}:00", "sek_per_kwh": p})
        return rows

    def test_charging_never_raises_peak(self):
        from batteri import simulate, BatteryConfig
        from economics import effekt_savings
        tf = _seom_like()
        cfg = BatteryConfig(capacity_kwh=10.0, max_charge_kw=5.0, max_discharge_kw=5.0,
                            base_load_kw=2.0, export_price_factor=0.0)
        r = simulate(self._prices(), cfg, tf)
        for s in r.slots:
            if s.action == "charge" and tf.is_peak_hour(s.date, s.hour):
                assert 2.0 + s.power_kw <= 2.0 + 1e-6
        assert effekt_savings(r, tf, cfg, 5) >= -1e-6

    def test_non_effekt_tariff_unchanged(self):
        """Without an effekttariff the cheap midday hours are still used."""
        from batteri import simulate, BatteryConfig
        from tariff import FastTariff
        cfg = BatteryConfig(capacity_kwh=10.0, max_charge_kw=5.0, max_discharge_kw=5.0,
                            base_load_kw=2.0, export_price_factor=0.0)
        r = simulate(self._prices(), cfg, FastTariff())
        assert any(s.action == "charge" and 10 <= int(s.hour[:2]) <= 12 for s in r.slots)

    def test_zero_rate_season_not_capped(self):
        """Hours priced at 0 kr/kW (e.g. Göteborg summer) don't limit charging."""
        from batteri import simulate, BatteryConfig
        from tariff import EffektTariff
        tf = EffektTariff(effekt_rate=135.0, low_season_rate=0.0, peak_months=(11, 12, 1, 2, 3),
                          night_discount=1.0, peak_weekday_only=True, peak_hour_start=7, peak_hour_end=20)
        # 1-5 June 2026 is Mon-Fri
        rows = [dict(r, date=f"2026-06-{int(r['date'][-2:]) - 4:02d}") for r in self._prices()]
        cfg = BatteryConfig(capacity_kwh=10.0, max_charge_kw=5.0, max_discharge_kw=5.0,
                            base_load_kw=2.0, export_price_factor=0.0)
        r = simulate(rows, cfg, tf)
        assert any(s.action == "charge" and 10 <= int(s.hour[:2]) <= 12 for s in r.slots)


class TestBaselineExport:
    def test_zero_battery_simulation(self):
        from batteri import simulate, BatteryConfig
        from tariff import Tidstariff
        from solar import SolarConfig
        from economics import baseline_export_revenue
        prices = [{"date": "2026-06-15", "hour": f"{h:02d}:00",
                   "sek_per_kwh": 0.3 if h < 6 else 1.0} for h in range(24)]
        cfg = BatteryConfig(capacity_kwh=10.0, export_price_factor=1.0)
        sol = SolarConfig(capacity_kwp=10.0)
        base = baseline_export_revenue(prices, cfg, Tidstariff(), sol)
        assert base > 0
        with_bat = simulate(prices, cfg, Tidstariff(), sol)
        # The battery soaks up some surplus, so it exports less than the panels alone
        assert with_bat.total_export_revenue <= base + 1e-9
        assert cfg.capacity_kwh == 10.0  # original config untouched
        zero = simulate(prices, BatteryConfig(capacity_kwh=0.0, max_charge_kw=0.0,
                                              max_discharge_kw=0.0, export_price_factor=1.0),
                        Tidstariff(), sol)
        assert zero.total_charged_kwh == 0 and zero.total_discharged_kwh == 0
        assert zero.total_solar_charge_kwh == 0 and zero.num_cycles == 0
        assert abs(zero.total_export_revenue - base) < 1e-9


class TestLoanSchedule:
    def test_mortgage_outlives_battery(self):
        from economics import loan_schedule
        ls = loan_schedule(100_000, 3.0, 50, 15)
        assert abs(ls["monthly_payment"] - 322) < 1
        assert abs(ls["balance_at_horizon"] - 83_663) <= 1
        assert abs(ls["interest_in_horizon"] - 41_619) <= 2
        assert abs(ls["paid_in_horizon"] - 57_956) <= 2

    def test_zero_rate(self):
        from economics import loan_schedule
        ls = loan_schedule(120_000, 0.0, 10, 5)
        assert abs(ls["monthly_payment"] - 1000) < 1e-9
        assert abs(ls["balance_at_horizon"] - 60_000) < 1e-6
        assert abs(ls["interest_in_horizon"]) < 1e-6

    def test_loan_ends_before_horizon(self):
        from economics import loan_schedule
        ls = loan_schedule(100_000, 5.0, 10, 15)
        assert ls["balance_at_horizon"] == 0
        assert abs(ls["interest_in_horizon"] - (ls["monthly_payment"] * 120 - 100_000)) < 1e-6


class TestWearAndStandby:
    def test_standby_cost(self):
        from economics import standby_cost_per_year
        # 45 W × 8,760 h = 394.2 kWh at 150 öre = 591.3 kr
        assert abs(standby_cost_per_year(45, 150.0) - 591.3) < 1e-9
        assert standby_cost_per_year(0, 150.0) == 0

    def test_yearly_benefit_mid_year_wear(self):
        from economics import yearly_benefit
        # Year 1: battery at 1 − 0.01×0.5, solar at 0.995^0.5, fixed unchanged
        b = yearly_benefit(10_000, 6_000, -500, 1, 0.01, 0.005)
        assert abs(b - (10_000 * 0.995 + 6_000 * 0.995 ** 0.5 - 500)) < 1e-9
        # No wear: plain sum
        assert yearly_benefit(10_000, 6_000, -500, 7, 0, 0) == 15_500
        # Battery value never goes negative
        assert yearly_benefit(10_000, 0, 0, 200, 0.01, 0) == 0

    def test_lifetime_benefit_partial_year(self):
        from economics import lifetime_benefit, yearly_benefit
        # No wear: equals yearly × lifetime, also for a fractional lifetime
        assert abs(lifetime_benefit(1_000, 500, -100, 12.4, 0, 0) - 1_400 * 12.4) < 1e-9
        # With wear: last year weighted by its fraction
        exp = sum(yearly_benefit(1_000, 500, -100, yr, 0.01, 0.005) for yr in range(1, 3))
        exp += 0.5 * yearly_benefit(1_000, 500, -100, 3, 0.01, 0.005)
        assert abs(lifetime_benefit(1_000, 500, -100, 2.5, 0.01, 0.005) - exp) < 1e-9
        # Linear battery fade: average over 15 years = value at the midpoint (7.5 yr)
        assert abs(lifetime_benefit(10_000, 0, 0, 15, 0.01, 0) - 15 * 10_000 * 0.925) < 1e-6

    def test_payback_interpolated_and_none(self):
        from economics import payback_years
        assert abs(payback_years(25_000, 10_000, 0, 0, 0, 0) - 2.5) < 1e-9
        # Wear makes payback later than investment / year-1 benefit
        assert payback_years(100_000, 10_000, 0, 0, 0.01, 0) > 100_000 / 9_950
        # Never reached within the 25-year solar lifetime
        assert payback_years(100_000, 1_000, 0, 0, 0.01, 0) is None
        assert payback_years(10_000, 1_000, 0, -2_000, 0, 0) is None
        assert payback_years(0, 1_000, 0, 0, 0, 0) == 0
        # After the battery lifetime only the panels keep paying: 5 years of
        # 10,000 (battery 8,000 + solar 2,000) = 50,000, then 2,000 per year.
        assert abs(payback_years(60_000, 8_000, 2_000, 0, 0, 0, lifetime=5) - 10.0) < 1e-9
        # A battery-only investment that isn't repaid within the battery's life never is
        assert payback_years(60_000, 8_000, 0, 0, 0, 0, lifetime=5) is None
        # Standby (fixed part) stops with the battery too
        assert abs(payback_years(40_000, 8_000, 2_000, -1_000, 0, 0, lifetime=4) - 6.0) < 1e-9

    def test_unchanged_scenario_equals_main_result(self):
        """The 1.0× scenario must reproduce the main lifetime benefit exactly."""
        from economics import lifetime_benefit, scenario_bat_part
        vol = {0.7: 6_000.0, 1.0: 9_000.0, 1.5: 12_000.0, 2.5: 15_000.0, 4.0: 20_000.0}
        main = lifetime_benefit(9_000.0, 6_653.0, -700.0, 13.7, 0.01, 0.005)
        scen = lifetime_benefit(lambda yr: scenario_bat_part(vol, 1.0, yr),
                                6_653.0, -700.0, 13.7, 0.01, 0.005)
        assert scen == main

    def test_scenario_ramp(self):
        from economics import scenario_bat_part, value_at_level
        vol = {0.7: 7_000.0, 1.0: 10_000.0, 1.5: 12_000.0}
        assert scenario_bat_part(vol, 1.5, 10) == 12_000.0
        assert scenario_bat_part(vol, 1.5, 14) == 12_000.0          # stays at target
        assert abs(scenario_bat_part(vol, 1.5, 5) - 11_000.0) < 1e-9  # 1.25× halfway
        assert abs(scenario_bat_part(vol, 0.7, 5) - 8_500.0) < 1e-9   # 0.85×
        assert value_at_level(vol, 5.0) == 12_000.0                  # clamped


class TestSolarFlows:
    def test_flows_add_up(self):
        from batteri import SimResult, BatteryConfig
        from economics import solar_flows
        r = SimResult(config=BatteryConfig())
        # 6 kW solar: 2 direct, 2 battery, 1 flex, 1 curtailed (zero export)
        s1 = _slot("2026-06-15", "12:00", solar=6.0)
        s1.solar_charge_kwh, s1.flex_consumed_kwh = 2.0, 1.0
        # 4 kW solar, battery discharging 3 kWh to the grid on top of 1 kWh solar export
        s2 = _slot("2026-06-15", "13:00", action="discharge", power=3.0, solar=4.0)
        s2.grid_export_kwh = 4.0
        r.slots = [s1, s2]
        f = solar_flows(r, direct_kwh=5.0)
        assert f["produced"] == 10.0 and f["battery"] == 2.0 and f["flex"] == 1.0
        assert f["exported"] == 1.0
        assert abs(f["curtailed"] - 1.0) < 1e-9


class TestReportAssumptions:
    def test_wear_and_five_scenarios_in_pdf(self):
        from report import generate_report
        scen = {f"S{v}": {"arb_yr": 1000.0 * v, "vol": v, "lifetime_profit": 100.0 * v - 200,
                          "desc": "antagande"} for v in (0.7, 1.0, 1.5, 2.5, 4.0)}
        pdf = generate_report(battery_label="32 kWh", future_scenarios=scen,
                              battery_fade_pct=1.0, standby_w=45, standby_cost_yr=600,
                              solar_degradation_pct=0.5)
        assert pdf[:4] == b"%PDF"


class TestSmartLoadEnergy:
    def test_daily_energy_matches_target(self):
        """11 kW EV needing 30 kWh: 3 hours, the most expensive at 8 kW."""
        from batteri import simulate, BatteryConfig, LoadSchedule
        ev = LoadSchedule("EV", 11.0, 18, 7, daily_kwh=30.0, smart=True)
        cfg = BatteryConfig(capacity_kwh=10.0, base_load_kw=1.0, scheduled_loads=[ev])
        prices = [{"date": "2026-01-07", "hour": f"{h:02d}:00",
                   "sek_per_kwh": 0.1 + 0.01 * h if h < 7 else 1.0 + 0.01 * h} for h in range(24)]
        simulate(prices, cfg, None)
        sched = cfg._smart_schedule["2026-01-07"][0]
        assert sorted(sched) == [0, 1, 2]
        assert abs(sum(sched.values()) - 30.0) < 1e-9
        assert sched[2] == 8.0 and sched[0] == 11.0
        ev_kwh = sum(cfg.total_load_kw(h, 1, "2026-01-07") - 1.0 for h in range(24))
        assert abs(ev_kwh - 30.0) < 1e-9

    def test_no_daily_target_runs_full_window(self):
        from batteri import simulate, BatteryConfig, LoadSchedule
        ev = LoadSchedule("EV", 11.0, 22, 2, daily_kwh=0.0, smart=True)
        cfg = BatteryConfig(capacity_kwh=10.0, base_load_kw=1.0, scheduled_loads=[ev])
        prices = [{"date": "2026-01-07", "hour": f"{h:02d}:00", "sek_per_kwh": 1.0} for h in range(24)]
        simulate(prices, cfg, None)
        assert cfg._smart_schedule["2026-01-07"][0] == {22: 11.0, 23: 11.0, 0: 11.0, 1: 11.0}


class TestBaselineBill:
    """Household bill without investing, used to compare an operator's tariffs."""

    def _result(self, slots, base_load=2.0):
        from batteri import SimResult, BatteryConfig
        cfg = BatteryConfig(base_load_kw=base_load)
        r = SimResult(config=cfg)
        r.slots = slots
        return r, cfg

    def test_energy_at_each_slot_price(self):
        from tariff import FastTariff
        from economics import baseline_bill
        r, cfg = self._result([_slot("2026-06-15", "03:00", cost_ore=100.0),
                               _slot("2026-06-15", "18:00", cost_ore=200.0)])
        # 2 kWh × 1 kr + 2 kWh × 2 kr, one year of data
        assert abs(baseline_bill(r, FastTariff(), cfg, 365.25) - 6.0) < 1e-9
        # Two years of data: halved per year
        assert abs(baseline_bill(r, FastTariff(), cfg, 730.5) - 3.0) < 1e-9

    def test_battery_actions_ignored(self):
        """The bill is WITHOUT the investment: charging/discharging changes nothing."""
        from tariff import FastTariff
        from economics import baseline_bill
        r1, cfg = self._result([_slot("2026-06-15", "03:00", cost_ore=100.0)])
        r2, _ = self._result([_slot("2026-06-15", "03:00", "charge", 5.0, cost_ore=100.0)])
        assert baseline_bill(r1, FastTariff(), cfg, 365.25) == baseline_bill(r2, FastTariff(), cfg, 365.25)

    def test_solar_in_baseline(self):
        """Existing panels: only the load they don't cover is bought (never negative)."""
        from tariff import FastTariff
        from economics import baseline_bill
        r, cfg = self._result([_slot("2026-06-15", "12:00", solar=3.0, cost_ore=100.0),
                               _slot("2026-06-15", "17:00", solar=1.0, cost_ore=100.0)])
        assert abs(baseline_bill(r, FastTariff(), cfg, 365.25) - 4.0) < 1e-9
        assert abs(baseline_bill(r, FastTariff(), cfg, 365.25, solar_in_baseline=True) - 1.0) < 1e-9

    def test_effekt_tariff_adds_demand_charge(self):
        """EffektTariff: energy + the no-investment peaks priced like effekt_savings()."""
        from economics import baseline_bill, effekt_savings
        tf = _seom_like()
        # Mon-Wed January 10:00 (measured) + one evening hour (not measured), load 2 kW
        slots = [_slot(f"2026-01-0{d}", "10:00", cost_ore=100.0) for d in (5, 6, 7)]
        slots.append(_slot("2026-01-05", "22:00", cost_ore=100.0))
        r, cfg = self._result(slots)
        # energy 4 × 2 kWh × 1 kr = 8; demand: top-3 average 2 kW × 145 kr = 290
        assert abs(baseline_bill(r, tf, cfg, 365.25) - 298.0) < 1e-9
        # Same peak rules as effekt_savings: a 5 kW charge raises the peak by 5 kW there
        r2, _ = self._result([_slot(f"2026-01-0{d}", "10:00", "charge", 5.0) for d in (5, 6, 7)])
        assert abs(effekt_savings(r2, tf, cfg, 365.25) - (-5.0 * 145.0)) < 1e-9
        assert abs(baseline_bill(r2, tf, cfg, 365.25) - (6.0 + 2.0 * 145.0)) < 1e-9

    def test_effekt_with_solar_in_baseline(self):
        from economics import baseline_bill
        tf = _seom_like()
        r, cfg = self._result([_slot(f"2026-01-0{d}", "12:00", solar=1.0, cost_ore=100.0)
                               for d in (5, 6, 7)], base_load=4.0)
        # raw: 3 × 4 kWh + 4 kW × 145; existing panels: 3 × 3 kWh + 3 kW × 145
        assert abs(baseline_bill(r, tf, cfg, 365.25) - (12.0 + 580.0)) < 1e-9
        assert abs(baseline_bill(r, tf, cfg, 365.25, solar_in_baseline=True) - (9.0 + 435.0)) < 1e-9

    def test_tidstariff_vs_enkeltariff_on_simulated_bill(self):
        """Real simulate(): the bill follows each tariff's prices and is battery-size independent."""
        from batteri import simulate, BatteryConfig
        from tariff import Tidstariff, FastTariff
        from economics import baseline_bill
        prices = [{"date": "2026-01-07", "hour": f"{h:02d}:00", "sek_per_kwh": 0.5} for h in range(24)]
        bills = {}
        for tf in (Tidstariff(), FastTariff()):
            for cap in (5.0, 32.0):
                cfg = BatteryConfig(capacity_kwh=cap, base_load_kw=1.0)
                r = simulate(prices, cfg, tf)
                bills[(tf.name, cap)] = baseline_bill(r, tf, cfg, 1)
        tid, enk = Tidstariff(), FastTariff()
        # Wed 7 Jan 2026: 16 peak hours (06-22) + 8 off-peak, 1 kWh each, spot 50 öre × 1.25
        exp_tid = (24 * 62.5 + 16 * tid.peak + 8 * tid.offpeak + 24 * tid.energy_tax) / 100 * 365.25
        exp_enk = (24 * 62.5 + 24 * (enk.flat_rate + enk.energy_tax)) / 100 * 365.25
        assert abs(bills[(tid.name, 5.0)] - exp_tid) < 1e-6
        assert abs(bills[(enk.name, 32.0)] - exp_enk) < 1e-6
        assert bills[(tid.name, 5.0)] == bills[(tid.name, 32.0)]


class TestExampleInputs:
    """Which personal figures are still the app's untouched examples."""

    def _si(self, **kw):
        from example_inputs import EXAMPLE, default_battery_rows
        rows = [(r["Namn"], r["Kapacitet_kWh"], r["Max_kW"], float(r["Pris_SEK"]))
                for r in default_battery_rows(EXAMPLE["eur_sek"])]
        si = {"pricing_mode": "table", "battery_rows": rows, "eur_sek": EXAMPLE["eur_sek"],
              "sek_per_kwh": None, "bat_install": EXAMPLE["bat_install"], "use_solar": True,
              "solar_kwp": EXAMPLE["solar_kwp"], "sol_price": EXAMPLE["sol_price"],
              "sol_install": EXAMPLE["sol_install"], "use_heating_model": True,
              "own_consumption": False, "energy_class": EXAMPLE["energy_class"],
              "house_area": EXAMPLE["house_area"], "heating_type": EXAMPLE["heating_type"]}
        si.update(kw)
        return si

    def test_all_defaults_flagged(self):
        from example_inputs import untouched_examples
        assert untouched_examples(self._si()) == [
            "battery_prices", "battery_install", "solar_kwp", "solar_price", "house"]

    def test_default_table_matches_nkon_prices(self):
        from example_inputs import default_battery_rows
        rows = {r["Namn"]: r["Pris_SEK"] for r in default_battery_rows(11.5)}
        assert rows["32 kWh"] == round(2857 * 11.5 * 1.25)
        assert rows["32+16 kWh"] == round((2857 + 1512) * 11.5 * 1.25)
        assert len(rows) == 8

    def test_own_values_not_flagged(self):
        from example_inputs import untouched_examples
        si = self._si(sol_price=150000, bat_install=20000, solar_kwp=10.0)
        assert untouched_examples(si) == ["battery_prices", "house"]
        # Changing only the installation part counts as an own solar price
        assert "solar_price" not in untouched_examples(self._si(sol_install=20000))

    def test_battery_table(self):
        from example_inputs import untouched_examples
        si = self._si()
        edited = list(si["battery_rows"])
        edited[3] = (edited[3][0], edited[3][1], edited[3][2], 30000.0)
        assert "battery_prices" not in untouched_examples(self._si(battery_rows=edited))
        assert "battery_prices" not in untouched_examples(self._si(battery_rows=edited[:4]))
        # Another EUR rate: the default table for that rate is still the example
        from example_inputs import default_battery_rows
        rows12 = [(r["Namn"], r["Kapacitet_kWh"], r["Max_kW"], r["Pris_SEK"])
                  for r in default_battery_rows(12.0)]
        assert "battery_prices" in untouched_examples(self._si(battery_rows=rows12, eur_sek=12.0))
        assert "battery_prices" not in untouched_examples(self._si(battery_rows=rows12))

    def test_sek_per_kwh_mode(self):
        from example_inputs import untouched_examples, EXAMPLE
        si = self._si(pricing_mode="sek_kwh", eur_sek=None, sek_per_kwh=EXAMPLE["sek_per_kwh"])
        assert "battery_prices" in untouched_examples(si)
        assert "battery_prices" not in untouched_examples(dict(si, sek_per_kwh=1500))

    def test_no_solar(self):
        from example_inputs import untouched_examples
        items = untouched_examples(self._si(use_solar=False, solar_kwp=0, sol_price=0))
        assert "solar_kwp" not in items and "solar_price" not in items

    def test_house(self):
        from example_inputs import untouched_examples
        assert "house" not in untouched_examples(self._si(own_consumption=True))
        assert "house" not in untouched_examples(self._si(house_area=180))
        assert "house" not in untouched_examples(self._si(energy_class="E"))
        assert "house" not in untouched_examples(self._si(heating_type="heating_district"))
        assert "house" not in untouched_examples(self._si(use_heating_model=False))

    def test_nothing_untouched(self):
        from example_inputs import untouched_examples
        si = self._si(battery_rows=[("Mitt", 20.0, 10.0, 50000.0)], bat_install=0,
                      solar_kwp=8.0, sol_price=60000, own_consumption=True)
        assert untouched_examples(si) == []

    def test_grid_not_judged(self):
        """Operator, fuse and phases are never flagged by value."""
        from example_inputs import untouched_examples
        si = self._si(grid_operator="Vattenfall Eldistribution", fuse_amps=25, phases=3)
        assert not {"grid_operator", "fuse_amps", "phases"} & set(untouched_examples(si))

    def test_translations_exist(self):
        from translations import STRINGS
        for key in ("example_warning", "example_pdf_note", "example_mark", "example_item_battery_table",
                    "example_item_battery_sek_kwh", "example_item_battery_install",
                    "example_item_solar_kwp", "example_item_solar_price", "example_item_house",
                    "assume_grid", "assume_tariff_reference", "detail_of_which_tariff",
                    "add_ev_load", "add_pool_heat_pump", "ev_load_name", "pool_heat_pump_name"):
            assert STRINGS[key]["sv"] and STRINGS[key]["en"], key



class TestTariffSwitchSaving:
    BILLS = {"V Tidstariff": 34744.0, "V Enkeltariff": 36707.0}

    def test_saving_from_dearer_tariff(self):
        from economics import tariff_switch_saving
        saving, cheapest = tariff_switch_saving(self.BILLS, "V Enkeltariff")
        assert saving == pytest.approx(1963.0)
        assert cheapest == "V Tidstariff"

    def test_already_cheapest(self):
        from economics import tariff_switch_saving
        assert tariff_switch_saving(self.BILLS, "V Tidstariff") == (0.0, "V Tidstariff")

    def test_unknown_or_missing(self):
        from economics import tariff_switch_saving
        assert tariff_switch_saving(self.BILLS, "V Effekttariff") is None
        assert tariff_switch_saving({}, "V Tidstariff") is None
        assert tariff_switch_saving(None, "V Tidstariff") is None

    def test_translations_exist(self):
        from translations import STRINGS
        for key in ("current_tariff_label", "current_tariff_unknown", "current_tariff_help",
                    "current_tariff_keep", "current_tariff_change", "current_tariff_switch_saving",
                    "assume_current_tariff"):
            assert STRINGS[key]["sv"] and STRINGS[key]["en"], key


class TestEnergyFlows:
    @staticmethod
    def _day(**kw):
        n = 2
        base = {"hour": [0, 12], "spot": [0.5, 0.5], "buy_ore": [100.0, 100.0], "load_kw": [0.0] * n,
                "ev_kw": [0.0] * n, "solar_kw": [0.0] * n, "room_kw": [10.0] * n, "in_kwh": [0.0] * n,
                "out_kwh": [0.0] * n, "solar_in_kwh": [0.0] * n, "export_kwh": [0.0] * n,
                "flex_kwh": [0.0] * n, "soc_before_kwh": [5.0, 5.0], "soc_kwh": [5.0, 5.0], "net_sek": [0.0] * n}
        base.update(kw)
        return base

    def test_hour_balances_and_ev_split(self):
        import controller_check as cc
        # hour 0: load 4 (EV 2), battery 3, grid 1. hour 12: solar 10 → 2 house, 5 battery, 1 flex, 2 curtailed
        h = self._day(load_kw=[4.0, 2.0], ev_kw=[2.0, 0.0], out_kwh=[3.0, 0.0], solar_kw=[0.0, 10.0],
                      solar_in_kwh=[0.0, 5.0], flex_kwh=[0.0, 1.0])
        d = cc.day_flows({"2024-06-01": h}, "2024-06-01")
        assert d["from"]["battery"][0] == pytest.approx(3.0)
        assert d["from"]["grid"][0] == pytest.approx(1.0)
        assert d["to"]["ev"][0] == pytest.approx(2.0)
        assert d["to"]["house"][0] == pytest.approx(2.0)
        assert d["to"]["battery"][1] == pytest.approx(5.0)
        assert d["to"]["flex"][1] == pytest.approx(1.0)
        assert d["to"]["curtailed"][1] == pytest.approx(2.0)
        for i in range(2):   # every hour: sources = uses
            assert sum(v[i] for v in d["from"].values()) == pytest.approx(sum(v[i] for v in d["to"].values()))
        assert cc.day_flows({"2024-06-01": h}, "2024-06-02") is None

    def test_yearly_losses(self):
        import controller_check as cc
        # 10 kWh from the grid into the battery, 9 out, stored energy unchanged → 1 kWh lost
        h = self._day(load_kw=[9.0, 0.0], in_kwh=[0.0, 10.0], out_kwh=[9.0, 0.0],
                      soc_before_kwh=[15.0, 5.0], soc_kwh=[5.0, 15.0])
        f = cc.energy_flows({"2024-06-01": h})
        assert f["links"][("battery", "losses")] == pytest.approx(365.25)
        assert f["links"][("grid", "battery")] == pytest.approx(3652.5)


    def test_flow_series_balances_every_hour(self):
        import controller_check as cc
        h = self._day(load_kw=[4.0, 2.0], ev_kw=[2.0, 0.0], out_kwh=[3.0, 0.0], solar_kw=[0.0, 10.0],
                      solar_in_kwh=[0.0, 5.0], flex_kwh=[0.0, 1.0], net_sek=[2.5, 0.0])
        sr = cc.flow_series({"2024-06-02": h, "2024-06-01": h})
        assert sr["dates"] == ["2024-06-01", "2024-06-02"] and sr["day_start"] == [0, 2]
        for i in range(4):
            supply = sr["solar"][i] - sr["curtailed"][i] + sr["grid_in"][i] + sr["bat_out"][i]
            use = sr["house"][i] + sr["ev"][i] + sr["flex"][i] + sr["bat_in"][i] + sr["export"][i]
            assert supply == pytest.approx(use)
        assert sr["net_ore"][0] == pytest.approx(250)

    def test_player_packs_int16_hundredths(self):
        import base64
        import json
        from array import array
        import controller_check as cc
        import flow_player
        h = self._day(load_kw=[4.25, 2.0], solar_kw=[0.0, 10.0], solar_in_kwh=[0.0, 5.0])
        sr = cc.flow_series({"2024-06-01": h})
        html = flow_player.player_html(sr, 32.0, {"locale": "sv-SE"}, "dark")
        payload = json.loads(html.split("const P = ", 1)[1].split(";\n", 1)[0])
        house = array("h", base64.b64decode(payload["data"]["house"]))
        assert list(house) == [425, 200]
        assert payload["capacity"] == 32.0 and 'data-theme="dark"' in html

class TestControllerSummary:
    def test_steps_add_up(self):
        import controller_check as cc

        def agg(calc, ideal, prog, ctrl, ev_calc_kr, ev_ctrl_kr):
            return {"days": 365.25, "calc": {"net": calc, "out_kwh": 0}, "ideal": {"net": ideal, "out_kwh": 0},
                    "progperf": {"net": prog, "out_kwh": 0}, "ctrl": {"net": ctrl, "out_kwh": 0},
                    "ev": {"calc_kwh": 1000.0, "calc_kr": ev_calc_kr, "ctrl_kwh": 1100.0, "ctrl_kr": ev_ctrl_kr,
                           "unmet_kwh": 0.0}, "safe_min": 0, "guard_events": 0}
        raw = {"total": agg(1000, 1000, 990, 950, 1000, 1210), "years": {}, "ev_daily_kwh": 2.7,
               "segments": 6, "base_load_kw": 3.0, "first": "a", "last": "b"}
        s = cc.summarize(raw)
        assert sum(s["steps"].values()) == pytest.approx(s["bat_diff_yr"]) == pytest.approx(-50)
        # EV: 1.00 → 1.10 kr/kWh on the calculator's 1,000 kWh = 100 kr more
        assert s["ev"]["extra_kr_yr"] == pytest.approx(100)
        assert s["total_diff_yr"] == pytest.approx(-150)
        assert s["total_diff_pct"] == pytest.approx(-15)


class TestControllerCheck:
    """The firmware planner reproduces the calculator (parity); the real controller runs the period."""

    def test_parity_with_calculator(self):
        import shutil
        import controller_check as cc
        if not (shutil.which("g++") or shutil.which("c++")):
            pytest.skip("no C++ compiler")
        from batteri import BatteryConfig, LoadSchedule
        from elpriser import load_csv
        from solar import SolarConfig
        from tariff import create_tariffs_for_operator
        rows = [r for r in load_csv(os.path.join(os.path.dirname(__file__), "historik_SE3_3ar.csv"))
                if "2024-03-01" <= r["date"] < "2024-04-01"]
        cfg = BatteryConfig(capacity_kwh=32, max_charge_kw=12.5, max_discharge_kw=12.5, fuse_amps=25,
                            base_load_kw=1.5, export_price_factor=0.0,
                            scheduled_loads=[LoadSchedule("Elbil", 11.0, 18, 7, daily_kwh=20, smart=True)])
        tf = next(x for x in create_tariffs_for_operator("Vattenfall Eldistribution") if "Tid" in x.name)
        hourly, _ = cc.calculator_hourly(rows, cfg, tf, SolarConfig(capacity_kwp=10))
        raw = cc.run_check(hourly, {"capacity_kwh": 32, "max_charge_kw": 12.5, "max_discharge_kw": 12.5,
                                    "efficiency": cfg.efficiency, "min_soc": cfg.min_soc, "max_soc": cfg.max_soc},
                           cfg.grid_max_kw, 25, solar_kwp=10)
        s = cc.summarize(raw)
        assert s["days"] == 31
        assert abs(s["steps"]["parity"]) < 0.005 * abs(s["kr"]["calc"])
        assert s["safe_min"] == 0, "the controller never fell back to its safe program"
        assert s["kr"]["ctrl"] > 0.5 * s["kr"]["calc"], s["kr"]
        assert s["ev"]["unmet_kwh_yr"] < 1
        # EV: the controller plans about the calculator's EV energy (not a full extra slot)
        assert s["ev"]["ctrl_kwh_yr"] < 1.1 * s["ev"]["calc_kwh_yr"]

    def test_translations_exist(self):
        from translations import STRINGS
        for key in ("ctrl_header", "ctrl_caption", "ctrl_button", "ctrl_notes", "ctrl_step_total",
                    "ctrl_step_controller",
                    "flow_header", "flow_solar", "flow_grid", "flow_battery", "flow_house", "flow_ev",
                    "flow_flex", "flow_export", "flow_curtailed", "flow_losses", "flow_day_from",
                    "player_header", "player_play", "player_speed_4", "player_charging"):
            assert STRINGS[key]["sv"] and STRINGS[key]["en"], key

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
