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


# --- 7. Universal consumption import (parse_any_consumption_file) -------------
# Synthetic fixtures for every supported layout. Layouts marked VERIFIED match
# public sources (see import_consumption.py header); the rest are assumed.

import io as _io
import json as _json
from datetime import datetime as _dt, time as _tm, timedelta as _td, timezone as _tz

from import_consumption import (
    ConsumptionParseError, consumption_to_hourly_profile, consumption_to_monthly_daily,
    load_consumption_file, parse_any_consumption_file, rows_to_hourly,
)


def _parse(text, name="f.csv", encoding="utf-8"):
    return parse_any_consumption_file(name, text.encode(encoding) if isinstance(text, str) else text)


def _total(rows):
    return round(sum(r["consumption_kwh"] for r in rows), 4)


def _hours(rows, day):
    return [r["hour"] for r in rows if r["date"] == day]


class TestAnyLongLayouts:
    def test_datetime_column_with_metadata_rows(self):
        txt = ("Anläggnings-ID;735999100000000000\nMätpunkt;Elnät\n\n"
               "Datum;Förbrukning (kWh)\n"
               + "\n".join(f"2025-01-01 {h:02d}:00;1,{h % 10}" for h in range(24)))
        rows, info = _parse(txt)
        assert info["format"] == "long" and info["resolution_min"] == 60
        assert len(rows) == 24 and rows[3]["consumption_kwh"] == 1.3

    def test_date_and_time_split(self):
        txt = "Datum;Tid;Förbrukning\n" + "\n".join(f"2025-02-03;{h:02d}:00;0,5" for h in range(24))
        rows, _ = _parse(txt)
        assert _hours(rows, "2025-02-03") == [f"{h:02d}:00" for h in range(24)]
        assert _total(rows) == 12

    def test_fran_till_columns(self):
        txt = "Från;Till;Mängd;Enhet\n" + "\n".join(
            f"2025-01-01 {h:02d}:00;2025-01-01 {h:02d}:59;2;kWh" for h in range(24))
        rows, _ = _parse(txt)
        assert rows[0]["hour"] == "00:00" and _total(rows) == 48

    def test_till_only_column_shifts_to_interval_start(self):
        txt = "Till;Förbrukning kWh\n" + "\n".join(
            f"2025-01-01 {h:02d}:00;1" for h in range(1, 24))
        rows, _ = _parse(txt)
        assert rows[0]["hour"] == "00:00" and rows[-1]["hour"] == "22:00"

    def test_greenely_style_comma_csv_quoted_decimals(self):
        txt = "Tid,Elanvändning (kWh)\n" + "\n".join(f'2025-01-01 {h:02d}:00,"1,25"' for h in range(24))
        rows, _ = _parse(txt)
        assert _total(rows) == 30

    def test_quarter_hours_cost_columns_ignored(self):
        # Mälarenergi-like (second-hand): Kvart;Förbrukning;Kostnad;Kostnad, elnät
        txt = "Kvart;Förbrukning;Kostnad;Kostnad, elnät\n" + "\n".join(
            f"2025-01-01 {q // 4:02d}:{q % 4 * 15:02d};0,25;9,99;3,33" for q in range(96))
        rows, info = _parse(txt)
        assert info["resolution_min"] == 15 and len(rows) == 96
        assert _total(rows) == 24
        hourly = rows_to_hourly(rows)
        assert len(hourly) == 24 and hourly[5]["kwh"] == pytest.approx(1.0)

    def test_hour_ending_numbering_1_to_24(self):
        txt = "Datum;Timme;Förbrukning kWh\n" + "\n".join(f"2025-01-01;{h};{h}" for h in range(1, 25))
        rows, _ = _parse(txt)
        assert rows[0] == {"date": "2025-01-01", "hour": "00:00", "consumption_kwh": 1.0}
        assert rows[-1]["hour"] == "23:00" and rows[-1]["consumption_kwh"] == 24

    def test_newest_first_file(self):
        txt = "Datum;Förbrukning\n" + "\n".join(f"2025-01-01 {h:02d}:00;{h + 1}" for h in reversed(range(24)))
        rows, _ = _parse(txt)
        assert rows[0]["hour"] == "00:00" and rows[0]["consumption_kwh"] == 1

    def test_european_dates(self):
        txt = "Datum;Förbrukning\n" + "\n".join(f"13.01.2025 {h:02d}:00;1" for h in range(24))
        rows, _ = _parse(txt)
        assert rows[0]["date"] == "2025-01-13"


