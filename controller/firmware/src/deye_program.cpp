/*
 * deye_program.cpp — pure Deye program logic (no hardware, no logging).
 * See deye_program.h / deye_registers.h for the register model and sources.
 */

#include "deye_program.h"
#include <algorithm>
#include <cmath>

namespace {

constexpr int DAY_MIN = 1440;

struct Seg {
    int t;        // start minute of this program point
    int soc;
    int charge;   // DEYE_PROG_CHARGE_GRID or 0
    int power;
};

bool same_settings(const Seg& a, const Seg& b) {
    return a.soc == b.soc && a.charge == b.charge && a.power == b.power;
}

int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

}  // namespace

// Steps shared by both builders: merge equal neighbours (also circularly),
// point at 0000, pad to six points, emit. pts sorted by time, n ≤ 6 after
// merging; pts must have room for DEYE_N_PROGRAMS + 1 entries.
static bool emit_points(Seg* pts, int n, const Seg& idle, int grid_charge_current_a,
                        DeyeProgram* out) {
    /* 3. Merge consecutive points with identical settings (also circularly). */
    int m = 0;
    for (int i = 0; i < n; i++) {
        if (m > 0 && same_settings(pts[m - 1], pts[i])) {
            continue;
        }
        pts[m++] = pts[i];
    }
    n = m;
    if (n > 1 && same_settings(pts[0], pts[n - 1])) {
        for (int i = 1; i < n; i++) pts[i - 1] = pts[i];
        n--;
    }
    if (n == 0) {
        pts[n++] = idle;                            /* whole day self-use */
    }

    /* 4. A point at 0000 if there is room (the segment crossing midnight
     *    is split there — same settings, no behaviour change). */
    if (pts[0].t != 0 && n < DEYE_N_PROGRAMS) {
        Seg mid = pts[n - 1];
        mid.t = 0;
        for (int i = n; i > 0; i--) pts[i] = pts[i - 1];
        pts[0] = mid;
        n++;
    }

    /* 5. Pad to six points by splitting the longest segment in the middle. */
    while (n < DEYE_N_PROGRAMS) {
        int best = 0, best_len = -1;
        for (int i = 0; i < n; i++) {
            const int next = (i + 1 < n) ? pts[i + 1].t : pts[0].t + DAY_MIN;
            const int len = next - pts[i].t;
            if (len > best_len) {
                best_len = len;
                best = i;
            }
        }
        if (best_len < 2) {
            return false;                           /* cannot happen with ≤ 6 points */
        }
        Seg add = pts[best];
        add.t = (pts[best].t + best_len / 2) % DAY_MIN;
        pts[n++] = add;
        std::sort(pts, pts + n, [](const Seg& a, const Seg& b) { return a.t < b.t; });
    }

    /* 6. Emit. */
    DeyeProgram p;
    bool any_charge = false;
    for (int i = 0; i < DEYE_N_PROGRAMS; i++) {
        p.time_hhmm[i] = deye_min_to_hhmm(pts[i].t);
        p.power_w[i]   = static_cast<uint16_t>(pts[i].power);
        p.soc[i]       = static_cast<uint16_t>(pts[i].soc);
        p.charge[i]    = static_cast<uint16_t>(pts[i].charge);
        any_charge = any_charge || pts[i].charge != 0;
    }
    p.tou_enable = DEYE_TOU_ENABLE_ALL_DAYS;
    p.grid_charge_enable = any_charge ? 1 : 0;
    p.grid_charge_current_a = static_cast<uint16_t>(clampi(grid_charge_current_a, 0, 1000));
    *out = p;
    return true;
}


uint16_t deye_min_to_hhmm(int minute_of_day) {
    if (minute_of_day < 0) {
        minute_of_day = 0;
    }
    minute_of_day %= DAY_MIN;          /* 1440 → 0000 (next point at midnight) */
    return static_cast<uint16_t>((minute_of_day / 60) * 100 + minute_of_day % 60);
}

int deye_hhmm_to_min(uint16_t hhmm) {
    const int hh = hhmm / 100;
    const int mm = hhmm % 100;
    if (hh > 23 || mm > 59) {
        return -1;
    }
    return hh * 60 + mm;
}

