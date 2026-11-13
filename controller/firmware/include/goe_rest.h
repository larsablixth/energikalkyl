#pragma once

// bool is a built-in type in C++14 — no header needed

// go-e Charger (Gemini) local HTTP API v2.
//   status: GET /api/status?filter=car,amp,frc   (small response, fits buffer)
//   set:    GET /api/set?amx=N   amx = current limit WITHOUT flash write
//           GET /api/set?frc=1   force OFF (pause charging)
//           GET /api/set?frc=0   release our force-off (back to neutral)
// frc: 0 = neutral (charger decides), 1 = force off, 2 = force on.
// `amp` would persist to flash on every write — never used for control.

typedef struct {
    bool  car_connected;  // car state 2..4 (charging / waiting / complete)
    bool  charging;       // car state 2
    int   current_amps;   // effective setpoint: 0 if forced off, else amp
    int   force_state;    // frc (0 neutral, 1 off, 2 on)
    float soc_percent;    // -1 if unknown
} GoeStatus;

bool goe_get_status(GoeStatus* status_out);

// Set the charging current limit (GOE_MIN_AMPS..GOE_MAX_AMPS) via amx.
// Does NOT touch frc (a user force-off in the app stays in force).
// Out-of-range values are rejected (returns false) — use
// goe_stop_charging() to pause. Response is checked.
bool goe_set_amps(int max_amps);

// Pause charging (frc=1). Response is checked.
bool goe_stop_charging(void);

// Undo our pause (frc=0 = neutral). Only call after goe_stop_charging().
bool goe_release_stop(void);
