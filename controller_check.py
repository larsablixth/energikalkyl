"""
Controller check and energy flows for the recommended battery (pure, no Streamlit).

Controller check: the calculator assumes a battery that does exactly what the
day-ahead plan says. A real controller (the NORVI controller firmware, copied
into controller/ by controller/sync.sh) has to express the plan as a Deye
inverter program of at most six points per day, shares the fuse with the EV
and keeps a reserve for the house, and plans from a forecast instead of the
actual day. run_check() sends the calculator's own hourly inputs through the
firmware's planner, one day at a time, in a separate process
(controller/check_main.cpp) and summarize() turns the result into kr/yr steps:

    calculator → firmware planner, same inputs (parity, ≈ 0)
               → Deye program (≤ 6 points per day)
               → EV + fuse budget (EV planned by the controller, house reserve)
               → forecast (yesterday's load and solar)

The same check runs in the energy-scheduler-sim repository ("Validate
calculator"), which also simulates the inverter's physics and the fuse guard;
that last step is not part of this check.

Energy flows: calculator_hourly() gives the recommended battery's hourly
values (also used by the "Export for simulator" JSON), energy_flows() the
yearly flows between sun, grid, battery and the loads, day_flows() one day.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from batteri import simulate

CONTROLLER_DIR = Path(__file__).resolve().parent / "controller"
BUILD_DIR = Path(os.environ.get("ENERGIKALKYL_CONTROLLER_BUILD",
                                Path(__file__).resolve().parent / ".controller_build"))
COMPILE_TIMEOUT_S = 300
RUN_TIMEOUT_S = 300

# Order of the chains in the check program's output
CHAINS = ("calc", "ideal", "progperf", "ctrlperf", "ctrlmodel")
EV_MODES = {"battery": 0, "ev": 1, "auto": 2}


class ControllerUnavailable(RuntimeError):
    """The check can't run here (no C++ compiler, or the build failed)."""


# ── Build ──────────────────────────────────────────────────────────────────

def _sources() -> list[Path]:
    files = sorted(p for p in CONTROLLER_DIR.rglob("*") if p.suffix in (".cpp", ".h"))
    if not files:
        raise ControllerUnavailable("controller/ has no sources")
    return files


def firmware_version() -> str:
    """The firmware commit the copied planner comes from (controller/VERSION)."""
    try:
        for line in (CONTROLLER_DIR / "VERSION").read_text().splitlines():
            if line.startswith("firmware "):
                return line.split()[1][:7]
    except OSError:
        pass
    return "?"


def binary_path() -> Path:
    h = hashlib.sha256()
    for p in _sources():
        h.update(p.relative_to(CONTROLLER_DIR).as_posix().encode())
        h.update(p.read_bytes())
    return BUILD_DIR / f"controller_check-{h.hexdigest()[:12]}"


def build_binary() -> Path:
    """Compile controller/ once (cached per source hash). Raises ControllerUnavailable."""
    out = binary_path()
    if out.exists():
        return out
    cxx = os.environ.get("CXX") or shutil.which("g++") or shutil.which("c++") or shutil.which("clang++")
    if not cxx:
        raise ControllerUnavailable("no C++ compiler (g++) installed")
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    srcs = ([CONTROLLER_DIR / "sim" / "batch.cpp"]
            + sorted((CONTROLLER_DIR / "firmware" / "src").glob("*.cpp"))
            + [CONTROLLER_DIR / "check_main.cpp"])
    fd, tmp = tempfile.mkstemp(prefix=out.name + ".", dir=BUILD_DIR)
    os.close(fd)
    cmd = [cxx, "-std=c++14", "-O2", "-w",
           "-include", str(CONTROLLER_DIR / "sim" / "sim_overrides.h"),
           "-I", str(CONTROLLER_DIR / "sim"), "-I", str(CONTROLLER_DIR / "firmware" / "include"),
           "-o", tmp] + [str(s) for s in srcs]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=COMPILE_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as e:
        Path(tmp).unlink(missing_ok=True)
        raise ControllerUnavailable(f"compile failed: {e}") from e
    if r.returncode != 0:
        Path(tmp).unlink(missing_ok=True)
        raise ControllerUnavailable("compile failed: " + (r.stderr or r.stdout)[-500:])
    os.chmod(tmp, 0o755)
    os.replace(tmp, out)          # atomic: parallel sessions never see a half-written binary
    return out


# ── Hourly values of the calculator ───────────────────────────────────────

HOURLY_KEYS = ("hour", "spot", "buy_ore", "load_kw", "ev_kw", "solar_kw", "room_kw",
               "in_kwh", "out_kwh", "solar_in_kwh", "export_kwh", "flex_kwh", "soc_before_kwh", "soc_kwh",
               "net_sek")


