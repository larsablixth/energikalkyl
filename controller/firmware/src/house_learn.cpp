// house_learn.cpp — fit the house load model to measurements (see house_learn.h)

#include "house_learn.h"
#include "config.h"
#include <cmath>
#include <cstring>

namespace {

constexpr int   MIN_VALID_HOURS = 20;
constexpr float MAX_HOUR_KWH    = 40.0f;   // above any 3×25..63 A house in one hour

// Heating electricity per unit of heat loss at temperature t. While the heat
// pump covers the demand this is ΔT / COP(t); in deep cold, where the prior
// model says the electric heater helps, it includes the heater's share so
// that those hours do not masquerade as a leakier house.
float heating_per_h_loss(const HouseLoadModel& m, float t) {
    if (m.h_loss_kw_per_c > 0.0f) {
        return house_heating_kw(m, t) / m.h_loss_kw_per_c;
    }
    const float dt = m.t_indoor_c - t;
    return (dt > 0.0f) ? dt / house_heat_pump_cop(m, t) : 0.0f;
}

float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

}  // namespace

void house_learn_reset(HouseLearnState* s) {
    *s = HouseLearnState{};
}

float house_learn_day_x(const HouseLoadModel& prior, const float* hour_temp_c) {
    float x = 0.0f;
    for (int h = 0; h < 24; h++) {
        x += heating_per_h_loss(prior, hour_temp_c[h]);
    }
    return x;
}

bool house_learn_add_day(HouseLearnState* s, const HouseLoadModel& prior,
                         const float* hour_kwh, const float* hour_temp_c,
                         float memory_days) {
    /* Hours with both a plausible energy and a plausible temperature. */
    int n = 0;
    float y = 0.0f, x = 0.0f, heat_sum = 0.0f;
    bool ok[24];
    float heat[24];
    for (int h = 0; h < 24; h++) {
        const float e = hour_kwh[h];
        const float t = hour_temp_c[h];
        ok[h] = std::isfinite(e) && e >= 0.0f && e <= MAX_HOUR_KWH && house_temp_plausible(t);
        heat[h] = 0.0f;
        if (!ok[h]) continue;
        n++;
        y += e;
        x += heating_per_h_loss(prior, t);
        heat[h] = house_heating_kw(prior, t);
        heat_sum += heat[h];
    }
    if (n < MIN_VALID_HOURS) {
        return false;
    }
    /* Scale a day with a few missing hours up to 24 h. */
    const float scale = 24.0f / static_cast<float>(n);
    const float y_day = y * scale;
    const float x_day = x * scale;
    if (!(y_day > 0.0f)) {
        return false;            /* a day with no consumption at all: meter fault */
    }

    /* Regression sums, older days fading. */
    const float keep = (memory_days > 0.0f) ? (1.0f - 1.0f / memory_days) : 1.0f;
    s->w   = s->w   * keep + 1.0f;
    s->sx  = s->sx  * keep + x_day;
    s->sy  = s->sy  * keep + y_day;
    s->sxx = s->sxx * keep + x_day * x_day;
    s->sxy = s->sxy * keep + x_day * y_day;
    s->days++;

    /* Habit: hour's energy relative to the day's mean, minus the part the
     * model already explains through that hour's temperature. Zero-mean over
     * the day by construction. Running average, then a 30-day EMA. */
    const float mean_e = y / static_cast<float>(n);
    const float mean_heat = heat_sum / static_cast<float>(n);
    const float alpha = (s->offset_days < 30u)
        ? 1.0f / static_cast<float>(s->offset_days + 1u) : 1.0f / 30.0f;
    for (int h = 0; h < 24; h++) {
        if (!ok[h]) continue;
        const float dev = (hour_kwh[h] - mean_e) - (heat[h] - mean_heat);
        s->hour_offset_kw[h] += alpha * (dev - s->hour_offset_kw[h]);
    }
    s->offset_days++;
    return true;
}

