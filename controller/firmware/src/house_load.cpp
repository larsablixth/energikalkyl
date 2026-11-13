// house_load.cpp — expected house load vs outdoor temperature (see house_load.h)

#include "house_load.h"
#include "config.h"
#include <cmath>

HouseLoadModel house_load_default(void) {
    HouseLoadModel m;
    m.base_kw         = HOUSE_BASE_LOAD_KW;
    m.dhw_kwh_per_day = HOUSE_DHW_KWH_PER_DAY;
    m.h_loss_kw_per_c = HOUSE_H_LOSS_KW_PER_C;
    m.t_indoor_c      = HOUSE_T_INDOOR_C;
    m.cop_base        = HOUSE_HP_COP_BASE;
    m.cop_slope       = HOUSE_HP_COP_SLOPE;
    m.cop_min         = HOUSE_HP_COP_MIN;
    m.hp_max_heat_kw  = HOUSE_HP_MAX_HEAT_KW;
    m.elpatron_kw     = HOUSE_ELPATRON_KW;
    return m;
}

float house_heat_pump_cop(const HouseLoadModel& m, float t_outdoor_c) {
    const float cop = m.cop_base + m.cop_slope * t_outdoor_c;
    return (cop > m.cop_min) ? cop : m.cop_min;
}

float house_heating_kw(const HouseLoadModel& m, float t_outdoor_c) {
    const float delta_t = m.t_indoor_c - t_outdoor_c;
    if (delta_t <= 0.0f) {
        return 0.0f;                       /* no heating needed */
    }
    float demand = m.h_loss_kw_per_c * delta_t;   /* kW thermal */

    /* Heat pump first, up to its maximum heat output. */
    const float hp_heat = (demand < m.hp_max_heat_kw) ? demand : m.hp_max_heat_kw;
    float elec = (hp_heat > 0.0f) ? hp_heat / house_heat_pump_cop(m, t_outdoor_c) : 0.0f;
    demand -= hp_heat;

    /* Electric heater (COP 1) covers the rest, up to its size. */
    if (demand > 0.0f) {
        elec += (demand < m.elpatron_kw) ? demand : m.elpatron_kw;
    }
    return elec;
}

float house_load_kw(const HouseLoadModel& m, float t_outdoor_c) {
    return m.base_kw + m.dhw_kwh_per_day / 24.0f + house_heating_kw(m, t_outdoor_c);
}

float house_normal_temp_c(int month) {
    if (month < 1) month = 1;
    if (month > 12) month = 12;
    return HOUSE_NORMAL_TEMP_C[month - 1];
}

bool house_temp_plausible(float t_outdoor_c) {
    return std::isfinite(t_outdoor_c) && t_outdoor_c >= -60.0f && t_outdoor_c <= 60.0f;
}
