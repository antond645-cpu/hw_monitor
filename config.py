"""HW Monitor configuration.

All settings are loaded from environment variables with sensible defaults.
You can override values via docker-compose or a local .env file.
"""
from __future__ import annotations

import os
import secrets
import shutil
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_bool_auto(name: str, auto_default: bool) -> bool:
    """Parse bool-like env with optional 'auto' mode."""
    raw = os.getenv(name)
    if raw is None:
        return auto_default
    value = raw.strip().lower()
    if value == "auto":
        return auto_default
    return value in {"1", "true", "yes", "on"}


def _has_drm_vendor(vendor_hex: str) -> bool:
    """Return True when /sys/class/drm contains a GPU with vendor id."""
    base = Path("/sys/class/drm")
    if not base.exists():
        return False
    needle = vendor_hex.strip().lower()
    for path in base.glob("card*/device/vendor"):
        try:
            if path.read_text(encoding="utf-8").strip().lower() == needle:
                return True
        except Exception:
            continue
    return False


# --- Authentication ---
PASSWORD: str = os.getenv("AUTH_PASS", "admin")
# Session cookie signing key; random when not explicitly set.
SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_hex(32))
# Session cookie lifetime after successful login (seconds).
SESSION_TTL_SEC: int = int(os.getenv("SESSION_TTL_SEC", str(7 * 24 * 3600)))

# --- HTTP ---
APP_TITLE: str = os.getenv("APP_TITLE", "HW Monitor")
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8181"))

# --- Metrics collection ---
# Poll interval for the background collector (seconds).
COLLECT_INTERVAL_SEC: float = float(os.getenv("COLLECT_INTERVAL_SEC", "1.0"))
# smartctl cache TTL: disk temperatures change slowly, and frequent HDD polls
# can wake drives from standby.
SMART_TTL_SEC: int = int(os.getenv("SMART_TTL_SEC", "60"))
# Timeout for external commands (sensors, smartctl, nvidia-smi).
CMD_TIMEOUT_SEC: float = float(os.getenv("CMD_TIMEOUT_SEC", "4.0"))
# In-memory ring buffer size (points). 300 @ 1s = 5 minutes and should match
# the frontend live window (MAX_LIVE_POINTS).
RING_BUFFER_SIZE: int = int(os.getenv("RING_BUFFER_SIZE", "300"))
# SMART device list.
SMART_DEVICES: list[str] = [
    d.strip()
    for d in os.getenv("SMART_DEVICES", "auto").split(",")
    if d.strip() and d.strip().lower() != "auto"
]
# Whether to collect NVIDIA GPU metrics via nvidia-smi.
ENABLE_NVIDIA: bool = _env_bool_auto("ENABLE_NVIDIA", shutil.which("nvidia-smi") is not None)
# Whether to collect AMD GPU metrics via sysfs.
ENABLE_AMD: bool = _env_bool_auto("ENABLE_AMD", _has_drm_vendor("0x1002"))
# Whether to collect Intel GPU metrics via sysfs.
ENABLE_INTEL: bool = _env_bool_auto("ENABLE_INTEL", _has_drm_vendor("0x8086"))

# --- History storage ---
DB_PATH: Path = Path(os.getenv("DB_PATH", "/var/lib/hw_monitor/history.db"))
# Retention period for raw points (older data is pruned periodically).
HISTORY_RETENTION_DAYS: int = int(os.getenv("HISTORY_RETENTION_DAYS", "14"))

# --- Manual mapping of generic voltage labels to rails ---
# Many Super I/O chips (NCT6798, IT87xx, ...) expose +12V/+5V as raw inN
# values due to onboard voltage dividers. Without proper sensors3.conf tuning,
# you may see `in4: 1.05 V` instead of `+12V: 12.60 V`.
# This variable accepts comma-separated "source:target:multiplier" entries.
#
# Example for typical Asus/MSI NCT6798D boards:
#   VOLTAGE_MAPPING="in4:+12V:12,in1:+5V:5"
#
# Tune multipliers empirically: compare real voltage from BIOS/multimeter
# with the raw sensors reading and calculate the ratio.
def _parse_mapping(raw: str) -> dict[str, tuple[str, float]]:
    result: dict[str, tuple[str, float]] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        parts = item.split(":")
        if len(parts) != 3:
            continue
        src, dst, mult = parts
        try:
            result[src.strip().lower()] = (dst.strip(), float(mult))
        except ValueError:
            continue
    return result


VOLTAGE_MAPPING: dict[str, tuple[str, float]] = _parse_mapping(
    os.getenv("VOLTAGE_MAPPING", "")
)

# --- Logging ---
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
