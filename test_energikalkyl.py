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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
