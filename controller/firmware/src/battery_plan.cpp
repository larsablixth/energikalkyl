/*
 * battery_plan.cpp — pure day planning (see battery_plan.h).
 *
 * bat_plan_day() follows energikalkyl batteri.py simulate() step by step
 * (same candidate set, same order, same constraints) so that the firmware
 * and the investment calculator agree on what a day is worth. Differences
 * between the two then come only from what the controller can EXECUTE
 * (bat_plan_program / bat_simulate_program), not from the planning logic.
 */

#include "battery_plan.h"
#include "fuse.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>

namespace {

constexpr float EPS_KWH = 0.001f;   // energikalkyl's 0.001 kWh threshold
constexpr int MAX_TRANCHES = (EXPORT_PRICE_FACTOR > 0.0f) ? 2 : 1;

// Candidate storage: packed (j, tranche, i+1) in generation order, sorted by
// profit. Sized for the worst case (all pairs i < j plus one stored-energy
// candidate per use slot and tranche): ≈ 10 KB with one tranche.
constexpr int MAX_CANDIDATES = MAX_TRANCHES * (PLAN_MAX_SLOTS * (PLAN_MAX_SLOTS + 1) / 2);
uint16_t s_cand[MAX_CANDIDATES];

float s_tr_val[PLAN_MAX_SLOTS][2];
float s_tr_room[PLAN_MAX_SLOTS][2];
int   s_n_tr[PLAN_MAX_SLOTS];
float s_charge_room[PLAN_MAX_SLOTS];

inline uint16_t pack(int i, int j, int t, int n) {
    return static_cast<uint16_t>((j * MAX_TRANCHES + t) * (n + 1) + (i + 1));
}
inline void unpack(uint16_t c, int n, int* i, int* j, int* t) {
    const int ip1 = c % (n + 1);
    const int jt = c / (n + 1);
    *i = ip1 - 1;
    *t = jt % MAX_TRANCHES;
    *j = jt / MAX_TRANCHES;
}

inline float fmin3(float a, float b, float c) { return std::min(a, std::min(b, c)); }

}  // namespace

// ── Planner ─────────────────────────────────────────────────────────────