class TestAnyUnitsAndTime:
    def test_wh_header_converted(self):
        txt = "Tidpunkt;Energi (Wh)\n" + "\n".join(f"2025-01-01 {h:02d}:00;1500" for h in range(24))
        rows, _ = _parse(txt)
        assert rows[0]["consumption_kwh"] == 1.5

    def test_unit_column_wh(self):
        txt = "Datum;Värde;Enhet\n" + "\n".join(f"2025-01-01 {h:02d}:00;800;Wh" for h in range(24))
        rows, _ = _parse(txt)
        assert rows[0]["consumption_kwh"] == 0.8

    def test_utc_z_timestamps_autumn_dst(self):
        # Local 2025-10-26 has 25 hours: 22:00Z on the 25th .. 22:00Z on the 26th
        start = _dt(2025, 10, 25, 22, tzinfo=_tz.utc)
        lines = ["timestamp,consumption_kwh"] + [
            f"{(start + _td(hours=i)).strftime('%Y-%m-%dT%H:%M:%SZ')},1.0" for i in range(25)]
        rows, _ = _parse("\n".join(lines))
        assert {r["date"] for r in rows} == {"2025-10-26"}
        assert _hours(rows, "2025-10-26")[:5] == ["00:00", "01:00", "02:00", "02:00", "03:00"]
        assert rows_to_hourly(rows)[2]["kwh"] == 2.0

    def test_offset_timestamps_converted(self):
        lines = ["from;consumption"] + [f"2025-06-01T{h:02d}:00:00+00:00;1" for h in range(3)]
        rows, _ = _parse("\n".join(lines) + "\n2025-06-01T03:00:00+00:00;1")
        assert rows[0] == {"date": "2025-06-01", "hour": "02:00", "consumption_kwh": 1.0}  # CEST = UTC+2

    def test_naive_local_autumn_repeated_hour(self):
        hours = [0, 1, 2, 2] + list(range(3, 24))
        txt = "Datum;Tid;kWh\n" + "\n".join(f"2025-10-26;{h:02d}:00;1" for h in hours)
        rows, _ = _parse(txt)
        assert len(rows) == 25 and _total(rows) == 25

    def test_naive_local_spring_23_hours(self):
        txt = "Datum;Tid;kWh\n" + "\n".join(f"2025-03-30;{h:02d}:00;1" for h in range(24) if h != 2)
        rows, _ = _parse(txt)
        assert len(rows) == 23 and "02:00" not in _hours(rows, "2025-03-30")


class TestAnyWide:
    def _wide(self, header, rows):
        return "\n".join([";".join(header)] + [";".join(r) for r in rows])

    def test_24_columns_with_sum_and_dst_days(self):
        hdr = ["Datum"] + [f"{h:02d}-{h + 1:02d}" for h in range(24)] + ["02-03 (2)", "Summa"]
        normal = ["2025-01-01"] + ["1"] * 24 + ["", "24"]
        spring = ["2025-03-30", "1", "1", ""] + ["1"] * 21 + ["", "23"]
        autumn = ["2025-10-26"] + ["1"] * 25 + ["25"]
        rows, info = _parse(self._wide(hdr, [normal, spring, autumn]))
        assert info["format"] == "wide"
        assert len(_hours(rows, "2025-01-01")) == 24
        assert len(_hours(rows, "2025-03-30")) == 23 and "02:00" not in _hours(rows, "2025-03-30")
        assert _hours(rows, "2025-10-26").count("02:00") == 2
        assert _total(rows) == 72

    def test_hour_ending_numbered_columns_wh_in_metadata(self):
        txt = "Enhet: Wh\n" + self._wide(["Datum"] + [str(h) for h in range(1, 25)],
                                         [["2025-01-02"] + ["500"] * 24])
        rows, _ = _parse(txt)
        assert rows[0]["hour"] == "00:00" and _total(rows) == 12

    def test_96_quarter_columns(self):
        hdr = ["Datum"] + [f"{q * 15 // 60:02d}:{q * 15 % 60:02d}" for q in range(96)]
        rows, info = _parse(self._wide(hdr, [["2025-01-01"] + ["0,1"] * 96]))
        assert info["resolution_min"] == 15 and len(rows) == 96
        assert consumption_to_hourly_profile(rows)[7] == pytest.approx(0.4)