int house_learn_model(const HouseLearnState* s, const HouseLoadModel& prior,
                      HouseLoadModel* out) {
    *out = prior;
    if (!s || s->version != HOUSE_LEARN_VERSION ||
        s->w < static_cast<float>(HOUSE_LEARN_MIN_DAYS)) {
        return HOUSE_FIT_PRIOR;
    }
    const float xm = s->sx / s->w;
    const float ym = s->sy / s->w;
    const float var_x = s->sxx / s->w - xm * xm;
    const float cov_xy = s->sxy / s->w - xm * ym;

    /* Slope (heat loss) only when the days differ enough in temperature and
     * the result is physically sensible; otherwise keep the prior's. */
    int fit = HOUSE_FIT_LEVEL;
    float h_loss = prior.h_loss_kw_per_c;
    if (var_x > HOUSE_LEARN_MIN_X_SPREAD * HOUSE_LEARN_MIN_X_SPREAD) {
        const float slope = cov_xy / var_x;
        if (slope >= HOUSE_LEARN_H_LOSS_MIN && slope <= HOUSE_LEARN_H_LOSS_MAX) {
            h_loss = slope;
            fit = HOUSE_FIT_FULL;
        }
    }
    /* Level: A = 24 × base + hot water. */
    const float a = ym - h_loss * xm;
    out->h_loss_kw_per_c = h_loss;
    out->base_kw = clampf((a - prior.dhw_kwh_per_day) / 24.0f,
                          HOUSE_LEARN_BASE_MIN_KW, HOUSE_LEARN_BASE_MAX_KW);
    return fit;
}

float house_learn_hour_offset_kw(const HouseLearnState* s, int local_hour) {
    const int h = ((local_hour % 24) + 24) % 24;
    if (!s || s->version != HOUSE_LEARN_VERSION ||
        s->offset_days < static_cast<uint32_t>(HOUSE_LEARN_MIN_DAYS)) {
        return HOUSE_HOUR_OFFSET_KW[h];
    }
    return s->hour_offset_kw[h];
}

float house_expected_load_kw(const HouseLearnState* s, const HouseLoadModel& prior,
                             float t_outdoor_c, int local_hour) {
    HouseLoadModel m;
    house_learn_model(s, prior, &m);
    const float kw = house_load_kw(m, t_outdoor_c) + house_learn_hour_offset_kw(s, local_hour);
    return (kw > HOUSE_LOAD_MIN_KW) ? kw : HOUSE_LOAD_MIN_KW;
}

// ── Saving what was learned ───────────────────────────────────────────────

namespace {

const uint8_t BLOB_MAGIC[4] = {'H', 'L', 'S', '1'};

uint32_t crc32_of(const uint8_t* data, int len) {
    uint32_t crc = 0xFFFFFFFFu;
    for (int i = 0; i < len; i++) {
        crc ^= data[i];
        for (int b = 0; b < 8; b++) {
            crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
        }
    }
    return crc ^ 0xFFFFFFFFu;
}

bool state_sane(const HouseLearnState& s) {
    if (s.version != HOUSE_LEARN_VERSION) return false;
    const float v[] = {s.w, s.sx, s.sy, s.sxx, s.sxy};
    for (float f : v) {
        if (!std::isfinite(f) || f < 0.0f) return false;
    }
    if (s.w > static_cast<float>(s.days) + 0.5f) return false;   /* weights never exceed days */
    for (int h = 0; h < 24; h++) {
        if (!std::isfinite(s.hour_offset_kw[h]) || std::fabs(s.hour_offset_kw[h]) > 50.0f) return false;
    }
    return true;
}

}  // namespace

int house_learn_serialize(const HouseLearnState* s, uint8_t* buf, int buf_size) {
    const int body = static_cast<int>(sizeof(HouseLearnState));
    const int total = 4 + body + 4;
    if (!s || !buf || buf_size < total) {
        return 0;
    }
    std::memcpy(buf, BLOB_MAGIC, 4);
    std::memcpy(buf + 4, s, static_cast<size_t>(body));
    const uint32_t crc = crc32_of(buf, 4 + body);
    for (int i = 0; i < 4; i++) {
        buf[4 + body + i] = static_cast<uint8_t>((crc >> (8 * i)) & 0xFFu);
    }
    return total;
}

bool house_learn_deserialize(const uint8_t* buf, int len, HouseLearnState* out) {
    const int body = static_cast<int>(sizeof(HouseLearnState));
    const int total = 4 + body + 4;
    if (!buf || !out || len != total || std::memcmp(buf, BLOB_MAGIC, 4) != 0) {
        return false;
    }
    uint32_t crc = 0;
    for (int i = 0; i < 4; i++) {
        crc |= static_cast<uint32_t>(buf[4 + body + i]) << (8 * i);
    }
    if (crc != crc32_of(buf, 4 + body)) {
        return false;
    }
    HouseLearnState s;
    std::memcpy(static_cast<void*>(&s), buf + 4, static_cast<size_t>(body));
    if (!state_sane(s)) {
        return false;
    }
    *out = s;
    return true;
}