void bat_plan_day(const PlanSlot* s, int n, int from_slot, const PlanParams& p,
                  float start_level_kwh, BatteryPlan* out) {
    std::memset(static_cast<void*>(out), 0, sizeof(*out));
    if (!s || n <= 0) return;
    if (n > PLAN_MAX_SLOTS) n = PLAN_MAX_SLOTS;
    if (from_slot < 0) from_slot = 0;
    out->n = n;
    const float usable = p.capacity_kwh * (p.max_soc - p.min_soc);
    out->usable_kwh = usable;
    const float eff = p.efficiency;
    const float h = p.slot_h;

    /* Stored energy above the floor at the end of each slot, before trading
     * (expected solar surplus charges for free first). */
    float lvl = std::max(0.0f, start_level_kwh);
    out->start_level = lvl;
    for (int k = 0; k < n; k++) {
        float s_in = 0.0f;
        if (k >= from_slot) {
            const float surplus = std::max(0.0f, s[k].solar_kwh - s[k].load_kwh);
            if (surplus > EPS_KWH) {
                s_in = std::max(0.0f, fmin3(surplus, p.max_charge_kw * h, usable - lvl));
            }
        }
        lvl += s_in;
        out->solar_in[k] = s_in;
        out->level[k] = lvl;
    }

    /* Grid charge room per slot (fuse budget / inverter), minus the solar
     * that already charges in that slot. */
    for (int k = 0; k < n; k++) {
        const float room = s[k].grid_room_kwh;
        s_charge_room[k] = (k >= from_slot && room > 0.1f * h)
            ? std::max(0.0f, room - out->solar_in[k]) : 0.0f;
    }

    /* Discharge tranches: own net load at full buying cost; with export the
     * rest of the discharge power at the export value. */
    for (int j = 0; j < n; j++) {
        s_n_tr[j] = 0;
        if (j < from_slot) continue;
        const float max_out = p.max_discharge_kw * h;
        const float net = std::max(0.0f, s[j].load_kwh - s[j].solar_kwh);
        const float own = std::min(max_out, net);
        if (own > EPS_KWH) {
            s_tr_val[j][s_n_tr[j]] = s[j].buy_cost;
            s_tr_room[j][s_n_tr[j]] = own;
            s_n_tr[j]++;
        }
        if (MAX_TRANCHES > 1 && p.export_enabled && max_out - own > EPS_KWH) {
            s_tr_val[j][s_n_tr[j]] = std::max(0.0f, s[j].export_value);
            s_tr_room[j][s_n_tr[j]] = max_out - own;
            s_n_tr[j]++;
        }
    }

    /* Candidates in energikalkyl's generation order. */
    int nc = 0;
    for (int j = from_slot; j < n; j++) {
        for (int t = 0; t < s_n_tr[j]; t++) {
            const float v = s_tr_val[j][t];
            if (nc < MAX_CANDIDATES) s_cand[nc++] = pack(-1, j, t, n);
            for (int i = from_slot; i < j; i++) {
                if (s_charge_room[i] <= 0.0f) continue;
                const float c = s[i].buy_cost;
                const float profit = v - c / eff;
                if (profit > p.min_spread && v > c / eff && nc < MAX_CANDIDATES) {
                    s_cand[nc++] = pack(i, j, t, n);
                }
            }
        }
    }
    auto profit_of = [&](uint16_t c) {
        int i, j, t;
        unpack(c, n, &i, &j, &t);
        const float v = s_tr_val[j][t];
        return (i < 0) ? v : v - s[i].buy_cost / eff;
    };
    /* Most profitable first; ties keep generation order (= Python's stable
     * sort with reverse=True). Packed keys increase with generation order. */
    std::sort(s_cand, s_cand + nc, [&](uint16_t a, uint16_t b) {
        const float pa = profit_of(a), pb = profit_of(b);
        if (pa != pb) return pa > pb;
        return a < b;
    });

    float* plan_c = out->charge_kwh;
    float* plan_d = out->discharge_kwh;
    float* level = out->level;
    for (int k = 0; k < nc; k++) {
        int i, j, t;
        unpack(s_cand[k], n, &i, &j, &t);
        if (plan_c[j] > 0.0f) continue;
        float& dis_left = s_tr_room[j][t];
        if (dis_left <= EPS_KWH) continue;
        if (i < 0) {
            float stored = level[j];
            for (int q = j + 1; q < n; q++) stored = std::min(stored, level[q]);
            const float e_out = std::min(dis_left, stored * eff);
            if (e_out > EPS_KWH) {
                plan_d[j] += e_out;
                dis_left -= e_out;
                for (int q = j; q < n; q++) level[q] -= e_out / eff;
            }
            continue;
        }
        if (plan_d[i] > 0.0f) continue;
        float peak = level[i];
        for (int q = i + 1; q < j; q++) peak = std::max(peak, level[q]);
        const float room = usable - peak;
        const float e_in = fmin3(s_charge_room[i] - plan_c[i], room, dis_left / eff);
        if (e_in > EPS_KWH) {
            plan_c[i] += e_in;
            plan_d[j] += e_in * eff;
            dis_left -= e_in * eff;
            for (int q = i; q < j; q++) level[q] += e_in;
        }
    }

    /* Paid to consume (TOTAL buying cost < 0): fill the remaining room even
     * without a later use today — the energy is kept for tomorrow. (Not in
     * energikalkyl; SE3 history has hardly any such hours: needs spot <
     * −0.60 SEK/kWh.) */
    for (int i = from_slot; i < n; i++) {
        if (!(s[i].buy_cost < 0.0f) || plan_d[i] > 0.0f) continue;
        float peak = level[i];
        for (int q = i + 1; q < n; q++) peak = std::max(peak, level[q]);
        const float e_in = std::min(s_charge_room[i] - plan_c[i], usable - peak);
        if (e_in > EPS_KWH) {
            plan_c[i] += e_in;
            for (int q = i; q < n; q++) level[q] += e_in;
        }
    }
}

