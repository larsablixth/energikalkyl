"""Tests for data import parsers and tariff holidays (no network)."""

from datetime import date

import pytest

from import_consumption import parse_consumption_csv, parse_number
from import_solar import parse_solar_csv, solar_to_hourly_dict
from import_vattenfall import _hourly_from_column, parse_vattenfall_hourly
from eon_source import _parse_measurements
from tariff import _swedish_holidays, is_peak_hour, EffektTariff


# --- 1. Decimal comma / thousands separators -------------------------------

class TestNumberParsing:
    @pytest.mark.parametrize("raw,expected", [
        ("1,5", 1.5), ("1 234,5", 1234.5), ("1\xa0234,5", 1234.5),
        ("1 234,5", 1234.5), ("1.234,5", 1234.5), ("1,234.5", 1234.5),
        ("2", 2.0), ('"0,25"', 0.25), ("-", None), ("", None), ("abc", None),
    ])
    def test_semicolon_file(self, raw, expected):
        assert parse_number(raw, comma_decimal=False, delimiter=";") == expected

    def test_late_decimal_comma_rows_not_dropped(self):
        lines = ["Datum;Förbrukning (kWh)"]
        lines += [f"2025-01-01 {h:02d}:00;2" for h in range(10)]
        lines += ["2025-01-01 10:00;1,5", "2025-01-01 11:00;1 234,5"]
        rows = parse_consumption_csv("\n".join(lines))
        assert len(rows) == 12
        assert rows[10]["consumption_kwh"] == 1.5
        assert rows[11]["consumption_kwh"] == 1234.5

    def test_solar_late_decimal_comma(self):
        lines = ["Datum;Tid;Energi (kWh)"]
        lines += [f"2025-06-01;{h:02d}:00;0" for h in range(8)]
        lines += ["2025-06-01;08:00;1,5"]
        recs = parse_solar_csv("\n".join(lines))
        assert solar_to_hourly_dict(recs)["2025-06-01 08:00"] == 1.5


# --- 2. Solar column selection and units ------------------------------------

class TestSolarColumns:
    def test_prefers_energy_over_power_column(self):
        csv = ("Timestamp,Power (W),Energy (kWh)\n"
               "2025-06-01 12:00,4000,4.1\n"
               "2025-06-01 13:00,3000,3.2\n")
        d = solar_to_hourly_dict(parse_solar_csv(csv))
        assert d == {"2025-06-01 12:00": 4.1, "2025-06-01 13:00": 3.2}

    def test_power_in_watts_averaged_per_hour(self):
        csv = ("Timestamp;Effekt (W)\n"
               "2025-06-01 12:00;4000\n2025-06-01 12:15;2000\n"
               "2025-06-01 12:30;4000\n2025-06-01 12:45;2000\n")
        d = solar_to_hourly_dict(parse_solar_csv(csv))
        assert d == {"2025-06-01 12:00": pytest.approx(3.0)}

    def test_subhourly_energy_summed(self):
        csv = ("Timestamp;Energy (kWh)\n"
               "2025-06-01 12:00;0,5\n2025-06-01 12:15;0,5\n"
               "2025-06-01 12:30;0,5\n2025-06-01 12:45;0,5\n")
        d = solar_to_hourly_dict(parse_solar_csv(csv))
        assert d == {"2025-06-01 12:00": pytest.approx(2.0)}

    def test_wh_energy_converted(self):
        csv = "Timestamp;Yield (Wh)\n2025-06-01 12:00;2500\n"
        d = solar_to_hourly_dict(parse_solar_csv(csv))
        assert d == {"2025-06-01 12:00": pytest.approx(2.5)}


# --- 3. E.ON parsing ---------------------------------------------------------

class TestEon:
    def test_zero_value_kept_and_utc_converted(self):
        data = {"values": [
            {"timestamp": "2025-01-15T10:00:00Z", "value": 0.0, "consumption": 9.9},
            {"timestamp": "2025-07-15T10:00:00Z", "value": 1.2},
            {"timestamp": "2025-01-15T23:00:00Z", "consumption": 0.7},
        ]}
        nodes = _parse_measurements(data)
        assert nodes[0] == {"date": "2025-01-15", "hour": 11, "kwh": 0.0}  # CET
        assert nodes[1]["hour"] == 12  # CEST
        assert nodes[2] == {"date": "2025-01-16", "hour": 0, "kwh": 0.7}