class TestAnyMeterReadings:
    def test_hourly_meter_readings_differenced(self):
        txt = "Datum;Mätarställning (kWh)\n" + "\n".join(
            f"2025-01-01 {h:02d}:00;{12000 + h * 1.5:.1f}".replace(".", ",") for h in range(25 - 1))
        rows, info = _parse(txt)
        assert info["format"] == "meter"
        assert len(rows) == 23 and all(r["consumption_kwh"] == 1.5 for r in rows)

    def test_meter_gap_is_missing_not_zero_or_lumped(self):
        hrs = [h for h in range(24) if h not in (5, 6, 7, 8)]  # 5 h gap > 3 h limit
        txt = "Datum;Mätarställning\n" + "\n".join(f"2025-01-01 {h:02d}:00;{1000 + h}" for h in hrs)
        rows, _ = _parse(txt)
        assert all(r["consumption_kwh"] == 1.0 for r in rows)
        assert "04:00" not in _hours(rows, "2025-01-01")

    def test_unlabelled_cumulative_detected(self):
        txt = "Tid;Värde\n" + "\n".join(f"2025-01-0{1 + h // 24} {h % 24:02d}:00;{54321 + h * 2}" for h in range(72))
        rows, info = _parse(txt)
        assert info["format"] == "meter" and _total(rows) == 142

    def test_meter_across_autumn_dst(self):
        start = _dt(2025, 10, 25, 22, tzinfo=_tz.utc)
        lines = ["time,meter reading kWh"] + [
            f"{(start + _td(hours=i)).isoformat()},{100 + i}" for i in range(26)]
        rows, _ = _parse("\n".join(lines))
        assert _total(rows) == 25 and len(_hours(rows, "2025-10-26")) == 25