// ── Deye model ──────────────────────────────────────────────────────────

float bat_segment_power_kw(const PlanSegment* segs, int n_segs, int k, const PlanSlot* s,
                           int n, int from_slot, float slot_h) {
    if (k < 0 || k >= n_segs || !segs[k].grid_charge || slot_h <= 0.0f) return 0.0f;
    const int a = std::max(segs[k].start_slot, std::max(0, from_slot));
    const int b = (k + 1 < n_segs) ? std::min(segs[k + 1].start_slot, n) : n;
    float pw = 1e9f;
    for (int q = a; q < b; q++) pw = std::min(pw, std::max(0.0f, s[q].grid_room_kwh) / slot_h);
    return (pw < 1e8f) ? pw : 0.0f;
}

DayMoney bat_simulate_program(const PlanSegment* segs, int n_segs, const PlanSlot* s,
                              int n, int from_slot, const PlanParams& p,
                              float start_level_kwh) {
    DayMoney m;
    const float cap = p.capacity_kwh;
    const float floor_abs = cap * p.min_soc;
    const float top = cap * p.max_soc;
    const float h = p.slot_h;
    float soc = floor_abs + std::max(0.0f, start_level_kwh);
    int seg = 0, pw_seg = -1;
    float seg_pw = 0.0f;
    for (int k = 0; k < n; k++) {
        while (seg + 1 < n_segs && segs[seg + 1].start_slot <= k) seg++;
        if (k < from_slot) continue;
        const bool grid = n_segs > 0 && segs[seg].grid_charge;
        if (grid && pw_seg != seg) {
            /* one power per program point (the pipeline writes the min room
             * of the segment's slots: fuse-safe in every slot) */
            seg_pw = bat_segment_power_kw(segs, n_segs, seg, s, n, from_slot, h);
            pw_seg = seg;
        }
        const float seg_level = cap * static_cast<float>(n_segs > 0 ? segs[seg].soc_pct : 0) / 100.0f;
        const float load = s[k].load_kwh;
        const float solar = s[k].solar_kwh;

        /* PV surplus first */
        float solar_in = 0.0f;
        const float surplus = std::max(0.0f, solar - load);
        if (surplus > EPS_KWH) {
            solar_in = std::max(0.0f, fmin3(surplus, p.max_charge_kw * h, top - soc));
            soc += solar_in;
        }
        m.solar_in_kwh += solar_in;

        if (grid && soc < seg_level - EPS_KWH) {
            const float room = std::max(0.0f, std::min(s[k].grid_room_kwh, seg_pw * h) - solar_in);
            const float e = fmin3(room, seg_level - soc, top - soc);
            if (e > EPS_KWH) {
                soc += e;
                m.charged_kwh += e;
                m.charge_cost += e * s[k].buy_cost;
            }
            continue;   /* the house runs on the grid while charging */
        }
        /* self-use down to the segment SOC (also the floor of a GRID
         * segment that already reached its target) */
        const float fl = std::max(floor_abs, seg_level);
        const float net = std::max(0.0f, load - solar);
        if (soc > fl && net > EPS_KWH) {
            const float e_out = fmin3(net, p.max_discharge_kw * h, (soc - fl) * p.efficiency);
            if (e_out > EPS_KWH) {
                soc -= e_out / p.efficiency;
                m.discharged_kwh += e_out;
                m.discharge_value += e_out * s[k].buy_cost;
            }
        }
    }
    m.end_level = soc - floor_abs;
    return m;
}

// ── energikalkyl's execution of the plan (ideal controller) ─────────────