# --- 4. Vattenfall hourly layout ---------------------------------------------

def _by_key(records):
    return {(r["date"], r["hour"]): r["kwh"] for r in records}


class TestVattenfallHourly:
    def test_plain_month_with_label_row(self):
        cells = ["Jan"] + [float(i) for i in range(31 * 24)]
        recs = _by_key(_hourly_from_column(2025, 1, cells))
        assert len(recs) == 744
        assert recs[("2025-01-01", 0)] == 0.0
        assert recs[("2025-01-31", 23)] == 743.0

    def test_blank_cell_skips_hour_without_shift(self):
        cells = [None] + [1.0] * (31 * 24)
        cells[1 + 5] = None  # 2025-01-01 05:00 missing
        recs = _by_key(_hourly_from_column(2025, 1, cells))
        assert len(recs) == 743
        assert ("2025-01-01", 5) not in recs
        assert recs[("2025-01-31", 23)] == 1.0

    def test_march_23_hour_day(self):
        n = 31 * 24 - 1
        cells = [float(i) for i in range(n)]  # row 3 is already hour 0
        recs = _by_key(_hourly_from_column(2025, 3, cells, skip_first=False))
        assert len(recs) == n
        assert ("2025-03-30", 2) not in recs
        assert recs[("2025-03-30", 3)] == 29 * 24 + 2
        assert recs[("2025-03-31", 23)] == n - 1

    def test_october_25_hour_day_keeps_first_hour(self):
        n = 31 * 24 + 1
        cells = [1.0] * n
        recs = _by_key(_hourly_from_column(2025, 10, cells))
        assert recs[("2025-10-01", 0)] == 1.0
        assert recs[("2025-10-26", 2)] == 2.0  # 02:00 twice → summed
        assert len(recs) == 744
        assert sum(recs.values()) == pytest.approx(n)

    def test_october_with_leading_summary_value(self):
        cells = [99.0] + [1.0] * (31 * 24 + 1)
        recs = _by_key(_hourly_from_column(2025, 10, cells, skip_first=True))
        assert recs[("2025-10-01", 0)] == 1.0
        assert sum(recs.values()) == pytest.approx(745)

    def test_workbook_roundtrip(self, tmp_path):
        openpyxl = pytest.importorskip("openpyxl")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Serie"
        ws.cell(1, 1, 2025)
        days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        for m in range(12):
            n = days[m] * 24 + (-1 if m == 2 else 1 if m == 9 else 0)
            ws.cell(3, 12 + m, "kWh")
            for i in range(n):
                ws.cell(4 + i, 12 + m, 1.0)
        path = tmp_path / "vf.xlsx"
        wb.save(path)
        recs = parse_vattenfall_hourly(str(path))
        assert len({r["date"] for r in recs}) == 365
        assert sum(r["kwh"] for r in recs) == pytest.approx(8760)


# --- 6. Swedish holidays -------------------------------------------------------

class TestHolidays:
    def test_2026_holidays(self):
        h = _swedish_holidays(2026)
        for d in [date(2026, 1, 1), date(2026, 1, 6), date(2026, 4, 3),
                  date(2026, 4, 6), date(2026, 5, 1), date(2026, 5, 14),
                  date(2026, 6, 6), date(2026, 6, 19), date(2026, 12, 24),
                  date(2026, 12, 25), date(2026, 12, 26), date(2026, 12, 31)]:
            assert d in h, d

    @pytest.mark.parametrize("year,expected", [
        (2025, date(2025, 6, 20)), (2027, date(2027, 6, 25)), (2028, date(2028, 6, 23)),
    ])
    def test_midsommarafton_is_friday(self, year, expected):
        assert expected in _swedish_holidays(year)
        assert expected.weekday() == 4

    def test_kristi_himmelsfard_2025(self):
        assert date(2025, 5, 29) in _swedish_holidays(2025)

    def test_year_round_effekt_tariff_skips_may_first(self):
        tariff = EffektTariff(peak_months=None, peak_weekday_only=True,
                              peak_hour_start=7, peak_hour_end=19)
        assert not tariff.is_peak_hour("2026-05-01", "10:00")  # Friday, 1 maj
        assert tariff.is_peak_hour("2026-05-04", "10:00")      # ordinary Monday

    def test_tidstariff_unchanged_in_winter(self):
        assert is_peak_hour("2026-01-07", "10:00")
        assert not is_peak_hour("2026-01-06", "10:00")