def calculator_hourly(price_rows, cfg, tariff, solar=None):
    """Simulate the battery once and return ({date: {key: [per hour]}}, result).

    One simulate() call also refreshes the config's smart-load (EV) schedule for
    this tariff (the tariff sweep leaves the last tariff's schedule behind), so
    the EV kW per hour matches the result. in_kwh = grid charging, out_kwh =
    delivered by the battery, solar_in_kwh = solar charged into the battery,
    soc_before_kwh / soc_kwh = stored energy at the start / end of the hour.
    """
    r = simulate(price_rows, cfg, tariff=tariff, solar=solar)
    hourly: dict[str, dict[str, list]] = {}
    for s in r.slots:
        h = int(s.hour.split(":")[0])
        m = int(s.date.split("-")[1])
        ev = sum(cfg._scheduled_kw(i, sl, h, s.date) for i, sl in enumerate(cfg.scheduled_loads))
        row = (h, round(s.sek_per_kwh, 5), round(s.total_cost_ore, 3),
               round(cfg.total_load_kw(h, m, s.date), 4), round(ev, 4),
               round(s.solar_kw, 4), round(cfg.available_charge_kw(h, m, s.date), 4),
               round(s.energy_kwh, 4) if s.action == "charge" else 0.0,
               round(s.energy_kwh, 4) if s.action == "discharge" else 0.0,
               round(s.solar_charge_kwh, 4), round(s.grid_export_kwh, 4),
               round(s.flex_consumed_kwh, 4), round(s.soc_before, 4), round(s.soc_after, 4),
               round(s.saving_sek - s.cost_sek + s.export_revenue_sek, 4))
        d = hourly.setdefault(s.date, {k: [] for k in HOURLY_KEYS})
        for k, v in zip(HOURLY_KEYS, row):
            d[k].append(v)
    return hourly, r


# ── Controller check ──────────────────────────────────────────────────────