DayMoney bat_execute_plan(const BatteryPlan* plan, const PlanSlot* s, int n,
                          const PlanParams& p, float start_level_kwh) {
    DayMoney m;
    const float cap = p.capacity_kwh;
    const float floor_abs = cap * p.min_soc;
    const float top = cap * p.max_soc;
    const float h = p.slot_h;
    float soc = floor_abs + std::max(0.0f, start_level_kwh);
    for (int k = 0; k < n; k++) {
        const float load = s[k].load_kwh;
        const float solar = s[k].solar_kwh;
        float solar_in = 0.0f;
        const float surplus = std::max(0.0f, solar - load);
        if (surplus > EPS_KWH) {
            solar_in = fmin3(std::min(surplus, p.max_charge_kw * h), top - soc, 1e9f);
            if (solar_in > EPS_KWH) {
                soc += solar_in;
                m.solar_in_kwh += solar_in;
            } else {
                solar_in = 0.0f;
            }
        }
        if (plan->charge_kwh[k] > EPS_KWH) {
            const float gk = std::max(0.0f, s[k].grid_room_kwh - solar_in);
            const float e = std::min(std::min(plan->charge_kwh[k], gk), top - soc);
            if (e > EPS_KWH) {
                soc += e;
                m.charged_kwh += e;
                m.charge_cost += e * s[k].buy_cost;
                continue;
            }
        }
        if (plan->discharge_kwh[k] > EPS_KWH) {
            float e_out = std::min(plan->discharge_kwh[k], p.max_discharge_kw * h);
            e_out = std::min(e_out, (soc - floor_abs) * p.efficiency);
            const float net = std::max(0.0f, load - solar);
            if (!p.export_enabled) e_out = std::min(e_out, net);
            if (e_out > EPS_KWH) {
                soc -= e_out / p.efficiency;
                m.discharged_kwh += e_out;
                const float own = std::min(e_out, net);
                m.discharge_value += own * s[k].buy_cost + (e_out - own) * s[k].export_value;
            }
        }
    }
    m.end_level = soc - floor_abs;
    return m;
}

// ── Plan → program segments ─────────────────────────────────────────────

namespace {

struct SlotSetting {
    bool grid;
    int pct;
};

bool same(const PlanSegment& a, const PlanSegment& b) {
    return a.grid_charge == b.grid_charge && a.soc_pct == b.soc_pct;
}

float objective(const PlanSegment* segs, int ns, const PlanSlot* s, int n, int from,
                const PlanParams& p, float start_level, float terminal_value) {
    const DayMoney m = bat_simulate_program(segs, ns, s, n, from, p, start_level);
    return m.net() + m.end_level * terminal_value;
}

/* Adjacent segments with the same settings are one program point — for
 * GRID segments only if their power (min grid room) is the same too:
 * otherwise the merged point would charge at the smaller power everywhere
 * (e.g. a night GRID segment spanning EV slots). Those merges go through
 * the least-loss loop instead. */
int compact(PlanSegment* segs, int ns, const PlanSlot* s, int n, int from, float h) {
    static PlanSegment tmp[PLAN_MAX_SLOTS];
    for (int i = 0; i < ns; i++) tmp[i] = segs[i];
    int m = 0;
    float last_pw = 0.0f;
    for (int i = 0; i < ns; i++) {
        const float pw = bat_segment_power_kw(tmp, ns, i, s, n, from, h);
        if (m > 0 && same(segs[m - 1], tmp[i]) &&
            (!tmp[i].grid_charge || std::fabs(pw - last_pw) <= 0.05f + 0.01f * std::max(pw, last_pw))) {
            last_pw = std::min(last_pw, pw);
            continue;
        }
        segs[m++] = tmp[i];
        last_pw = pw;
    }
    return m;
}

}  // namespace

