// Controller check for energikalkyl: the NORVI's own controller (firmware
// controller.cpp) runs the calculator's period minute by minute in the
// simulator's world (sim/runner.cpp, sim/world.cpp), next to the firmware
// planner on the calculator's own inputs (sim/reference.cpp). Same check as
// the simulator's "Validate calculator" (energy-scheduler-sim):
//   calc       energikalkyl's result
//   ideal      firmware planner on the calculator's inputs (parity, ≈ 0)
//   progperf   that plan as a Deye program (≤ 6 points)
//   ctrl       the real controller: 13:30 price fetch, its own forecasts
//              (house model at the month's normal temperature, cos³ solar),
//              EV + fuse budget, look-ahead, fuse guard, the Deye executing
//              its program
//
// Run as a separate process (controller_check.py): the firmware's
// time_local_init() sets the process time zone to Europe/Stockholm.
//
// stdin, one line each:
//   P capacity_kwh max_charge_kw max_discharge_kw efficiency min_soc% max_soc% grid_max_kw
//     ev_win_start_h ev_win_end_h ev_mode(0 battery,1 ev,2 auto,-1 firmware) fuse_amps solar_kwp
//   D yyyy-mm-dd n                      (a day with n hourly rows follows)
//   R spot_sek buy_sek load_kwh ev_kwh solar_kwh calc_net_sek calc_in_kwh calc_out_kwh
// stdout: one JSON object.
#include <cstdio>
#include <cstring>
#include <cmath>
#include <ctime>
#include <map>
#include <string>
#include <vector>
#include <algorithm>

#include "config.h"
#include "tariff.h"
#include "time_local.h"
#include "battery_plan.h"

extern "C" {
float* ref_in_ptr();
float* ref_out_ptr();
void ref_set_battery(float, float, float, float, float, float, float, float);
void ref_plan_day(int n, int slot_min, float lvl_ideal, float lvl_progperf);
void run_reset();
void run_set_plant(float, float, float, int, int, int, float, float, int, int, float, float, float, float);
void run_set_ev_mode(int mode);
void run_set_options(float, int, int, float, float, float, int);
float* run_day_buffer();
int run_add_day(int y, int m, int d, int n, int slot_min, int has_buy, int has_temp);
int run_days(int count);
float* run_day_result(int i);
int run_house_days();
}

namespace {

// runner.cpp RR_* fields used here
enum { RR_BATTERY_KR = 0, RR_IN = 3, RR_OUT = 4, RR_EV_KWH = 9, RR_EV_KR = 10, RR_EV_UNMET = 11,
       RR_GUARD_EVENTS = 18, RR_SAFE_MIN = 21, RR_PROGRAM_WRITES = 16 };

struct Day {
    std::string date;
    int y = 0, m = 0, d = 0;
    std::vector<float> spot, buy, load, ev, solar;
    double calc_net = 0, calc_in = 0, calc_out = 0;
};

struct Agg {
    double days = 0;
    double net[4] = {0, 0, 0, 0};        // calc, ideal, progperf, ctrl
    double in_kwh[4] = {0, 0, 0, 0};
    double out_kwh[4] = {0, 0, 0, 0};
    double calc_ev_kwh = 0, calc_ev_kr = 0, ctrl_ev_kwh = 0, ctrl_ev_kr = 0, ev_unmet = 0;
    double safe_min = 0, guard_events = 0, program_writes = 0;
};

void print_agg(const Agg& a) {
    static const char* names[4] = {"calc", "ideal", "progperf", "ctrl"};
    std::printf("{\"days\":%.0f", a.days);
    for (int k = 0; k < 4; k++) {
        std::printf(",\"%s\":{\"net\":%.3f,\"in_kwh\":%.3f,\"out_kwh\":%.3f}", names[k], a.net[k], a.in_kwh[k],
                    a.out_kwh[k]);
    }
    std::printf(",\"ev\":{\"calc_kwh\":%.3f,\"calc_kr\":%.3f,\"ctrl_kwh\":%.3f,\"ctrl_kr\":%.3f,\"unmet_kwh\":%.3f}",
                a.calc_ev_kwh, a.calc_ev_kr, a.ctrl_ev_kwh, a.ctrl_ev_kr, a.ev_unmet);
    std::printf(",\"safe_min\":%.0f,\"guard_events\":%.0f,\"program_writes\":%.0f}", a.safe_min, a.guard_events,
                a.program_writes);
}

// Vattenfall-style high-load time (tariff.h): Jan-Mar + Nov-Dec, weekdays 06-22, not holidays
bool high_load(int y, int m, int d, int hour) {
    if (!(m <= 3 || m >= 11) || hour < 6 || hour >= 22) return false;
    std::tm tmv{};
    tmv.tm_year = y - 1900; tmv.tm_mon = m - 1; tmv.tm_mday = d; tmv.tm_hour = 12;
    std::mktime(&tmv);
    if (tmv.tm_wday == 0 || tmv.tm_wday == 6) return false;
    return !tariff_is_holiday(y, m, d);
}

float median(std::vector<float> v) {
    if (v.empty()) return NAN;
    std::sort(v.begin(), v.end());
    return v[v.size() / 2];
}

}  // namespace