bool deye_build_program(const TouWindow* windows, int n_windows,
                        int min_soc, int idle_power_w, int grid_charge_current_a,
                        DeyeProgram* out) {
    if (!out || n_windows < 0 || n_windows > MAX_TOU_WINDOWS ||
        (n_windows > 0 && !windows)) {
        return false;
    }
    min_soc = clampi(min_soc, 0, 100);
    idle_power_w = clampi(idle_power_w, 0, 65535);

    /* 1. Validate, split midnight-crossing windows into intervals, check overlap. */
    struct Iv { int s, e, owner; };
    Iv ivs[2 * MAX_TOU_WINDOWS];
    int niv = 0;
    bool used[MAX_TOU_WINDOWS] = {};
    for (int i = 0; i < n_windows; i++) {
        const int s = windows[i].start_min;
        const int e = windows[i].end_min;
        if (s < 0 || s >= DAY_MIN || e < 0 || e > DAY_MIN) {
            return false;
        }
        if (s == e || (s == 0 && e == 0)) {
            continue;                               /* empty window */
        }
        used[i] = true;
        if (e > s) {
            ivs[niv++] = {s, e, i};
        } else {                                    /* crosses midnight */
            ivs[niv++] = {s, DAY_MIN, i};
            if (e > 0) {
                ivs[niv++] = {0, e, i};
            }
        }
    }
    for (int a = 0; a < niv; a++) {
        for (int b = a + 1; b < niv; b++) {
            if (ivs[a].owner != ivs[b].owner &&
                ivs[a].s < ivs[b].e && ivs[b].s < ivs[a].e) {
                return false;                       /* overlapping windows */
            }
        }
    }

    /* 2. Boundary points: window start (charge settings), window end (idle). */
    const Seg idle = {0, min_soc, 0, idle_power_w};
    Seg pts[2 * MAX_TOU_WINDOWS + DEYE_N_PROGRAMS];
    int n = 0;
    for (int i = 0; i < n_windows; i++) {
        if (!used[i]) {
            continue;
        }
        const TouWindow& w = windows[i];
        const int pw = (w.charge_power_w > 0) ? clampi(w.charge_power_w, 1, 65535) : idle_power_w;
        pts[n++] = {w.start_min, clampi(w.target_soc, min_soc, 100), DEYE_PROG_CHARGE_GRID, pw};
        Seg end = idle;
        end.t = w.end_min % DAY_MIN;
        pts[n++] = end;
    }
    /* Sort by time; at equal time a window START wins over a window END
     * (touching windows: the charge continues). */
    std::sort(pts, pts + n, [](const Seg& a, const Seg& b) {
        if (a.t != b.t) return a.t < b.t;
        return a.charge > b.charge;
    });
    int m = 0;
    for (int i = 0; i < n; i++) {
        if (m > 0 && pts[m - 1].t == pts[i].t) {
            continue;                               /* keep the first (charge) */
        }
        pts[m++] = pts[i];
    }
    n = m;

    return emit_points(pts, n, idle, grid_charge_current_a, out);
}

bool deye_build_program_segments(const ProgSegment* segs, int n_segs,
                                 int min_soc, int idle_power_w, int grid_charge_current_a,
                                 DeyeProgram* out) {
    if (!out || n_segs < 1 || n_segs > DEYE_N_PROGRAMS || !segs) {
        return false;
    }
    min_soc = clampi(min_soc, 0, 100);
    idle_power_w = clampi(idle_power_w, 0, 65535);
    if (segs[0].start_min != 0) {
        return false;
    }
    Seg pts[DEYE_N_PROGRAMS + 1];
    for (int i = 0; i < n_segs; i++) {
        if (segs[i].start_min < 0 || segs[i].start_min >= DAY_MIN ||
            (i > 0 && segs[i].start_min <= segs[i - 1].start_min)) {
            return false;
        }
        const int pw = (segs[i].power_w > 0) ? clampi(segs[i].power_w, 1, 65535) : idle_power_w;
        pts[i] = {segs[i].start_min, clampi(segs[i].soc, min_soc, 100),
                  segs[i].grid_charge ? DEYE_PROG_CHARGE_GRID : 0, pw};
    }
    Seg idle = {0, min_soc, 0, idle_power_w};
    return emit_points(pts, n_segs, idle, grid_charge_current_a, out);
}

void deye_safe_program(int min_soc, int idle_power_w, DeyeProgram* out) {
    /* Cannot fail: no windows. */
    (void)deye_build_program(nullptr, 0, min_soc, idle_power_w, 0, out);
}