int bat_plan_program(const BatteryPlan* plan, const PlanSlot* s, int from_slot,
                     const PlanParams& p, int max_segments, PlanSegment* out) {
    const int n = plan->n;
    if (n <= 0 || max_segments <= 0) {
        if (max_segments > 0) {
            out[0] = PlanSegment{};
            return 1;
        }
        return 0;
    }
    if (from_slot < 0) from_slot = 0;
    if (from_slot >= n) from_slot = n - 1;
    const int min_pct = static_cast<int>(std::lround(p.min_soc * 100.0f));
    const int max_pct = static_cast<int>(std::lround(p.max_soc * 100.0f));
    auto pct_of = [&](float level, bool up) {
        const float x = 100.0f * (p.min_soc + level / p.capacity_kwh);
        int v = up ? static_cast<int>(std::ceil(x - 0.05f)) : static_cast<int>(std::lround(x));
        return std::max(min_pct, std::min(up ? 100 : max_pct, v));
    };

    static PlanSegment segs[PLAN_MAX_SLOTS];
    static PlanSegment trial[PLAN_MAX_SLOTS];
    int ns = 0;
    for (int k = from_slot; k < n; k++) {
        PlanSegment g;
        g.start_slot = (k == from_slot) ? 0 : k;
        if (plan->charge_kwh[k] > EPS_KWH) {
            g.grid_charge = true;
            g.soc_pct = pct_of(plan->level[k], false);
        } else if (plan->discharge_kwh[k] > EPS_KWH) {
            g.grid_charge = false;
            g.soc_pct = pct_of(plan->level[k], false);
        } else {
            g.grid_charge = false;                      /* HOLD: floor ≥ level */
            g.soc_pct = pct_of(plan->level[k], true);
        }
        segs[ns++] = g;
    }
    ns = compact(segs, ns, s, n, from_slot, p.slot_h);

    /* Energy left at the end of the day is worth something tomorrow, but
     * less than using it today as planned: half of the cheapest buying cost
     * of the remaining day, per delivered kWh. (Valued at the full price, a
     * merge that HOLDS energy the plan uses would look free.) */
    float tv = 1e9f;
    for (int k = from_slot; k < n; k++) tv = std::min(tv, s[k].buy_cost);
    tv = 0.5f * p.efficiency * std::max(0.0f, tv);
    const float start = plan->start_level;

    float cur = objective(segs, ns, s, n, from_slot, p, start, tv);
    while (ns > 1) {
        float best = -1e30f;
        int best_a = -1;
        PlanSegment best_set;
        for (int a = 0; a + 1 < ns; a++) {
            /* merged settings: grid flag of either × SOC of either */
            for (int c = 0; c < 4; c++) {
                PlanSegment keep;
                keep.grid_charge = (c & 1) ? segs[a + 1].grid_charge : segs[a].grid_charge;
                keep.soc_pct = (c & 2) ? segs[a + 1].soc_pct : segs[a].soc_pct;
                if ((c == 1 || c == 2) && keep.grid_charge == segs[a].grid_charge &&
                    keep.soc_pct == segs[a].soc_pct) continue;     /* duplicate of c=0 */
                int m = 0;
                for (int i = 0; i < ns; i++) {
                    if (i == a + 1) continue;
                    trial[m] = segs[i];
                    if (i == a) {
                        trial[m].grid_charge = keep.grid_charge;
                        trial[m].soc_pct = keep.soc_pct;
                    }
                    m++;
                }
                const float o = objective(trial, m, s, n, from_slot, p, start, tv);
                if (o > best + 1e-6f) {
                    best = o;
                    best_a = a;
                    best_set = keep;
                }
            }
        }
        const bool must = ns > max_segments;
        if (best_a < 0 || (!must && best < cur - 1e-4f)) break;
        segs[best_a].grid_charge = best_set.grid_charge;
        segs[best_a].soc_pct = best_set.soc_pct;
        for (int i = best_a + 1; i + 1 < ns; i++) segs[i] = segs[i + 1];
        ns--;
        ns = compact(segs, ns, s, n, from_slot, p.slot_h);
        cur = objective(segs, ns, s, n, from_slot, p, start, tv);
    }
    for (int i = 0; i < ns; i++) out[i] = segs[i];
    return ns;
}

// ── EV ──────────────────────────────────────────────────────────────────