int main() {
    time_local_init();
    float cap = 0, mc = 0, md = 0, eff = 0.9f, mn = 5, mx = 95, gm = 0, kwp = 0;
    int ev_start = EV_WINDOW_START_H, ev_end = EV_WINDOW_END_H, ev_mode = -1, fuse = FUSE_NOMINAL_AMPS;
    std::vector<Day> days;
    char line[512];
    int rows_left = 0;
    while (std::fgets(line, sizeof line, stdin)) {
        if (line[0] == 'P') {
            std::sscanf(line + 1, "%f %f %f %f %f %f %f %d %d %d %d %f", &cap, &mc, &md, &eff, &mn, &mx, &gm,
                        &ev_start, &ev_end, &ev_mode, &fuse, &kwp);
        } else if (line[0] == 'D') {
            char date[16];
            int n = 0;
            if (std::sscanf(line + 1, "%15s %d", date, &n) != 2) continue;
            days.emplace_back();
            days.back().date = date;
            std::sscanf(date, "%d-%d-%d", &days.back().y, &days.back().m, &days.back().d);
            rows_left = n;
        } else if (line[0] == 'R' && !days.empty() && rows_left > 0) {
            float sp, buy, load, ev, sol, net, in, out;
            if (std::sscanf(line + 1, "%f %f %f %f %f %f %f %f", &sp, &buy, &load, &ev, &sol, &net, &in, &out) != 8) continue;
            Day& d = days.back();
            if (static_cast<int>(d.spot.size()) < PLAN_MAX_SLOTS) {
                d.spot.push_back(sp); d.buy.push_back(buy); d.load.push_back(load);
                d.ev.push_back(ev); d.solar.push_back(sol);
                d.calc_net += net; d.calc_in += in; d.calc_out += out;
            }
            rows_left--;
        }
    }
    if (days.empty() || cap <= 0) { std::printf("{\"error\":\"no input\"}\n"); return 1; }

    // The installation: the calculator's battery, fuse, EV energy and grid fees
    double ev_total = 0;
    std::vector<float> fee_hi, fee_lo;
    for (const Day& d : days) {
        for (size_t i = 0; i < d.spot.size(); i++) {
            ev_total += d.ev[i];
            const float fee = d.buy[i] - d.spot[i] * SPOT_VAT_FACTOR;
            (high_load(d.y, d.m, d.d, static_cast<int>(i)) ? fee_hi : fee_lo).push_back(fee);
        }
    }
    const float ev_daily = static_cast<float>(std::round(ev_total / days.size() * 10) / 10);
    const float fee_low = median(fee_lo);
    const float fee_high = fee_hi.empty() ? fee_low : median(fee_hi);

    // References: the firmware planner on the calculator's own inputs
    ref_set_battery(cap, mc, md, eff, mn, mx, MIN_SPREAD_SEK, gm);
    float* rin = ref_in_ptr();
    const int S = PLAN_MAX_SLOTS;
    float li = 0, lp = 0;
    std::vector<float> ideal(days.size()), prog(days.size());
    std::vector<float> ideal_in(days.size()), ideal_out(days.size()), prog_in(days.size()), prog_out(days.size());
    for (size_t di = 0; di < days.size(); di++) {
        const Day& d = days[di];
        const int n = static_cast<int>(d.spot.size());
        for (int i = 0; i < n; i++) {
            rin[0 * S + i] = d.buy[i];
            rin[1 * S + i] = d.load[i];
            rin[2 * S + i] = d.solar[i];
        }
        ref_plan_day(n, 60, li, lp);
        const float* o = ref_out_ptr();
        ideal[di] = o[0]; ideal_in[di] = o[3]; ideal_out[di] = o[4];
        prog[di] = o[6]; prog_in[di] = o[9]; prog_out[di] = o[10];
        li = o[5]; lp = o[11];
    }

    // The real controller in the world
    run_reset();
    run_set_plant(cap, md, eff, static_cast<int>(std::lround(mn)), static_cast<int>(std::lround(mx)), fuse,
                  BASE_LOAD_KW, ev_daily, ev_start, ev_end, kwp, fee_high, fee_low, MIN_SPREAD_SEK);
    if (ev_mode >= 0) run_set_ev_mode(ev_mode);
    run_set_options(mn, 0, 60, 0, 0, 0, 0);
    float* b = run_day_buffer();
    const int MS = MAX_SLOTS;
    for (const Day& d : days) {
        const int n = static_cast<int>(d.spot.size());
        for (int i = 0; i < n; i++) {
            b[0 * MS + i] = d.spot[i];
            b[1 * MS + i] = d.buy[i];
            b[2 * MS + i] = std::max(0.0f, d.load[i] - d.ev[i]);   // the controller plans its own EV
            b[3 * MS + i] = d.solar[i];
            b[4 * MS + i] = NAN;
            b[5 * MS + i] = d.ev[i];
        }
        run_add_day(d.y, d.m, d.d, n, 60, 1, 0);
    }
    run_days(static_cast<int>(days.size()));

    std::map<std::string, Agg> years;
    Agg tot;
    for (size_t di = 0; di < days.size(); di++) {
        const Day& d = days[di];
        const float* r = run_day_result(static_cast<int>(di));
        double cev = 0, cevkr = 0;
        for (size_t i = 0; i < d.ev.size(); i++) { cev += d.ev[i]; cevkr += d.ev[i] * d.buy[i]; }
        for (Agg* a : {&years[d.date.substr(0, 4)], &tot}) {
            a->days += 1;
            a->net[0] += d.calc_net; a->in_kwh[0] += d.calc_in; a->out_kwh[0] += d.calc_out;
            a->net[1] += ideal[di]; a->in_kwh[1] += ideal_in[di]; a->out_kwh[1] += ideal_out[di];
            a->net[2] += prog[di]; a->in_kwh[2] += prog_in[di]; a->out_kwh[2] += prog_out[di];
            a->net[3] += r[RR_BATTERY_KR]; a->in_kwh[3] += r[RR_IN]; a->out_kwh[3] += r[RR_OUT];
            a->calc_ev_kwh += cev; a->calc_ev_kr += cevkr;
            a->ctrl_ev_kwh += r[RR_EV_KWH]; a->ctrl_ev_kr += r[RR_EV_KR]; a->ev_unmet += r[RR_EV_UNMET];
            a->safe_min += r[RR_SAFE_MIN]; a->guard_events += r[RR_GUARD_EVENTS];
            a->program_writes += r[RR_PROGRAM_WRITES];
        }
    }

    std::printf("{\"first\":\"%s\",\"last\":\"%s\",\"ev_daily_kwh\":%.2f,\"ev_mode\":%d,\"fuse_amps\":%d,"
                "\"solar_kwp\":%.2f,\"grid_fee_high\":%.4f,\"grid_fee_low\":%.4f,\"segments\":%d,"
                "\"base_load_kw\":%.2f,\"house_days\":%d,\"total\":",
                days.front().date.c_str(), days.back().date.c_str(), ev_daily,
                ev_mode >= 0 ? ev_mode : static_cast<int>(EV_PRIORITY_MODE), fuse, kwp, fee_high, fee_low,
                MAX_PROG_SEGMENTS, BASE_LOAD_KW, run_house_days());
    print_agg(tot);
    std::printf(",\"years\":{");
    bool first = true;
    for (const auto& kv : years) {
        std::printf("%s\"%s\":", first ? "" : ",", kv.first.c_str());
        print_agg(kv.second);
        first = false;
    }
    std::printf("}}\n");
    return 0;
}

// The interactive simulator's JS hooks (sim/hal_stubs.cpp): never called here
// (the runner gives the controller the C++ world), but they must link.
extern "C" {
double js_now_utc() { return 0; }
int js_read_soc(float* out) { *out = 50; return 1; }
int js_fetch_prices(int, int, int, float*, int, int*) { return 0; }
int js_forecast(int, double, int, int, int, float*) { return 0; }
int js_write_program(const uint16_t*, int) { return 1; }
int js_read_live(float* out) { std::memset(out, 0, 5 * sizeof(float)); return 1; }
int js_read_meter(float* out) { std::memset(out, 0, 4 * sizeof(float)); return 1; }
int js_goe_status(float* out) { out[0] = 0; out[1] = 0; out[2] = -1; return 1; }
int js_goe_set_amps(int) { return 1; }
int js_flex_set(int, int) { return 1; }
void js_log(const char*, const char*) {}
void js_display(const char*, const char*, const char*, const char*) {}
}