def _ha_history(entities, start=_dt(2025, 1, 1, tzinfo=_tz.utc)):
    lines = ["entity_id,state,last_changed"]
    for ent, samples in entities.items():
        for minutes, state in samples:
            ts = (start + _td(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            lines.append(f"{ent},{state},{ts}")
    return "\n".join(lines)


class TestHomeAssistant:
    def test_history_cumulative_irregular_and_unavailable(self):
        # VERIFIED layout (HA frontend): entity_id,state,last_changed (UTC ISO)
        samples = [(m, f"{5000 + m / 60:.4f}") for m in range(0, 24 * 60 + 1, 7)]
        samples.insert(10, (71, "unavailable"))
        samples.insert(20, (141, "unknown"))
        rows, info = _parse(_ha_history({"sensor.house_energy_total": samples}), "history.csv")
        assert info["format"] == "ha_history"
        hourly = rows_to_hourly(rows)
        # 2025-01-01 00:00 UTC = 01:00 local
        assert hourly[0] == {"date": "2025-01-01", "hour": 1, "kwh": pytest.approx(1.0, abs=0.01)}
        assert all(h["kwh"] == pytest.approx(1.0, abs=0.01) for h in hourly)

    def test_history_picks_consumption_entity_and_detects_wh(self):
        hist = _ha_history({
            "sensor.solar_export_energy": [(m * 60, 100 + m * 3) for m in range(48)],
            "sensor.grid_import_energy": [(m * 60, 2_000_000 + m * 1200) for m in range(48)],
        })
        rows, info = _parse(hist, "history.csv")
        assert info["detail"] == "sensor.grid_import_energy"
        assert all(r["consumption_kwh"] == pytest.approx(1.2) for r in rows)

    def test_history_meter_reset_continues(self):
        vals = [10, 11, 12, 0.5, 1.5, 2.5]
        rows, _ = _parse(_ha_history({"sensor.daily_energy": [(i * 60, v) for i, v in enumerate(vals)]}))
        assert [r["consumption_kwh"] for r in rows] == [1, 1, 0.5, 1, 1]

    def test_history_power_sensor_integrated(self):
        samples = [(0, 1000), (30, 3000), (60, 2000), (120, 2000)]
        rows, info = _parse(_ha_history({"sensor.house_power": samples}))
        assert info["format"] == "ha_history_power"
        assert [r["consumption_kwh"] for r in rows] == [2.0, 2.0]

    def test_statistics_sum_state_tsv(self):
        # VERIFIED layout (klausj1/homeassistant-statistics README)
        lines = ["statistic_id\tstart\tunit\tsum\tstate"] + [
            f"sensor.energy\t01.01.2025 {h:02d}:00\tkWh\t{h * 2}\t{500 + h * 2}" for h in range(24)]
        rows, info = _parse("\n".join(lines), "stats.tsv")
        assert info["format"] == "ha_statistics"
        # sum at row 'start' = total at end of that hour → first hour has no baseline
        assert rows[0] == {"date": "2025-01-01", "hour": "01:00", "consumption_kwh": 2.0}
        assert len(rows) == 23

    def test_statistics_delta_wh(self):
        lines = ["statistic_id,start,unit,delta"] + [
            f"sensor.energy,2025-01-01 {h:02d}:00,Wh,750" for h in range(24)]
        rows, _ = _parse("\n".join(lines))
        assert rows[0]["hour"] == "00:00" and _total(rows) == 18

    def test_statistics_mean_power_and_epoch(self):
        base = int(_dt(2025, 1, 1, tzinfo=_tz.utc).timestamp())
        lines = ["statistic_id,start_ts,unit,mean"] + [
            f"sensor.power,{base + h * 3600},W,1500" for h in range(5)]
        rows, _ = _parse("\n".join(lines))
        assert rows[0] == {"date": "2025-01-01", "hour": "01:00", "consumption_kwh": 1.5}


class TestAnyContainers:
    def test_cp1252_and_utf16(self):
        txt = "Datum;Förbrukning (kWh)\n" + "\n".join(f"2025-01-01 {h:02d}:00;1" for h in range(24))
        assert len(_parse(txt, encoding="cp1252")[0]) == 24
        assert len(_parse(b"\xff\xfe" + txt.encode("utf-16-le"))[0]) == 24

    def test_xlsx_long_on_second_sheet_with_datetime_cells(self):
        openpyxl = pytest.importorskip("openpyxl")
        wb = openpyxl.Workbook()
        wb.active.title = "Översikt"
        wb.active.append(["Total", 999])
        ws = wb.create_sheet("Kvartsvärden")
        ws.append(["Mätpunkt 735999"])
        ws.append([])
        ws.append(["Från", "Till", "Förbrukning (kWh)"])
        t0 = _dt(2025, 1, 1)
        for q in range(96 * 2):
            ws.append([t0 + _td(minutes=15 * q), t0 + _td(minutes=15 * q + 15), 0.3])
        buf = _io.BytesIO()
        wb.save(buf)
        rows, info = parse_any_consumption_file("export.xlsx", buf.getvalue())
        assert info["container"] == "Excel" and info["resolution_min"] == 15
        assert len(rows) == 192 and _total(rows) == pytest.approx(57.6)

    def test_xlsx_wide_with_time_headers(self):
        openpyxl = pytest.importorskip("openpyxl")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Datum"] + [_tm(h, 0) for h in range(24)])
        ws.append([_dt(2025, 1, 1)] + [1.25] * 24)
        buf = _io.BytesIO()
        wb.save(buf)
        rows, info = parse_any_consumption_file("w.xlsx", buf.getvalue())
        assert info["format"] == "wide" and _total(rows) == 30

    def test_vattenfall_excel_routed(self):
        openpyxl = pytest.importorskip("openpyxl")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Serie"
        ws.cell(1, 1, 2025)
        for i in range(31 * 24):
            ws.cell(4 + i, 12, 0.5)
        buf = _io.BytesIO()
        wb.save(buf)
        rows, info = parse_any_consumption_file("Vattenfall.xlsx", buf.getvalue())
        assert info["format"] == "vattenfall_excel" and len(rows) == 744

    def test_json_tibber_nodes_and_day_lists(self):
        tib = {"data": {"viewer": {"homes": [{"consumption": {"nodes": [
            {"from": f"2025-01-01T{h:02d}:00:00.000+01:00", "to": "", "cost": 3.0,
             "unitPrice": 1.2, "consumption": 1.1} for h in range(24)]}}]}}}
        rows, info = _parse(_json.dumps(tib), "tibber.json")
        assert info["container"] == "JSON" and _total(rows) == pytest.approx(26.4)
        days = {"consumption": {"2025-01-01": [1] * 24, "2025-01-02": [2] * 24}}
        rows, info = _parse(_json.dumps(days), "export.json")
        assert info["format"] == "wide" and _total(rows) == 72

    def test_load_consumption_file_path(self, tmp_path):
        p = tmp_path / "x.csv"
        p.write_text("Datum;Tid;kWh\n" + "\n".join(f"2025-01-01;{h:02d}:00;1" for h in range(24)),
                     encoding="cp1252")
        assert len(load_consumption_file(str(p))) == 24


class TestAnyErrors:
    def test_daily_only(self):
        txt = "Datum;Förbrukning\n" + "\n".join(f"2025-01-{d:02d};30" for d in range(1, 20))
        with pytest.raises(ConsumptionParseError) as e:
            _parse(txt)
        assert e.value.reason == "daily_only"

    def test_no_time_lists_columns(self):
        with pytest.raises(ConsumptionParseError) as e:
            _parse("Namn;Värde\nfoo;1\nbar;2")
        assert e.value.reason == "no_time" and e.value.columns == ["Namn", "Värde"]

    def test_only_cost_columns(self):
        txt = "Datum;Kostnad (kr)\n" + "\n".join(f"2025-01-01 {h:02d}:00;3" for h in range(24))
        with pytest.raises(ConsumptionParseError) as e:
            _parse(txt)
        assert e.value.reason == "no_value"

    def test_all_zero_is_an_error(self):
        txt = "Datum;Förbrukning\n" + "\n".join(f"2025-01-01 {h:02d}:00;0" for h in range(24))
        with pytest.raises(ConsumptionParseError) as e:
            _parse(txt)
        assert e.value.reason == "all_zero"

    def test_old_xls(self):
        with pytest.raises(ConsumptionParseError) as e:
            parse_any_consumption_file("a.xls", b"\xd0\xcf\x11\xe0" + b"\0" * 100)
        assert e.value.reason == "xls_old"


class TestProfilesSubHourly:
    def test_hourly_profile_sums_quarters(self):
        rows = [{"date": f"2025-01-0{d}", "hour": f"{h:02d}:{m:02d}", "consumption_kwh": 0.25}
                for d in (1, 2) for h in range(24) for m in (0, 15, 30, 45)]
        prof = consumption_to_hourly_profile(rows)
        assert all(v == pytest.approx(1.0) for v in prof.values())
        assert consumption_to_monthly_daily(rows)[1] == pytest.approx(24.0)

    def test_hourly_profile_unchanged_for_hourly(self):
        rows = [{"date": "2025-01-01", "hour": f"{h:02d}:00", "consumption_kwh": h} for h in range(24)]
        assert consumption_to_hourly_profile(rows)[5] == 5