float ev_plan_day(const float* buy_cost, const int* local_start_min, const float* room_kw,
                  int n, float slot_h, int win_start_h, int win_end_h, float kwh_needed,
                  uint8_t* amps_out) {
    static int16_t idx[MAX_SLOTS];
    if (n > MAX_SLOTS) n = MAX_SLOTS;
    int m = 0;
    for (int i = 0; i < n; i++) {
        amps_out[i] = 0;
        const int hr = local_start_min[i] / 60;
        const bool in = (win_start_h <= win_end_h)
            ? (hr >= win_start_h && hr < win_end_h)
            : (hr >= win_start_h || hr < win_end_h);
        if (in) idx[m++] = static_cast<int16_t>(i);
    }
    std::sort(idx, idx + m, [&](int16_t a, int16_t b) {
        if (buy_cost[a] != buy_cost[b]) return buy_cost[a] < buy_cost[b];
        return a < b;
    });
    const float kwh_per_amp = static_cast<float>(FUSE_PHASES) * FUSE_VOLTAGE / 1000.0f * slot_h;
    float got = 0.0f;
    for (int k = 0; k < m && got < kwh_needed - EPS_KWH; k++) {
        const int i = idx[k];
        int a = fuse_goe_amps(room_kw[i], FUSE_PHASES, FUSE_VOLTAGE, GOE_MIN_AMPS, GOE_MAX_AMPS);
        if (a <= 0) continue;
        /* Last (most expensive chosen) slot: only the amps the remaining need
         * takes, not the full room — at full room the plan overshot the daily
         * need by up to one slot at max amps (~11 kWh/h at 16 A). Never below
         * GOE_MIN_AMPS, so the overshoot is now < 1 A × slot, or the
         * GOE_MIN_AMPS slot when less than that is left. */
        const int need_a = static_cast<int>(std::ceil((kwh_needed - got) / kwh_per_amp - 1e-4f));
        if (need_a < a) a = std::max(GOE_MIN_AMPS, need_a);
        amps_out[i] = static_cast<uint8_t>(a);
        got += static_cast<float>(a) * kwh_per_amp;
    }
    return got;
}

// ── Battery + EV sharing one fuse budget ────────────────────────────────

