/**
 * @file tariff.cpp
 * @brief Swedish Vattenfall grid fee (nätavgift) calculation with holiday awareness
 *
 * Implements Vattenfall's "Tidstariff" (time-of-use tariff) for Swedish residential
 * customers. The grid fee has two tiers:
 *
 *   - Höglasttid (high-load): Winter weekdays 06:00-21:59, excluding public holidays
 *   - Låglasttid (low-load):  All other times (nights, weekends, holidays, summer)
 *
 * Winter months: January, February, March, November, December
 * Summer months: April through October (always low rate)
 *
 * The scheduler adds these grid fees to the ENTSO-E spot price to get the true
 * total cost of electricity per hour, which determines optimal charge/discharge timing.
 * A 10 öre/kWh difference in grid fee can shift charge windows by several hours.
 *
 * Holiday detection covers all Swedish public holidays ("röda dagar"), including
 * fixed-date holidays and moveable holidays that depend on Easter. Midsommarafton
 * and Midsommardagen have special rules (Saturday between June 20-26).
 *
 * References:
 *   - Vattenfall Elnät AB price list: https://www.vattenfall.se/elavtal/elpriser/timpris/
 *   - Swedish public holidays: SFS 1989:253 (Lag om allmänna helgdagar)
 *   - Easter algorithm: Anonymous Gregorian algorithm (Meeus, "Astronomical Algorithms")
 *
 * Dependencies:
 *   - config.h: GRID_FEE_HIGH, GRID_FEE_LOW (SEK/kWh from your Vattenfall invoice)
 *   - <time.h>: mktime() for date arithmetic (normalizing day-of-month overflow)
 */

#include "tariff.h"
#include "config.h"
#include "plant.h"
#include <ctime>

// ── Easter calculation (Anonymous Gregorian algorithm) ─────────────────────
/**
 * Compute the date of Easter Sunday for a given year using the Anonymous
 * Gregorian algorithm (also known as the "Meeus/Jones/Butcher" algorithm).
 *
 * This is the standard algorithm used by Western Christian churches and adopted
 * by Swedish law for determining moveable public holidays. It is valid for any
 * year in the Gregorian calendar (1583 onwards).
 *
 * The algorithm uses modular arithmetic on the year to account for the 19-year
 * Metonic cycle (lunar), century corrections, and leap year adjustments.
 *
 * @param year       Gregorian year (e.g. 2025)
 * @param month_out  Output: month of Easter Sunday (3 = March, 4 = April)
 * @param day_out    Output: day of Easter Sunday (1-31)
 */
static void easter_date(int year, int* month_out, int* day_out) {
    int a = year % 19;           /* Metonic cycle position (golden number - 1) */
    int b = year / 100;          /* Century number */
    int c = year % 100;          /* Year within century */
    int d = b / 4;               /* Century leap year correction */
    int e = b % 4;               /* Century non-leap remainder */
    int f = (b + 8) / 25;        /* Proemptosis correction (for Metonic cycle drift) */
    int g = (b - f + 1) / 3;     /* Metemptosis correction */
    int h = (19 * a + b - d - g + 15) % 30;  /* Epact (age of moon on March 21) */
    int i = c / 4;               /* Leap year correction within century */
    int k = c % 4;               /* Non-leap remainder within century */
    int l = (32 + 2 * e + 2 * i - h - k) % 7;  /* Day-of-week correction */
    int m = (a + 11 * h + 22 * l) / 451;        /* Leap month correction */
    *month_out = (h + l - 7 * m + 114) / 31;    /* March = 3, April = 4 */
    *day_out   = ((h + l - 7 * m + 114) % 31) + 1;
}

/**
 * Advance a date by a signed offset (number of days).
 *
 * Uses the C library mktime() to normalize the date after adding the offset
 * to tm_mday. mktime() handles month/year overflow automatically (e.g., adding
 * 39 days to April 20 correctly yields May 29).
 *
 * Works for offsets within approximately +/-365 days. Used to compute
 * Easter-relative holidays like Ascension (Easter + 39) and Good Friday (Easter - 2).
 *
 * @param year, month, day  Starting date
 * @param offset            Days to add (can be negative)
 * @param month_out         Output: resulting month (1-12)
 * @param day_out           Output: resulting day (1-31)
 */
