#pragma once
// Expected house electricity load as a function of outdoor temperature.
// Pure functions (no hardware, no logging) — unit-tested natively
// (test/test_house_load) and used unchanged by the backtester.
//
// The model is energikalkyl's heating.py:
//
//   load [kW] = base load                       (always-on, lighting, cooking…)
//             + hot water                       (kWh/day spread over 24 h)
//             + space heating electricity:
//                 heat demand = H_LOSS × max(0, T_indoor − T_outdoor)   [kW thermal]
//                 heat pump covers up to HP_MAX_HEAT at COP(T_outdoor)
//                 an electric heater (COP 1) covers what is left, up to its size
//
// The numbers (config.h, HOUSE_*) are a CALIBRATION: they are fitted offline
// from old consumption data and old weather data (energikalkyl
// fit_heating_model) and typed into config.h. The controller does not learn
// them itself.
//
// The outdoor temperature comes from a forecast (PipelineIO::forecast_temp_c)
// when one is available, otherwise from the normal temperature of the month
// (house_normal_temp_c).

struct HouseLoadModel {
    float base_kw          = 0.0f;   // non-heating load, kW
    float dhw_kwh_per_day  = 0.0f;   // hot water electricity, kWh/day
    float h_loss_kw_per_c  = 0.0f;   // heat loss, kW thermal per °C
    float t_indoor_c       = 21.0f;  // indoor setpoint, °C
    float cop_base         = 3.0f;   // heat pump COP at 0 °C outdoor
    float cop_slope        = 0.0f;   // COP change per °C outdoor
    float cop_min          = 1.0f;   // COP never below this
    float hp_max_heat_kw   = 0.0f;   // heat pump max heat output, kW thermal
    float elpatron_kw      = 0.0f;   // supplementary electric heater, kW
};

// The calibrated model from config.h (HOUSE_* constants).
HouseLoadModel house_load_default(void);

// Heat pump COP at the given outdoor temperature.
float house_heat_pump_cop(const HouseLoadModel& m, float t_outdoor_c);

// Electricity for space heating (heat pump + electric heater), kW.
float house_heating_kw(const HouseLoadModel& m, float t_outdoor_c);

// Total expected house load, kW.
float house_load_kw(const HouseLoadModel& m, float t_outdoor_c);

// Normal (average) outdoor temperature of a month, °C (HOUSE_NORMAL_TEMP_C).
// month 1..12; anything else is clamped into that range.
float house_normal_temp_c(int month);

// True if t looks like a real outdoor temperature (finite, −60..+60 °C).
bool house_temp_plausible(float t_outdoor_c);