namespace {

constexpr float SHARED_SHORT_TOL_KWH = 0.05f;
constexpr float SHARED_TIE_SEK = 0.005f;

void plan_order(const SharedDayInput& in, bool ev_first, SharedDayPlan* out) {
    static float room_kw[MAX_SLOTS];
    const int n = std::min(in.n, MAX_SLOTS);
    const int g = std::max(1, in.group);
    const int m = std::min((n + g - 1) / g, PLAN_MAX_SLOTS);
    const int from = std::max(0, std::min(in.from_slot, n > 0 ? n - 1 : 0));
    const int from_p = from / g;
    const float slot_h = in.slot_h_price * static_cast<float>(g);
    const float kw_per_amp = static_cast<float>(FUSE_PHASES) * FUSE_VOLTAGE / 1000.0f;
    const bool ev = in.ev_kwh > EPS_KWH;
    auto load_kw = [&](int i) {
        const int q = i / g;
        return (q < m && in.load_kwh) ? in.load_kwh[q] / slot_h : 0.0f;
    };

    out->ev_first = ev_first && ev;
    out->ct_sees_ev = in.ct_sees_ev;
    out->m = m;
    out->ev_kwh = 0.0f;
    for (int i = 0; i < n; i++) { out->ev_amps[i] = 0; out->ev_e_kwh[i] = 0.0f; }

    /* Expected EV energy per price slot from ev_amps: the overshoot of the
     * last (most expensive chosen) slot removed, as in the EV money. */
    auto ev_energy = [&]() {
        int top_i = -1;
        float sum = 0.0f;
        for (int i = 0; i < n; i++) {
            out->ev_e_kwh[i] = out->ev_amps[i] * kw_per_amp * in.slot_h_price;
            if (!out->ev_amps[i]) continue;
            sum += out->ev_e_kwh[i];
            if (top_i < 0 || in.buy_cost[i] >= in.buy_cost[top_i]) top_i = i;
        }
        const float over = std::max(0.0f, sum - (ev ? in.ev_kwh : 0.0f));
        if (top_i >= 0) out->ev_e_kwh[top_i] = std::max(0.0f, out->ev_e_kwh[top_i] - over);
    };

    /* Battery on planning slots (groups of g price slots). pass2 = battery
     * first re-plan with the EV known (EV behind the CT). */
    auto plan_battery = [&](bool pass2) {
        for (int q = 0; q < m; q++) {
            PlanSlot x;
            float c = 0.0f, ex = 0.0f, evkw = 0.0f, eve = 0.0f;
            int cnt = 0;
            for (int i = q * g; i < n && i < (q + 1) * g; i++) {
                c += in.buy_cost[i];
                if (in.export_value) ex += in.export_value[i];
                evkw = std::max(evkw, out->ev_amps[i] * kw_per_amp);
                eve += out->ev_e_kwh[i];
                cnt++;
            }
            x.buy_cost = cnt ? c / static_cast<float>(cnt) : 0.0f;
            x.export_value = cnt ? ex / static_cast<float>(cnt) : 0.0f;
            const float house = in.load_kwh ? in.load_kwh[q] : 0.0f;
            x.load_kwh = house + (in.ct_sees_ev ? eve : 0.0f);
            x.solar_kwh = in.solar_kwh ? in.solar_kwh[q] : 0.0f;
            float room = std::min(in.bat_charge_kw, in.grid_max_kw - house / slot_h - evkw);
            if (pass2 && evkw > 0.0f && room < in.bat_charge_kw - 1e-3f) room = 0.0f;
            x.grid_room_kwh = std::max(0.0f, room) * slot_h;
            out->ps[q] = x;
        }
        PlanParams pp = in.pp;
        pp.slot_h = slot_h;
        bat_plan_day(out->ps, m, from_p, pp, in.start_level_kwh, &out->plan);
        const int maxs = std::max(1, std::min(in.max_segments, PLAN_MAX_SLOTS));
        out->n_segs = bat_plan_program(&out->plan, out->ps, from_p, pp, maxs, out->segs);
        out->bat = bat_simulate_program(out->segs, out->n_segs, out->ps, m, from_p, pp,
                                        in.start_level_kwh);
        /* terminal value: the same as bat_plan_program's objective */
        float tv = 1e9f;
        for (int q = from_p; q < m; q++) tv = std::min(tv, out->ps[q].buy_cost);
        tv = (m > from_p) ? 0.5f * pp.efficiency * std::max(0.0f, tv) : 0.0f;
        out->bat_value_sek = out->bat.net() + out->bat.end_level * tv;
    };

    /* EV first: the EV plan takes the room before the battery. */
    if (out->ev_first) {
        for (int i = 0; i < n; i++)
            room_kw[i] = (i < from) ? 0.0f : std::max(0.0f, in.grid_max_kw - load_kw(i));
        out->ev_kwh = ev_plan_day(in.buy_cost, in.local_start_min, room_kw, n, in.slot_h_price,
                                  in.ev_win_start_h, in.ev_win_end_h, in.ev_kwh, out->ev_amps);
        ev_energy();
    }

    plan_battery(false);

    /* Battery first: the EV gets what the GRID segments leave. */
    if (!out->ev_first && ev) {
        for (int i = 0; i < n; i++) {
            const int q = i / g;
            int k = 0;
            while (k + 1 < out->n_segs && out->segs[k + 1].start_slot <= q) k++;
            const bool grid = out->n_segs > 0 && out->segs[k].grid_charge;
            const float bat = grid ? in.bat_charge_kw : 0.0f;
            room_kw[i] = (i < from) ? 0.0f : std::max(0.0f, in.grid_max_kw - load_kw(i) - bat);
        }
        out->ev_kwh = ev_plan_day(in.buy_cost, in.local_start_min, room_kw, n, in.slot_h_price,
                                  in.ev_win_start_h, in.ev_win_end_h, in.ev_kwh, out->ev_amps);
        ev_energy();
        /* The Deye would serve that EV draw in SELF segments: re-plan the
         * battery knowing it (HOLD where serving the EV does not pay). */
        if (in.ct_sees_ev && out->ev_kwh > EPS_KWH) plan_battery(true);
    }

    /* EV money: planned kWh × buy cost, the overshoot of the last (most
     * expensive chosen) slot not counted. */
    float cost = 0.0f, top = 0.0f;
    bool any = false;
    for (int i = 0; i < n; i++) {
        if (!out->ev_amps[i]) continue;
        const float e = out->ev_amps[i] * kw_per_amp * in.slot_h_price;
        cost += e * in.buy_cost[i];
        top = any ? std::max(top, in.buy_cost[i]) : in.buy_cost[i];
        any = true;
    }
    const float need = ev ? in.ev_kwh : 0.0f;
    const float over = std::max(0.0f, out->ev_kwh - need);
    out->ev_cost_sek = cost - over * top;
    out->ev_short_kwh = std::max(0.0f, need - out->ev_kwh);
    out->total_sek = out->ev_cost_sek - out->bat_value_sek;
}

}  // namespace

