"""
BEMServer-inspired local data store with cleansing.

Lightweight alternative to full BEMServer stack. Provides:
- SQLite storage for consumption + temperature timeseries
- Data cleansing: outlier removal, gap filling, completeness check
- Interface compatible with energy_analysis.analyze()

Mirrors BEMServer's cleansing operations (cleanup.py, forward_fill.py,
completeness.py) without requiring PostgreSQL, Celery, or Redis.
"""

import os
import sqlite3
from collections import defaultdict

CACHE_DIR = ".bemserver_cache"
DB_PATH = os.path.join(CACHE_DIR, "timeseries.db")

# Cleansing bounds (domain-specific)
CONSUMPTION_MIN = 0.0    # kWh/h
CONSUMPTION_MAX = 50.0   # kWh/h (50 kWh single hour = extreme)
TEMPERATURE_MIN = -50.0  # °C
TEMPERATURE_MAX = 50.0   # °C


def _init_db():
    """Create SQLite tables if they don't exist."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS consumption (
            date TEXT NOT NULL,
            hour INTEGER NOT NULL,
            kwh REAL,
            source TEXT DEFAULT 'unknown',
            PRIMARY KEY (date, hour)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS temperature (
            date TEXT NOT NULL,
            hour INTEGER NOT NULL,
            temp_c REAL,
            station_id TEXT DEFAULT '',
            PRIMARY KEY (date, hour)
        )
    """)
    conn.commit()
    return conn


def _store_consumption(conn, hourly_data, source="vattenfall"):
    """Upsert hourly consumption data."""
    conn.executemany(
        "INSERT OR REPLACE INTO consumption (date, hour, kwh, source) VALUES (?, ?, ?, ?)",
        [(r["date"], r["hour"], r["kwh"], source) for r in hourly_data]
    )
    conn.commit()


def _store_temperature(conn, temps_data, station_id=""):
    """Upsert hourly temperature data from weather.load_temperatures() format."""
    rows = []
    for date_str, hourly in temps_data.items():
        for hour, temp in hourly:
            rows.append((date_str, hour, temp, station_id))
    conn.executemany(
        "INSERT OR REPLACE INTO temperature (date, hour, temp_c, station_id) VALUES (?, ?, ?, ?)",
        rows
    )
    conn.commit()


def _cleanse_consumption(conn):
    """Remove outliers: set out-of-bounds values to NULL."""
    conn.execute(
        "UPDATE consumption SET kwh = NULL WHERE kwh < ? OR kwh > ?",
        (CONSUMPTION_MIN, CONSUMPTION_MAX)
    )
    conn.commit()


def _cleanse_temperature(conn):
    """Remove outliers: set out-of-bounds values to NULL."""
    conn.execute(
        "UPDATE temperature SET temp_c = NULL WHERE temp_c < ? OR temp_c > ?",
        (TEMPERATURE_MIN, TEMPERATURE_MAX)
    )
    conn.commit()


def _fill_gaps(conn, table, value_col):
    """Fill single-hour gaps via linear interpolation (1-2 hour gaps only)."""
    # Find gaps: rows where value is NULL but neighbors exist
    rows = conn.execute(f"""
        SELECT date, hour FROM {table} WHERE {value_col} IS NULL
    """).fetchall()

    updates = []
    for date, hour in rows:
        # Look for neighbors in same day
        prev = conn.execute(f"""
            SELECT {value_col} FROM {table}
            WHERE date = ? AND hour = ? AND {value_col} IS NOT NULL
        """, (date, hour - 1)).fetchone()
        next_val = conn.execute(f"""
            SELECT {value_col} FROM {table}
            WHERE date = ? AND hour = ? AND {value_col} IS NOT NULL
        """, (date, hour + 1)).fetchone()

        if prev and next_val:
            # Interpolate
            interpolated = (prev[0] + next_val[0]) / 2
            updates.append((interpolated, date, hour))
        elif prev:
            # Forward fill
            updates.append((prev[0], date, hour))
        elif next_val:
            # Backward fill
            updates.append((next_val[0], date, hour))

    if updates:
        conn.executemany(
            f"UPDATE {table} SET {value_col} = ? WHERE date = ? AND hour = ?",
            updates
        )
        conn.commit()


def _compute_completeness(conn):
    """Compute data completeness per month."""
    result = {}
    for table, col in [("consumption", "kwh"), ("temperature", "temp_c")]:
        rows = conn.execute(f"""
            SELECT substr(date, 1, 7) AS month,
                   COUNT(*) AS total,
                   SUM(CASE WHEN {col} IS NOT NULL THEN 1 ELSE 0 END) AS valid
            FROM {table}
            GROUP BY month
            ORDER BY month
        """).fetchall()
        result[table] = {
            month: round(valid / total, 3) if total > 0 else 0
            for month, total, valid in rows
        }
    return result


def _read_consumption(conn):
    """Read cleansed consumption as list of dicts for energy_analysis."""
    rows = conn.execute("""
        SELECT date, hour, kwh FROM consumption
        WHERE kwh IS NOT NULL
        ORDER BY date, hour
    """).fetchall()
    return [{"date": d, "hour": h, "kwh": v} for d, h, v in rows]


def _read_temperatures(conn):
    """Read cleansed temperatures in weather.load_temperatures() format."""
    rows = conn.execute("""
        SELECT date, hour, temp_c FROM temperature
        WHERE temp_c IS NOT NULL
        ORDER BY date, hour
    """).fetchall()
    temps = defaultdict(list)
    for date, hour, temp in rows:
        temps[date].append((hour, temp))
    return dict(temps)


def store_and_cleanse(hourly_consumption, hourly_temperatures,
                      source="vattenfall", station_id=""):
    """
    Store raw data in SQLite, run cleansing pipeline, return cleansed data.

    Args:
        hourly_consumption: list of {"date": str, "hour": int, "kwh": float}
        hourly_temperatures: dict from weather.load_temperatures()
        source: data source label
        station_id: SMHI station ID

    Returns dict with:
        "hourly_consumption": cleansed list (same format as input)
        "hourly_temperatures": cleansed dict (same format as input)
        "completeness": per-month completeness ratios
    """
    conn = _init_db()
    try:
        # Store raw data
        _store_consumption(conn, hourly_consumption, source)
        _store_temperature(conn, hourly_temperatures, station_id)

        # Cleanse: outlier removal
        _cleanse_consumption(conn)
        _cleanse_temperature(conn)

        # Cleanse: gap filling
        _fill_gaps(conn, "consumption", "kwh")
        _fill_gaps(conn, "temperature", "temp_c")

        # Read back cleansed data
        completeness = _compute_completeness(conn)
        return {
            "hourly_consumption": _read_consumption(conn),
            "hourly_temperatures": _read_temperatures(conn),
            "completeness": completeness,
        }
    finally:
        conn.close()


def get_cleansed_data():
    """Read previously stored and cleansed data."""
    if not os.path.exists(DB_PATH):
        return None
    conn = _init_db()
    try:
        consumption = _read_consumption(conn)
        temperatures = _read_temperatures(conn)
        if not consumption:
            return None
        return {
            "hourly_consumption": consumption,
            "hourly_temperatures": temperatures,
            "completeness": _compute_completeness(conn),
        }
    finally:
        conn.close()
