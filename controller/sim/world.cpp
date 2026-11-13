// C++ port of sim-hardware.js DeyeSim / GoeSim / GridMeter (see world.h).
// Keep the two in step: same rules, same loss models.
#include "world.h"
#include <algorithm>
#include <cmath>

namespace {
int hhmm_to_min(int hhmm) {
    const int h = hhmm / 100, m = hhmm % 100;
    return (h > 23 || m > 59) ? -1 : h * 60 + m;
}
}  // namespace

void DeyeWorld::write_program(const uint16_t* regs) {
    n_points = 6;
    for (int i = 0; i < 6; i++) {
        points[i].start_min = hhmm_to_min(regs[i]);
        points[i].power_w = regs[6 + i];
        points[i].soc = regs[12 + i];
        points[i].grid = (regs[18 + i] & 1) == 1;
    }
    tou_enable = regs[24];
    grid_charge_enable = regs[25];
    grid_charge_current_a = regs[26];
}

bool DeyeWorld::grid_charge_programmed() const {
    if (!grid_charge_enable) return false;
    for (int i = 0; i < n_points; i++) if (points[i].grid) return true;
    return false;
}

int DeyeWorld::point_at(int minute) const {
    int best = -1, best_min = -1, last = -1, last_min = -1;
    for (int i = 0; i < n_points; i++) {
        const int m = points[i].start_min;
        if (m < 0) continue;
        if (m <= minute && m >= best_min) { best = i; best_min = m; }
        if (m >= last_min) { last = i; last_min = m; }
    }
    return best >= 0 ? best : last;
}

void DeyeWorld::tick(int minute, float dt_h, float load, float solar, bool grid_charge_allowed) {
    grid_charge_kw = solar_charge_kw = solar_direct_kw = served_kw = 0;
    export_kw = curtailed_kw = grid_draw_kw = 0;
    load_kw = std::max(0.0f, load);
    pv_kw = std::max(0.0f, solar);
    const float cap = capacity_kwh;
    float level = soc / 100.0f * cap;
    const float top = max_soc / 100.0f * cap;
    const float floor_abs = min_soc / 100.0f * cap;
    const float ce = realistic ? std::sqrt(efficiency) : 1.0f;
    const float de = realistic ? std::sqrt(efficiency) : efficiency;
    auto taper = [&](float kw) {
        if (!realistic || soc < 85.0f) return kw;
        const float p = (soc - 85.0f) / std::max(1.0f, max_soc - 85.0f);
        return kw * std::max(0.1f, 1.0f - p * 0.9f);
    };
    if (realistic) level = std::max(0.0f, level - standby_kw * dt_h);

    const int k = point_at(minute);
    Point pt;
    if (k >= 0) pt = points[k];
    else { pt.power_w = static_cast<int>(max_discharge_kw * 1000); pt.soc = static_cast<int>(min_soc); pt.grid = false; }
    const float pt_kw = pt.power_w / 1000.0f;
    const float pt_level = pt.soc / 100.0f * cap;

    // 1. PV → load
    solar_direct_kw = std::min(pv_kw, load_kw);
    const float surplus = pv_kw - solar_direct_kw;
    const float net = load_kw - solar_direct_kw;
    // 2. PV surplus → battery
    if (surplus > 1e-6f && level < top) {
        const float kw = std::min({surplus, taper(max_charge_kw), (top - level) / (dt_h * ce)});
        solar_charge_kw = std::max(0.0f, kw);
        level += solar_charge_kw * dt_h * ce;
    }
    // 3. leftover PV
    const float leftover = std::max(0.0f, surplus - solar_charge_kw);
    if (export_enabled) export_kw = leftover; else curtailed_kw = leftover;

    if (pt.grid && grid_charge_enable && grid_charge_allowed && level < pt_level - 1e-4f) {
        // 4. grid charge to the point SOC
        float kw = pt_kw;
        if (grid_charge_current_a > 0) {
            kw = std::min(kw, grid_charge_current_a * v_charge_max / inverter_eff / 1000.0f);
        }
        kw = std::min(kw, taper(max_charge_kw) - solar_charge_kw);
        kw = std::min(kw, (std::min(pt_level, top) - level) / (dt_h * ce));
        grid_charge_kw = std::max(0.0f, kw);
        level += grid_charge_kw * dt_h * ce;
    } else {
        // 5. self-use down to the point SOC (never below min SOC)
        const float fl = std::max(floor_abs, pt_level);
        if (net > 1e-6f && level > fl) {
            const float kw = std::min({net, pt_kw, max_discharge_kw, (level - fl) * de / dt_h});
            served_kw = std::max(0.0f, kw);
            level -= served_kw * dt_h / de;
        }
    }
    soc = std::min(100.0f, std::max(0.0f, level / cap * 100.0f));
    grid_draw_kw = net - served_kw + grid_charge_kw - export_kw;
}

void GoeWorld::set_amps(int a) {
    if (a < min_amps) a = 0;
    if (a > max_amps) a = max_amps;
    amps = a;
}

float GoeWorld::tick(float dt_h) {
    float kw = 0;
    if (car_connected && amps > 0 && need_kwh > 1e-6f) {
        kw = std::min(amps * phases * voltage / 1000.0f, obc_max_kw);
        kw = std::min(kw, need_kwh / dt_h);
    }
    draw_kw = kw;
    need_kwh = std::max(0.0f, need_kwh - kw * dt_h);
    return kw;
}

void MeterWorld::update(float house_kw, float deye_grid_kw, float ev_kw, bool ev_behind_ct) {
    const float deye_load = house_kw + (ev_behind_ct ? ev_kw : 0.0f);
    const float inv = (deye_load - deye_grid_kw) / 3.0f;
    const float kw[3] = {shares[0] * house_kw - inv + ev_kw / 3.0f,
                         shares[1] * house_kw - inv + ev_kw / 3.0f,
                         shares[2] * house_kw - inv + ev_kw / 3.0f};
    l1 = kw[0] * 1000.0f / voltage;
    l2 = kw[1] * 1000.0f / voltage;
    l3 = kw[2] * 1000.0f / voltage;
    power_w = (deye_grid_kw + (ev_behind_ct ? 0.0f : ev_kw)) * 1000.0f;
}
