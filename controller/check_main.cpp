// Controller check for energikalkyl: the calculator's hourly inputs through the
// controller firmware's planner (sim/batch.cpp bt_plan_day → firmware
// plan_shared_day / bat_plan_program), one day at a time. Same chains as the
// simulator's "Validate calculator" (energy-scheduler-sim sim-batch.js):
//   ideal      firmware planner on the calculator's own inputs (parity)
//   progperf   the plan as a Deye program (≤ MAX_PROG_SEGMENTS points)
//   ctrlperf   controller: EV planned by the firmware on its fuse budget
//   ctrlmodel  the same planned with a forecast (persistence = yesterday)
// Not included: the simulated Deye physics and fuse guard (simulator only).
//
// Run as a separate process (controller_check.py): time_local_init() sets the
// process time zone to Europe/Stockholm.
//
// stdin, one line each:
//   P capacity_kwh max_charge_kw max_discharge_kw efficiency min_soc% max_soc% grid_max_kw
//     ev_win_start_h ev_win_end_h ev_mode(0 battery,1 ev,2 auto,-1 firmware) persistence(0/1)
//   D yyyy-mm-dd n                      (a day with n hourly rows follows)
//   R spot_sek buy_sek load_kwh ev_kwh solar_kwh calc_net_sek calc_in_kwh calc_out_kwh
// stdout: one JSON object.
#include <cstdio>
#include <cstring>
#include <cmath>
#include <map>
#include <string>
#include <vector>
#include <algorithm>

#include "config.h"
#include "time_local.h"
#include "battery_plan.h"
#include "tou_window.h"

extern "C" {
float* bt_in_ptr();
float* bt_out_ptr();
int* bt_ev_ptr();
void bt_defaults();
void bt_set_battery(float, float, float, float, float, float, float, int);
void bt_set_grid(float, float, int, int, float, float);
void bt_set_ev(int, int, int, float, int);
int bt_plan_day(int, int, int, int, int, float, float, float, float, float, int);
}

namespace {

struct Day {
    std::string date;
    std::vector<float> spot, buy, house, ev, solar;
    double calc_net = 0, calc_in = 0, calc_out = 0;
};

struct Agg {
    double days = 0;
    double net[5] = {0, 0, 0, 0, 0};       // calc, ideal, progperf, ctrlperf, ctrlmodel
    double out_kwh[5] = {0, 0, 0, 0, 0};
    double calc_ev_kwh = 0, calc_ev_kr = 0, ctrl_ev_kwh = 0, ctrl_ev_kr = 0;
};

void print_agg(const Agg& a) {
    static const char* names[5] = {"calc", "ideal", "progperf", "ctrlperf", "ctrlmodel"};
    std::printf("{\"days\":%.0f", a.days);
    for (int k = 0; k < 5; k++)
        std::printf(",\"%s\":{\"net\":%.3f,\"out_kwh\":%.3f}", names[k], a.net[k], a.out_kwh[k]);
    std::printf(",\"ev\":{\"calc_kwh\":%.3f,\"calc_kr\":%.3f,\"ctrl_kwh\":%.3f,\"ctrl_kr\":%.3f}}",
                a.calc_ev_kwh, a.calc_ev_kr, a.ctrl_ev_kwh, a.ctrl_ev_kr);
}

}  // namespace