static void advance_date(int year, int month, int day, int offset,
                         int* month_out, int* day_out) {
    struct tm t = {};
    t.tm_year = year - 1900;  /* tm_year is years since 1900 */
    t.tm_mon  = month - 1;    /* tm_mon is 0-based (0 = January) */
    t.tm_mday = day + offset;  /* mktime normalizes overflow (e.g. day 35 of March) */
    std::mktime(&t);  // normalizes the date
    *month_out = t.tm_mon + 1;
    *day_out   = t.tm_mday;
}

/**
 * Find the Saturday within a 7-day range starting at a given date.
 *
 * Used for two Swedish holidays with "the Saturday between" rules:
 *   - Midsommardagen: the Saturday between June 20 and June 26
 *   - Alla helgons dag: the Saturday between October 31 and November 6
 *
 * These "floating Saturday" holidays are unique to Sweden and defined by
 * SFS 1989:253 (amended 1991).
 *
 * @param year       Gregorian year
 * @param month      Month of the start date (1-12)
 * @param start_day  First possible day (e.g. 20 for Midsommar, 31 for Alla helgons)
 * @return           The day-of-month of the Saturday (may overflow into next month)
 */
static int saturday_between(int year, int month, int start_day) {
    struct tm t = {};
    t.tm_year = year - 1900;
    t.tm_mon  = month - 1;
    t.tm_mday = start_day;
    std::mktime(&t);
    /* tm_wday: 0 = Sunday, 1 = Monday, ..., 6 = Saturday.
     * Calculate days until the next Saturday (or 0 if already Saturday). */
    const int days_to_saturday = (6 - t.tm_wday + 7) % 7;
    return start_day + days_to_saturday;
}

// ── Holiday check ──────────────────────────────────────────────────────────

/**
 * Determine whether a given date is a Swedish public holiday ("röd dag").
 *
 * Covers all holidays defined in SFS 1989:253:
 *
 * Fixed-date holidays:
 *   - Dec 24 / Dec 31: Julafton / Nyårsafton — not "röda dagar" by law, but
 *     Vattenfall's höglasttid excludes them and energikalkyl tariff.py
 *     _swedish_holidays() has them; the two must agree.
 *   - Jan 1:  Nyårsdagen (New Year's Day)
 *   - Jan 6:  Trettondedag jul (Epiphany)
 *   - May 1:  Första maj (International Workers' Day)
 *   - Jun 6:  Sveriges nationaldag (National Day of Sweden)
 *   - Dec 25: Juldagen (Christmas Day)
 *   - Dec 26: Annandag jul (Boxing Day / St. Stephen's Day)
 *
 * Easter-dependent moveable holidays:
 *   - Långfredagen (Good Friday): Easter - 2 days
 *   - Påskdagen (Easter Sunday): the Easter date itself
 *   - Annandag påsk (Easter Monday): Easter + 1 day
 *   - Kristi himmelsfärdsdag (Ascension Day): Easter + 39 days (always a Thursday)
 *   - Pingstdagen (Whit Sunday / Pentecost): Easter + 49 days
 *
 * Floating Saturday holidays:
 *   - Midsommardagen: Saturday between June 20-26
 *   - Midsommarafton: Friday before Midsommardagen (treated as holiday for tariff)
 *   - Alla helgons dag: Saturday between October 31 and November 6
 *
 * NOTE: Midsommarafton is not technically a "röd dag" by law, but Vattenfall
 * and most grid operators treat it as low-load since virtually no one works.
 * Including it here is conservative (results in lower grid fee = cheaper charging).
 *
 * @param year, month, day  Date to check (Gregorian)
 * @return true if the date is a Swedish public holiday
 */