def run_check(hourly, battery, grid_max_kw, ev_window=(18, 7), ev_mode=None, persistence=True):
    """Run the firmware planner on the calculator's hourly inputs.

    battery: capacity_kwh, max_charge_kw, max_discharge_kw, efficiency, min_soc,
    max_soc (fractions 0-1). ev_mode: "battery" / "ev" / "auto" / None (firmware
    default). Returns the check program's JSON (sums over the period and per year).
    Raises ControllerUnavailable.
    """
    exe = build_binary()
    lines = ["P %g %g %g %g %g %g %g %d %d %d %d" % (
        battery["capacity_kwh"], battery["max_charge_kw"], battery["max_discharge_kw"],
        battery["efficiency"], battery["min_soc"] * 100, battery["max_soc"] * 100, grid_max_kw,
        int(ev_window[0]), int(ev_window[1]), EV_MODES.get(ev_mode, -1), 1 if persistence else 0)]
    for date in sorted(hourly):
        h = hourly[date]
        lines.append(f"D {date} {len(h['hour'])}")
        for i in range(len(h["hour"])):
            lines.append("R %g %g %g %g %g %g %g %g" % (
                h["spot"][i], h["buy_ore"][i] / 100, h["load_kw"][i], h["ev_kw"][i], h["solar_kw"][i],
                h["net_sek"][i], h["in_kwh"][i], h["out_kwh"][i]))
    try:
        r = subprocess.run([str(exe)], input="\n".join(lines) + "\n", capture_output=True, text=True,
                           timeout=RUN_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ControllerUnavailable(f"check failed: {e}") from e
    if r.returncode != 0:
        raise ControllerUnavailable(f"check failed (exit {r.returncode}): {(r.stderr or r.stdout)[-300:]}")
    return json.loads(r.stdout)


def summarize(raw) -> dict:
    """kr/yr per chain, the steps between them, EV cost and battery + EV combined.

    Battery chains count battery money only (discharge value − charge cost).
    The controller charges the EV in its own hours, so the EV's charging cost is
    compared at the calculator's EV energy (controller kr/kWh × calculator kWh)
    and added to the battery difference: total_diff_yr < 0 means the controller
    does worse than the calculator.
    """
    def per_year(v, days):
        return v / days * 365.25 if days > 0 else 0.0

    def block(a):
        d = a["days"]
        kr = {k: per_year(a[k]["net"], d) for k in CHAINS}
        ev = a["ev"]
        calc_per = ev["calc_kr"] / ev["calc_kwh"] if ev["calc_kwh"] > 0 else 0.0
        ctrl_per = ev["ctrl_kr"] / ev["ctrl_kwh"] if ev["ctrl_kwh"] > 0 else 0.0
        ev_extra = per_year(ev["calc_kwh"] * (ctrl_per - calc_per), d) if ev["calc_kwh"] > 0 else 0.0
        bat_diff = kr["ctrlmodel"] - kr["calc"]
        total = bat_diff - ev_extra
        return {
            "days": d, "kr": kr,
            "steps": {"parity": kr["ideal"] - kr["calc"], "program": kr["progperf"] - kr["ideal"],
                      "ev_fuse": kr["ctrlperf"] - kr["progperf"], "forecast": kr["ctrlmodel"] - kr["ctrlperf"]},
            "ev": {"calc_kwh_yr": per_year(ev["calc_kwh"], d), "ctrl_kwh_yr": per_year(ev["ctrl_kwh"], d),
                   "calc_kr_kwh": calc_per, "ctrl_kr_kwh": ctrl_per, "extra_kr_yr": ev_extra},
            "bat_diff_yr": bat_diff,
            "total_diff_yr": total,
            "total_diff_pct": 100.0 * total / abs(kr["calc"]) if abs(kr["calc"]) > 1e-9 else 0.0,
        }

    out = block(raw["total"])
    out["years"] = {y: block(a) for y, a in raw.get("years", {}).items()}
    out["period"] = (raw.get("first"), raw.get("last"))
    out["ev_daily_kwh"] = raw.get("ev_daily_kwh", 0.0)
    out["segments"] = raw.get("segments")
    out["base_load_kw"] = raw.get("base_load_kw")
    return out


# ── Energy flows ──────────────────────────────────────────────────────────

FLOW_SOURCES = ("solar", "grid", "battery")
FLOW_SINKS = ("house", "ev", "battery", "flex", "export", "curtailed", "losses")


def _hour_flows(h, i):
    """Flows (kWh) of one hour: {(source, sink): kWh}."""
    load, ev, solar = h["load_kw"][i], h["ev_kw"][i], h["solar_kw"][i]
    flex = h.get("flex_kwh", [0.0] * len(h["hour"]))[i]
    s_bat, g_bat, out = h["solar_in_kwh"][i], h["in_kwh"][i], h["out_kwh"][i]
    direct = min(solar, load)
    b_load = min(out, max(0.0, load - direct))
    b_grid = max(0.0, out - b_load)                       # battery export (export mode only)
    s_exp = max(0.0, h["export_kwh"][i] - b_grid)
    s_curt = max(0.0, solar - direct - s_bat - flex - s_exp)
    g_load = max(0.0, load - direct - b_load)
    ev_share = ev / load if load > 1e-9 else 0.0
    f = {}
    for src, kwh in (("solar", direct), ("battery", b_load), ("grid", g_load)):
        f[(src, "ev")] = kwh * ev_share
        f[(src, "house")] = kwh * (1 - ev_share)
    f[("solar", "battery")] = s_bat
    f[("solar", "flex")] = flex
    f[("solar", "export")] = s_exp
    f[("solar", "curtailed")] = s_curt
    f[("grid", "battery")] = g_bat
    f[("battery", "export")] = b_grid
    return f


def energy_flows(hourly) -> dict:
    """Average yearly flows (kWh/yr) between sources and sinks.

    Returns {"links": {(source, sink): kWh/yr}, "days": n}. Battery losses =
    energy in − energy out − change of the stored energy over the period.
    Loads are split into house and EV by the EV's share of each hour's load.
    """
    tot: dict[tuple, float] = {}
    days = len(hourly)
    first_soc = last_soc = None
    for date in sorted(hourly):
        h = hourly[date]
        for i in range(len(h["hour"])):
            for k, v in _hour_flows(h, i).items():
                tot[k] = tot.get(k, 0.0) + v
        if h.get("soc_kwh") and h.get("soc_before_kwh"):
            if first_soc is None:
                first_soc = h["soc_before_kwh"][0]
            last_soc = h["soc_kwh"][-1]
    into = tot.get(("grid", "battery"), 0.0) + tot.get(("solar", "battery"), 0.0)
    out = sum(v for (src, _), v in tot.items() if src == "battery")
    stored_change = (last_soc - first_soc) if (first_soc is not None and last_soc is not None) else 0.0
    tot[("battery", "losses")] = max(0.0, into - out - stored_change)
    scale = 365.25 / days if days else 0.0
    return {"links": {k: v * scale for k, v in tot.items() if v * scale >= 0.5}, "days": days}


def day_flows(hourly, date) -> dict | None:
    """One day, per hour: where the power came from and where it went (kWh).

    Returns {"hour": [...], "from": {source: [...]}, "to": {sink: [...]},
    "soc_kwh": [...], "buy_ore": [...]}, or None when the date isn't in hourly.
    """
    h = hourly.get(date)
    if not h:
        return None
    n = len(h["hour"])
    frm = {s: [0.0] * n for s in FLOW_SOURCES}
    to = {s: [0.0] * n for s in FLOW_SINKS if s != "losses"}
    for i in range(n):
        for (src, sink), v in _hour_flows(h, i).items():
            frm[src][i] += v
            if sink in to:
                to[sink][i] += v
    return {"hour": list(h["hour"]), "from": frm, "to": to,
            "soc_kwh": list(h.get("soc_kwh") or [0.0] * n), "buy_ore": list(h["buy_ore"])}