int main() {
    time_local_init();
    float cap = 0, mc = 0, md = 0, eff = 0, mn = 0, mx = 0, gm = 0;
    int ws = EV_WINDOW_START_H, we = EV_WINDOW_END_H, mode = -1, persistence = 1;
    std::vector<Day> days;
    char tag[4];
    while (std::scanf("%3s", tag) == 1) {
        if (tag[0] == 'P') {
            if (std::scanf("%f %f %f %f %f %f %f %d %d %d %d", &cap, &mc, &md, &eff, &mn, &mx, &gm,
                           &ws, &we, &mode, &persistence) != 11) return 2;
        } else if (tag[0] == 'D') {
            char date[16];
            int n;
            if (std::scanf("%15s %d", date, &n) != 2) return 2;
            days.emplace_back();
            days.back().date = date;
        } else if (tag[0] == 'R') {
            float sp, buy, load, ev, sol, net, in, out;
            if (std::scanf("%f %f %f %f %f %f %f %f", &sp, &buy, &load, &ev, &sol, &net, &in, &out) != 8) return 2;
            if (days.empty()) return 2;
            Day& d = days.back();
            if (static_cast<int>(d.spot.size()) >= PLAN_MAX_SLOTS) continue;
            d.spot.push_back(sp); d.buy.push_back(buy); d.house.push_back(std::max(0.0f, load - ev));
            d.ev.push_back(ev); d.solar.push_back(sol);
            d.calc_net += net; d.calc_in += in; d.calc_out += out;
        } else {
            return 2;
        }
    }
    if (days.empty() || cap <= 0) { std::printf("{\"error\":\"no input\"}\n"); return 1; }

    // Same set-up as the simulator's datasetFromEnergikalkyl()
    double ev_total = 0;
    for (const Day& d : days) for (float e : d.ev) ev_total += e;
    const float ev_daily = static_cast<float>(std::round(ev_total / days.size() * 10) / 10);
    const int ev_mode = mode >= 0 ? mode : static_cast<int>(EV_PRIORITY_MODE);
    bt_defaults();
    bt_set_battery(cap, mc, md, eff, mn, mx, 0.20f, MAX_PROG_SEGMENTS);
    bt_set_grid(gm, BASE_LOAD_KW, 0, 0, 0.0f, EXPORT_FEE_SEK);
    bt_set_ev(ev_daily > 0.1f, ws, we, ev_daily, ev_mode);

    float* in = bt_in_ptr();
    const int S = PLAN_MAX_SLOTS;
    float lvl[4] = {0, 0, 0, 0};
    std::map<std::string, Agg> years;
    Agg tot;
    const Day* prev = nullptr;
    for (const Day& d : days) {
        const int n = static_cast<int>(d.spot.size());
        if (n == 0) continue;
        const bool persist = persistence && prev && static_cast<int>(prev->house.size()) == n;
        for (int i = 0; i < n; i++) {
            in[0 * S + i] = d.spot[i];
            in[1 * S + i] = d.buy[i];
            in[2 * S + i] = d.house[i];
            in[3 * S + i] = d.solar[i];
            in[4 * S + i] = persist ? prev->house[i] : d.house[i];
            in[5 * S + i] = persist ? prev->solar[i] : d.solar[i];
            in[6 * S + i] = d.ev[i];
        }
        int y = 0, m = 0, dd = 0;
        std::sscanf(d.date.c_str(), "%d-%d-%d", &y, &m, &dd);
        // ctrlmodel carries its own end level as the next day's SOC (the
        // simulator uses its simulated Deye's SOC)
        const float ctrl_soc = mn + lvl[3] / cap * 100.0f;
        bt_plan_day(y, m, dd, n, 60, lvl[0], lvl[1], lvl[2], lvl[3], ctrl_soc, persist ? 0 : 1);
        const float* o = bt_out_ptr();
        const int* amps = bt_ev_ptr();
        for (int k = 0; k < 4; k++) lvl[k] = o[k * 6 + 5];
        double ev_kwh = 0, ev_kr = 0, cev_kwh = 0, cev_kr = 0;
        for (int i = 0; i < n; i++) {
            const double kwh = amps[i] * FUSE_PHASES * FUSE_VOLTAGE / 1000.0;   // 60-min slots
            ev_kwh += kwh; ev_kr += kwh * d.buy[i];
            cev_kwh += d.ev[i]; cev_kr += d.ev[i] * d.buy[i];
        }
        for (Agg* a : {&years[d.date.substr(0, 4)], &tot}) {
            a->days += 1;
            a->net[0] += d.calc_net;
            a->out_kwh[0] += d.calc_out;
            for (int k = 0; k < 4; k++) {
                a->net[k + 1] += o[k * 6];
                a->out_kwh[k + 1] += o[k * 6 + 4];
            }
            a->calc_ev_kwh += cev_kwh; a->calc_ev_kr += cev_kr;
            a->ctrl_ev_kwh += ev_kwh; a->ctrl_ev_kr += ev_kr;
        }
        prev = &d;
    }

    std::printf("{\"first\":\"%s\",\"last\":\"%s\",\"ev_daily_kwh\":%.2f,\"ev_mode\":%d,"
                "\"segments\":%d,\"base_load_kw\":%.2f,\"total\":",
                days.front().date.c_str(), days.back().date.c_str(), ev_daily, ev_mode,
                MAX_PROG_SEGMENTS, BASE_LOAD_KW);
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
