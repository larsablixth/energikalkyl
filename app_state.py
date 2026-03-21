"""
Persist app session state across Streamlit refreshes.

Saves key data (consumption profiles, prices, house metadata, calibration)
to a local JSON file so the app restores its last state on reload.
"""

import json
import os
import pandas as pd

STATE_DIR = ".app_state"
STATE_FILE = os.path.join(STATE_DIR, "session.json")

# Keys to persist and their types for serialization
PERSIST_KEYS = {
    "seasonal_profile": "dict",
    "vattenfall_hourly": "list",
    "hourly_profile": "dict",
    "tibber_home": "dict",
    "df_prices": "dataframe",
    # Calibration inputs (Streamlit widget keys)
    "cal_year": "scalar",
    "cal_total": "scalar",
    "cal_heating": "scalar",
    "cal_ev": "scalar",
    "cal_active": "scalar",
    "cal_always": "scalar",
    # Air-to-air settings
    "use_aa": "scalar",
    "aa_heat_kw": "scalar",
    "aa_cool_kw": "scalar",
    "aa_min_temp": "scalar",
    "aa_cool_threshold": "scalar",
    "aa_price": "scalar",
    "aa_lifetime": "scalar",
}


def save_state(session_state):
    """Save persistable session state to disk."""
    os.makedirs(STATE_DIR, exist_ok=True)
    data = {}
    for key, typ in PERSIST_KEYS.items():
        if key not in session_state:
            continue
        val = session_state[key]
        if typ == "dataframe" and isinstance(val, pd.DataFrame):
            data[key] = {"_type": "dataframe", "records": val.to_dict(orient="records")}
        elif typ == "dict" and isinstance(val, dict):
            # seasonal_profile has int keys — convert to str for JSON
            data[key] = {"_type": "dict", "value": _keys_to_str(val)}
        elif typ == "scalar":
            data[key] = {"_type": "scalar", "value": val}
        else:
            data[key] = {"_type": typ, "value": val}

    with open(STATE_FILE, "w") as f:
        json.dump(data, f)


def load_state(session_state):
    """Restore persisted state into session, without overwriting existing keys."""
    if not os.path.exists(STATE_FILE):
        return False

    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return False

    restored = False
    for key, wrapper in data.items():
        if key in session_state:
            continue  # don't overwrite data loaded in this session
        typ = wrapper.get("_type", "")
        if typ == "dataframe":
            session_state[key] = pd.DataFrame(wrapper["records"])
            restored = True
        elif typ == "dict":
            session_state[key] = _keys_to_int(wrapper["value"])
            restored = True
        elif typ == "scalar":
            session_state[key] = wrapper["value"]
            restored = True
        elif typ == "list":
            session_state[key] = wrapper["value"]
            restored = True

    return restored


def _keys_to_str(obj):
    """Recursively convert dict int keys to str for JSON serialization."""
    if isinstance(obj, dict):
        return {str(k): _keys_to_str(v) for k, v in obj.items()}
    return obj


def _keys_to_int(obj):
    """Recursively convert dict str keys back to int where possible."""
    if isinstance(obj, dict):
        converted = {}
        for k, v in obj.items():
            try:
                key = int(k)
            except (ValueError, TypeError):
                key = k
            converted[key] = _keys_to_int(v)
        return converted
    return obj
