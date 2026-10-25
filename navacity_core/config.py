"""Central configuration for the NavaCity simulation and ML pipeline.

All content in this project is SIMULATED.  NavaCity is a fictional city.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
GENERATED_DIR = DATA_DIR / "generated"
ARTIFACTS_DIR = REPO_ROOT / "ml" / "artifacts"
FRONTEND_DIR = REPO_ROOT / "frontend"

DB_PATH = Path(os.environ.get("NAVACITY_DB_PATH", str(DATA_DIR / "navacity.db")))
DATASET_CSV = GENERATED_DIR / "navacity_transport.csv"
NETWORK_JSON = GENERATED_DIR / "navacity_network.json"
MODEL_BUNDLE = ARTIFACTS_DIR / "model_bundle.joblib"
METRICS_JSON = ARTIFACTS_DIR / "metrics.json"

# --------------------------------------------------------------------------
# Simulation window / reproducibility
# --------------------------------------------------------------------------
RANDOM_SEED = 20250615
SIM_START_DATE = date(2025, 1, 1)
SIM_END_DATE = date(2025, 6, 30)

# Number of hourly observations sampled per (segment, calendar day).
# Two of them are always the commuter peaks (08:00 and 18:00), the remainder
# are drawn uniformly so that the hour-of-day distribution stays varied.
SAMPLES_PER_SEGMENT_DAY = 4
PEAK_HOURS = (8, 18)

# --------------------------------------------------------------------------
# Crowd level model
# --------------------------------------------------------------------------
# Occupancy is expressed as a ratio of the hourly capacity offered by the
# planned service (passengers carried / (vehicle capacity x service frequency)).
#
#   Low       0.00 - 0.40   plenty of room, passengers rarely wait for a second vehicle
#   Moderate  0.40 - 0.65   comfortable, a few passengers may wait for the next service
#   High      0.65 - 0.85   crowded, boarding is slow and queues form
#   Critical  0.85 +        overcrowded, passengers are left behind / denied boarding
#
# The 0.85 cut-off is the point at which a standing passenger has roughly
# 0.85 m2 of space in a crush-loaded vehicle, which is the level at which
# operators normally describe a service as "overcrowded".
CROWD_LOW_MAX = 0.40
CROWD_MODERATE_MAX = 0.65
CROWD_HIGH_MAX = 0.85
OVERCROWDING_ALERT_THRESHOLD = 0.80

CROWD_LEVELS = ("Low", "Moderate", "High", "Critical")

# --------------------------------------------------------------------------
# Service frequency profiles (multiplier on the route's base frequency)
# --------------------------------------------------------------------------
FREQ_PROFILE_WEEKDAY = [
    0.25, 0.15, 0.12, 0.15, 0.30, 0.55, 0.90, 1.30,
    1.80, 1.90, 1.25, 1.00, 1.05, 1.05, 1.00, 1.10,
    1.40, 1.80, 1.95, 1.60, 1.20, 0.80, 0.50, 0.30,
]
FREQ_PROFILE_WEEKEND = [
    0.30, 0.20, 0.15, 0.15, 0.25, 0.40, 0.65, 0.85,
    1.00, 1.05, 1.10, 1.15, 1.20, 1.20, 1.15, 1.15,
    1.20, 1.25, 1.25, 1.15, 1.00, 0.75, 0.55, 0.40,
]

# --------------------------------------------------------------------------
# Occupancy profiles (multiplier on the mode's baseline occupancy)
# --------------------------------------------------------------------------
OCC_PROFILE_WEEKDAY = [
    0.10, 0.08, 0.07, 0.08, 0.14, 0.30, 0.55, 0.85,
    1.10, 1.25, 1.00, 0.82, 0.85, 0.88, 0.85, 0.90,
    1.05, 1.22, 1.30, 1.15, 0.90, 0.62, 0.42, 0.25,
]
OCC_PROFILE_WEEKEND = [
    0.15, 0.12, 0.10, 0.10, 0.15, 0.25, 0.45, 0.65,
    0.80, 0.90, 0.95, 1.00, 1.02, 1.00, 0.95, 0.95,
    1.00, 1.05, 1.08, 1.02, 0.90, 0.72, 0.50, 0.30,
]

# Baseline occupancy of the busiest hour of an average day.
BASE_OCCUPANCY = {"metro": 0.52, "bus": 0.55}

# Weather effects on occupancy (rain pushes people out of private vehicles
# and onto public transport; fog reduces services and suppresses trips).
WEATHER_OCCUPANCY_FACTOR = {
    "clear": 1.00,
    "cloudy": 0.99,
    "light_rain": 1.06,
    "heavy_rain": 1.12,
    "fog": 0.93,
}
WEATHER_TRAFFIC_FACTOR = {
    "clear": 1.00,
    "cloudy": 1.00,
    "light_rain": 1.05,
    "heavy_rain": 1.15,
    "fog": 0.95,
}

# Traffic congestion lifts bus occupancy (people switch from cars to buses) and
# lengthens the bus journey time.
TRAFFIC_LEVELS = ("light", "moderate", "heavy", "severe")
TRAFFIC_OCCUPANCY_FACTOR = {
    "light": 1.00,
    "moderate": 1.03,
    "heavy": 1.07,
    "severe": 1.10,
}
TRAFFIC_TRAVEL_TIME_FACTOR = {
    "light": 1.00,
    "moderate": 1.12,
    "heavy": 1.28,
    "severe": 1.45,
}

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def crowd_level_for(occupancy: float) -> str:
    """Map an occupancy ratio to a human readable crowd level."""
    if occupancy is None:
        return "Unknown"
    occ = float(occupancy)
    if occ >= CROWD_HIGH_MAX:
        return "Critical"
    if occ >= CROWD_MODERATE_MAX:
        return "High"
    if occ >= CROWD_LOW_MAX:
        return "Moderate"
    return "Low"


def crowd_level_bounds() -> list[dict]:
    """Machine readable description of the crowd thresholds."""
    return [
        {"level": "Low", "min": 0.0, "max": CROWD_LOW_MAX},
        {"level": "Moderate", "min": CROWD_LOW_MAX, "max": CROWD_MODERATE_MAX},
        {"level": "High", "min": CROWD_MODERATE_MAX, "max": CROWD_HIGH_MAX},
        {"level": "Critical", "min": CROWD_HIGH_MAX, "max": None},
    ]


def day_type_for(is_weekend: bool, is_holiday: bool) -> str:
    if is_holiday:
        return "holiday"
    return "weekend" if is_weekend else "weekday"


# The months that the simulator actually produced rows for.  Derived from the
# simulated window so that the two can never drift apart.
OBSERVED_MONTHS: frozenset[int] = frozenset(
    range(SIM_START_DATE.month, SIM_END_DATE.month + 1)
)


def is_within_simulated_window(day: date) -> bool:
    """True when the day lies inside the simulated (training) window."""
    return SIM_START_DATE <= day <= SIM_END_DATE


def is_within_observed_months(day: date) -> bool:
    """True when the *month* of the day was observed during the simulation.

    The month features (``month_sin`` / ``month_cos``) are cyclical, so a day
    in an unobserved month is an extrapolation even when the day itself is
    inside the window.  The simulated window covers January to June, so months
    7-12 were never observed.
    """
    return day.month in OBSERVED_MONTHS


def service_frequency_for(mode: str, hour: int, day_type: str, base_frequency: int) -> int:
    """Planned vehicles per hour for a route at a given hour."""
    profile = FREQ_PROFILE_WEEKDAY if day_type == "weekday" else FREQ_PROFILE_WEEKEND
    return max(1, int(round(base_frequency * profile[hour])))


def occupancy_profile_for(day_type: str) -> list[float]:
    return OCC_PROFILE_WEEKDAY if day_type == "weekday" else OCC_PROFILE_WEEKEND