bool tariff_is_holiday(int year, int month, int day) {
    // ── Fixed holidays ──
    if (month == 1  && day == 1)  { return true; }  // Nyårsdagen
    if (month == 1  && day == 6)  { return true; }  // Trettondedag jul
    if (month == 5  && day == 1)  { return true; }  // Första maj
    if (month == 6  && day == 6)  { return true; }  // Sveriges nationaldag
    if (month == 12 && day == 24) { return true; }  // Julafton (de facto, as energikalkyl)
    if (month == 12 && day == 25) { return true; }  // Juldagen
    if (month == 12 && day == 26) { return true; }  // Annandag jul
    if (month == 12 && day == 31) { return true; }  // Nyårsafton (de facto, as energikalkyl)

    // ── Easter-dependent holidays ──
    int em, ed;
    easter_date(year, &em, &ed);

    int hm, hd;

    // Långfredagen (Good Friday) = Easter - 2
    advance_date(year, em, ed, -2, &hm, &hd);
    if (month == hm && day == hd) { return true; }

    // Påskdagen (Easter Sunday)
    if (month == em && day == ed) { return true; }

    // Annandag påsk (Easter Monday) = Easter + 1
    advance_date(year, em, ed, 1, &hm, &hd);
    if (month == hm && day == hd) { return true; }

    // Kristi himmelsfärdsdag (Ascension) = Easter + 39
    advance_date(year, em, ed, 39, &hm, &hd);
    if (month == hm && day == hd) { return true; }

    // Pingstdagen (Whit Sunday) = Easter + 49
    advance_date(year, em, ed, 49, &hm, &hd);
    if (month == hm && day == hd) { return true; }

    // ── Floating Saturday holidays ──

    // Midsommardagen = Saturday between June 20-26
    if (month == 6) {
        const int midsommar = saturday_between(year, 6, 20);
        if (day == midsommar) { return true; }
        // Midsommarafton (day before) — not a legal holiday but treated as one
        // for grid tariff purposes by Vattenfall and most Swedish grid operators
        if (day == midsommar - 1) { return true; }
    }

    // Alla helgons dag = Saturday between Oct 31 - Nov 6
    // The search starts at Oct 31, but the resulting Saturday may fall in November
    // (e.g. if Oct 31 is a Sunday, the Saturday is Nov 6). We use mktime to
    // normalize the date and then compare against the input month/day.
    if (month == 10 || month == 11) {
        const int ahd = saturday_between(year, 10, 31);
        struct tm t = {};
        t.tm_year = year - 1900;
        t.tm_mon = 9;  // October (0-based)
        t.tm_mday = ahd;
        std::mktime(&t);  /* Normalizes: if ahd > 31, rolls into November */
        if (month == t.tm_mon + 1 && day == t.tm_mday) { return true; }
    }

    return false;
}

/**
 * Calculate the Vattenfall grid fee (nätavgift) for a specific hour.
 *
 * Implements Vattenfall Elnät AB's two-tier time-of-use tariff:
 *
 *   Höglasttid (high-load, GRID_FEE_HIGH):
 *     - Winter months ONLY: Jan, Feb, Mar, Nov, Dec
 *     - Weekdays ONLY: Monday through Friday
 *     - Daytime ONLY: 06:00 to 21:59 (16 hours)
 *     - NOT on public holidays
 *     All four conditions must be true simultaneously.
 *
 *   Låglasttid (low-load, GRID_FEE_LOW):
 *     - Everything else: summer, nights (22-05), weekends, holidays
 *
 * The fee values (SEK/kWh including 25% VAT) come from config.h and should be
 * updated when Vattenfall publishes new prices (typically January 1 each year).
 *
 * 2026 values: GRID_FEE_HIGH = 0.765 + 0.450 = 1.215, GRID_FEE_LOW =
 * 0.305 + 0.450 = 0.755 SEK/kWh. Both INCLUDE the energy tax (energiskatt).
 *
 * @param hour        Hour of day (0-23)
 * @param weekday     tm_wday: 0 = Sunday, 1 = Monday .. 6 = Saturday
 * @param month       Month (1-12)
 * @param is_holiday  Whether the date is a Swedish public holiday (from tariff_is_holiday)
 * @return            Grid fee in SEK/kWh
 */
float tariff_grid_fee(int hour, int weekday, int month, bool is_holiday) {
    /* Winter = months with high grid demand (heating season).
     * January (1), February (2), March (3), November (11), December (12). */
    const bool winter = (month <= 3 || month >= 11);

    /* Weekday check: Monday (1) through Friday (5) are working days.
     * Saturday (6) and Sunday (7) always get the low rate. */
    const bool workday = (weekday >= 1 && weekday <= 5);

    /* Höglasttid requires ALL conditions: winter AND workday AND not holiday AND daytime.
     * The 06-22 range covers the typical Swedish work/commute/cooking pattern. */
    if (winter && workday && !is_holiday && hour >= 6 && hour < 22) {
        return plant().grid_fee_high_sek;
    }
    return plant().grid_fee_low_sek;
}

float tariff_buy_cost(float spot_sek, float grid_fee_sek) {
    return spot_sek * SPOT_VAT_FACTOR + grid_fee_sek;
}

float tariff_export_value(float spot_sek) {
    if (!(EXPORT_PRICE_FACTOR > 0.0f)) {
        return 0.0f;
    }
    const float v = spot_sek * EXPORT_PRICE_FACTOR - EXPORT_FEE_SEK;
    return v > 0.0f ? v : 0.0f;
}