bool deye_program_grid_charges(const DeyeProgram* p) {
    if (!p) return false;
    if (p->grid_charge_enable) return true;
    for (int i = 0; i < DEYE_N_PROGRAMS; i++) {
        if (p->charge[i] & DEYE_PROG_CHARGE_GRID) return true;
    }
    return false;
}

int deye_program_writes(const DeyeProgram* p, DeyeRegWrite* out, int max_out) {
    if (!p || !out) return 0;
    int n = 0;
    auto add = [&](uint16_t addr, uint16_t value) {
        if (n < max_out) out[n++] = {addr, value};
    };
    const bool disabling = (p->grid_charge_enable == 0);
    if (disabling) {
        add(DEYE_REG_GRID_CHARGE_ENABLE, 0);        /* stop grid charge FIRST */
    }
    add(DEYE_REG_TOU_ENABLE, p->tou_enable);
    for (int i = 0; i < DEYE_N_PROGRAMS; i++) {
        add(static_cast<uint16_t>(DEYE_REG_PROG_TIME_BASE + i),   p->time_hhmm[i]);
        add(static_cast<uint16_t>(DEYE_REG_PROG_POWER_BASE + i),  p->power_w[i]);
        add(static_cast<uint16_t>(DEYE_REG_PROG_SOC_BASE + i),    p->soc[i]);
        add(static_cast<uint16_t>(DEYE_REG_PROG_CHARGE_BASE + i), p->charge[i]);
    }
    if (p->grid_charge_current_a > 0) {
        add(DEYE_REG_GRID_CHARGE_CURRENT, p->grid_charge_current_a);
    }
    if (!disabling) {
        add(DEYE_REG_GRID_CHARGE_ENABLE, p->grid_charge_enable);   /* enable LAST */
    }
    return n;
}

int deye_program_diff(const DeyeProgram* p, const uint16_t* block,
                      uint16_t base, int len, DeyeRegWrite* out, int max_out) {
    DeyeRegWrite all[DEYE_PROGRAM_MAX_WRITES];
    const int n_all = deye_program_writes(p, all, DEYE_PROGRAM_MAX_WRITES);
    int n = 0;
    for (int i = 0; i < n_all; i++) {
        const int off = static_cast<int>(all[i].addr) - static_cast<int>(base);
        if (block && off >= 0 && off < len && block[off] == all[i].value) {
            continue;
        }
        if (n < max_out) out[n++] = all[i];
    }
    return n;
}

int deye_grid_charge_current_a(float kw, float v_charge_max, float inverter_eff, int max_a) {
    if (!(kw > 0.0f) || !(v_charge_max > 0.0f) || !(inverter_eff > 0.0f) || max_a < 1) {
        return 0;
    }
    const int a = static_cast<int>(std::floor(kw * 1000.0f * inverter_eff / v_charge_max));
    return clampi(a, 1, max_a);
}

bool deye_decode_live(const uint16_t* block, int len, DeyeLiveData* out) {
    if (!block || !out || len < DEYE_LIVE_BLOCK_LEN) return false;
    auto u = [&](uint16_t addr) { return block[addr - DEYE_LIVE_BLOCK_BASE]; };
    auto s = [&](uint16_t addr) {
        return static_cast<float>(static_cast<int16_t>(u(addr)));
    };
    DeyeLiveData d;
    const uint16_t soc = u(DEYE_REG_BATTERY_SOC);
    if (soc > 100) return false;
    d.battery_soc     = static_cast<float>(soc);
    d.battery_power_w = s(DEYE_REG_BATTERY_POWER);
    d.grid_l1_w       = s(DEYE_REG_GRID_L1_POWER);
    d.grid_l2_w       = s(DEYE_REG_GRID_L2_POWER);
    d.grid_l3_w       = s(DEYE_REG_GRID_L3_POWER);
    d.grid_power_w    = s(DEYE_REG_GRID_POWER);
    d.load_power_w    = s(DEYE_REG_LOAD_POWER);
    d.pv_power_w      = static_cast<float>(u(DEYE_REG_PV1_POWER)) +
                        static_cast<float>(u(DEYE_REG_PV2_POWER));
    if (d.load_power_w < 0.0f || d.pv_power_w > 30000.0f) return false;
    *out = d;
    return true;
}