void plan_shared_day(const SharedDayInput& in, EvPriorityMode mode, SharedDayPlan* out) {
    const bool ev = in.ev_kwh > EPS_KWH;
    out->compared = false;
    out->other_total_sek = 0.0f;
    if (!ev || mode != EV_PRIO_AUTO) {
        plan_order(in, ev && mode == EV_PRIO_EV_FIRST, out);
        return;
    }
    static SharedDayPlan alt;
    plan_order(in, false, out);          /* battery first */
    plan_order(in, true, &alt);          /* EV first */
    bool take_alt;
    if (std::fabs(alt.ev_short_kwh - out->ev_short_kwh) > SHARED_SHORT_TOL_KWH) {
        take_alt = alt.ev_short_kwh < out->ev_short_kwh;     /* the EV must get its energy */
    } else {
        take_alt = alt.total_sek < out->total_sek - SHARED_TIE_SEK;
    }
    const float bf_total = out->total_sek;
    if (take_alt) {
        *out = alt;
        out->other_total_sek = bf_total;
    } else {
        out->other_total_sek = alt.total_sek;
    }
    out->compared = true;
}

// ── Solar model (energikalkyl solar.py) ─────────────────────────────────

namespace {
const float MONTHLY_KWH_PER_KWP[12] = {15, 35, 75, 110, 140, 145, 140, 115, 75, 40, 15, 8};
const float DAYLIGHT[12][2] = {
    {8.5f, 15.5f}, {7.5f, 16.5f}, {6.5f, 18.0f}, {5.5f, 19.5f}, {4.0f, 21.0f}, {3.5f, 21.5f},
    {4.0f, 21.0f}, {5.0f, 20.0f}, {6.5f, 18.5f}, {7.5f, 17.0f}, {8.0f, 15.5f}, {9.0f, 15.0f}};
const int DAYS_IN_MONTH[12] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};

float quarter_shape(int month, float t) {
    const float rise = DAYLIGHT[month - 1][0], set = DAYLIGHT[month - 1][1];
    if (t < rise || t > set) return 0.0f;
    const float noon = (rise + set) / 2.0f, half = (set - rise) / 2.0f;
    const float c = std::max(0.0f, std::cos((t - noon) / half * 3.14159265f / 2.0f));
    return c * c * c / 4.0f;
}
}  // namespace

float solar_model_kwh(int month, int start_min, int dur_min, float kwp, float perf_ratio) {
    if (month < 1 || month > 12 || dur_min <= 0 || !(kwp > 0.0f)) return 0.0f;
    float total = 0.0f;
    for (int q = 0; q < 96; q++) total += quarter_shape(month, q / 4.0f);
    if (total <= 0.0f) return 0.0f;
    const float daily = MONTHLY_KWH_PER_KWP[month - 1] * kwp * perf_ratio / DAYS_IN_MONTH[month - 1];
    /* Sum the quarter-hour samples inside the slot; a slot shorter than a
     * quarter gets its time share of the quarter it falls in. */
    float sum = 0.0f;
    const int end = start_min + dur_min;
    for (int q = 0; q < 96; q++) {
        const int qa = q * 15, qb = qa + 15;
        const int ov = std::min(end, qb) - std::max(start_min, qa);
        if (ov > 0) sum += quarter_shape(month, q / 4.0f) * static_cast<float>(ov) / 15.0f;
    }
    return daily * sum / total;
}
