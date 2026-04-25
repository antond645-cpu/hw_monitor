"""Metric collection and history storage.

Architecture:
- A background `Collector` thread samples all metrics every
  `COLLECT_INTERVAL_SEC` and writes snapshots to:
    1) in-memory deque (ring buffer) for live/10m windows without I/O;
    2) SQLite for long windows (1h/24h/1w) with SQL downsampling.
- HTTP routes only read from these structures and never run external commands
  in request context, which keeps the server responsive under concurrency.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Iterable

try:  # psutil can be unavailable in dev environments; degrade gracefully.
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None  # type: ignore

import config

log = logging.getLogger(__name__)


# ---------- Sensor parsers --------------------------------------------------

# label -> canonical key mapping. Prefer label-based parsing, but chips like
# NCT6798D often expose real +12V/+5V/Vcore rails under generic names in0..in7.
# Those are handled via value-based fallback below.
_VOLTAGE_LABELS: dict[str, str] = {
    "Vcore": "Vcore",
    "VCORE": "Vcore",
    "CPU Vcore": "Vcore",
    "SVI2_Core": "Vcore",
    "+12V": "+12V",
    "12V": "+12V",
    "+5V": "+5V",
    "5V": "+5V",
    "+3.3V": "+3.3V",
    "3.3V": "+3.3V",
    "3VCC": "+3.3V",
    "AVCC": "AVCC",
    "3VSB": "3VSB",
    "VBAT": "VBAT",
    "Vbat": "VBAT",
}

# CPU/package temperature labels. NVMe and disk temperatures are read via SMART
# for better consistency and to avoid duplicate per-disk keys.
_TEMP_LABELS: dict[str, str] = {
    "CPU Temp": "CPU Temp",
    "CPUTIN": "CPU Temp",
    "Tctl": "CPU Temp",
    "Tdie": "CPU Temp",
    "Tccd1": "CPU Temp",
    "Package id 0": "CPU Temp",
}

_TEMP_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*°?C")
_VOLT_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*(mV|V)\b")
_GENERIC_IN_RE = re.compile(r"^(?:in|IN|VIN)\d+$")


def _classify_voltage(v: float) -> str | None:
    """Heuristically infer voltage rail by value.

    Applies only to generic labels such as `in0` when the rail cannot be
    identified from the label name itself.
    """
    if 11.0 <= v <= 13.5:
        return "+12V"
    if 4.5 <= v <= 5.5:
        return "+5V"
    if 3.0 <= v <= 3.6:
        return "+3.3V"
    if 0.6 <= v <= 1.6:
        return "Vcore"
    return None


def _run(cmd: list[str]) -> str:
    """Run a command and return stdout, or an empty string on failure."""
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=config.CMD_TIMEOUT_SEC,
            check=False,
        )
        if r.returncode != 0:
            log.debug("cmd %s rc=%s stderr=%s", cmd[0], r.returncode, r.stderr.strip())
        return r.stdout or ""
    except FileNotFoundError:
        log.debug("cmd not found: %s", cmd[0])
    except subprocess.TimeoutExpired:
        log.warning("cmd timeout: %s", cmd)
    except Exception:  # pragma: no cover
        log.exception("cmd failed: %s", cmd)
    return ""


def parse_sensors(output: str) -> dict[str, float]:
    """Parse `sensors` output with two strategies.

    1) Exact match by label name (+12V/+5V/Vcore/CPUTIN/Tctl ...).
    2) For generic names in*/IN*/VIN* use value-based rail classification,
       filling only rails that are still unresolved by label.
    """
    data: dict[str, float] = {}
    fallback: list[tuple[str, float]] = []
    generic_values: dict[str, float] = {}
    saw_nct6798 = False

    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        if ":" not in line:
            # Section headers like "nct6798-isa-0290" / "coretemp-isa-0000".
            if "nct6798" in line.lower():
                saw_nct6798 = True
            continue
        label, _, rest = line.partition(":")
        label = label.strip()
        label_lc = label.lower()
        rest = rest.strip()
        if not rest:
            continue

        canonical_t = _TEMP_LABELS.get(label)
        if canonical_t:
            m = _TEMP_RE.search(rest)
            if m:
                try:
                    data[canonical_t] = round(float(m.group(1)), 1)
                except ValueError:
                    pass
            continue

        m_v = _VOLT_RE.search(rest)
        if not m_v:
            continue
        try:
            value = float(m_v.group(1))
        except ValueError:
            continue
        if m_v.group(2) == "mV":
            value /= 1000.0

        # 1) User mapping from config has highest priority, e.g. map
        #    "in4" to "+12V" with multiplier 12.
        user_map = config.VOLTAGE_MAPPING.get(label) or config.VOLTAGE_MAPPING.get(label_lc)
        if user_map:
            target_key, mult = user_map
            data[target_key] = round(value * mult, 3)
            continue

        # 2) Known labels are taken as-is.
        canonical_v = _VOLTAGE_LABELS.get(label)
        if canonical_v:
            data[canonical_v] = round(value, 3)
            continue

        # 3) Queue generic in*/IN*/VIN* labels for a second-pass heuristic.
        if _GENERIC_IN_RE.match(label):
            fallback.append((label, value))
            generic_values[label_lc] = value

    # Fill unresolved rails with the second-pass heuristic.
    for _label, v in fallback:
        key = _classify_voltage(v)
        if key and key not in data:
            data[key] = round(v, 3)

    # NCT6798 fallback: on some boards +12V/+5V are exposed as raw inN values
    # due to dividers if sensors.conf is not tuned.
    #
    # On ASUS boards (e.g. PRIME N100I-D D4), 1:10/1:5 dividers are often
    # wired to in10/in11, so check those first. Alternative mappings
    # (in4x12 / in1x5 / in5x5) are kept for MSI/Gigabyte layouts.
    if saw_nct6798:
        if "+12V" not in data:
            in10 = generic_values.get("in10")
            in4 = generic_values.get("in4")
            in0 = generic_values.get("in0")
            if in10 is not None and 1.05 <= in10 <= 1.35:
                data["+12V"] = round(in10 * 10.0, 3)
            elif in4 is not None and 0.8 <= in4 <= 1.3:
                data["+12V"] = round(in4 * 12.0, 3)
            elif in0 is not None and 1.6 <= in0 <= 2.4:
                data["+12V"] = round(in0 * 6.0, 3)
        if "+5V" not in data:
            in11 = generic_values.get("in11")
            in1 = generic_values.get("in1")
            in5 = generic_values.get("in5")
            if in11 is not None and 0.9 <= in11 <= 1.1:
                data["+5V"] = round(in11 * 5.0, 3)
            elif in1 is not None and 0.8 <= in1 <= 1.2:
                data["+5V"] = round(in1 * 5.0, 3)
            elif in5 is not None and 0.8 <= in5 <= 1.2:
                data["+5V"] = round(in5 * 5.0, 3)
    return data


def read_sensors() -> dict[str, float]:
    out = _run(["sensors"])
    return parse_sensors(out) if out else {}


# ---------- SMART -----------------------------------------------------------

# smartctl output formats:
#   SATA  :  "194 Temperature_Celsius 0x0022 ... -   35 (Min/Max 27/55)"
#            - RAW_VALUE comes after '-' in the flags column.
#   NVMe  :  "Temperature: 35 Celsius"
#   SAS   :  "Current Drive Temperature: 35 C"
#   also  :  "Airflow_Temperature_Cel ..." - ignored as less useful.
_SMART_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^\s*\d+\s+Temperature_Celsius\b.*?-\s+(\d+)", re.MULTILINE),
    re.compile(r"^Temperature:\s*(\d+)\s*Celsius", re.MULTILINE),
    re.compile(r"^Current Drive Temperature:\s*(\d+)", re.MULTILINE),
)


def read_smart(device: str) -> float | None:
    """Read disk temperature via smartctl.

    `-n standby` prevents waking sleeping HDDs. In that case smartctl exits
    with a standby indication and no temperature is returned; frontend shows
    "Sleep" status.
    """
    out = _run(["smartctl", "-A", "-n", "standby", device])
    if not out:
        return None
    if "STANDBY" in out.upper() or "SLEEP" in out.upper():
        return None
    for pat in _SMART_PATTERNS:
        m = pat.search(out)
        if m:
            try:
                return round(float(m.group(1)), 1)
            except ValueError:
                return None
    return None


def device_key(device: str) -> str:
    """'/dev/nvme0n1' -> 'nvme0n1'."""
    return device.rsplit("/", 1)[-1]


def discover_smart_devices() -> list[str]:
    """Best-effort autodiscovery for physical block devices.

    Returns base block devices from /sys/block:
    /dev/sdX, /dev/nvmeXnY, /dev/vdX, /dev/mmcblkX, etc.
    Virtual/service devices (loop, zram, dm-*, md*, sr*) are excluded.
    """
    sys_block = Path("/sys/block")
    if not sys_block.exists():
        return []

    skip_prefixes = ("loop", "ram", "zram", "dm-", "md", "sr", "fd")
    devices: list[str] = []
    try:
        for entry in sorted(sys_block.iterdir(), key=lambda p: p.name):
            name = entry.name
            if any(name.startswith(prefix) for prefix in skip_prefixes):
                continue
            dev = Path("/dev") / name
            if dev.exists():
                devices.append(str(dev))
    except Exception:
        log.debug("smart device autodiscovery failed", exc_info=True)
        return []
    return devices


# ---------- NVIDIA GPU ------------------------------------------------------

# nvidia-smi fields in query order. Some values can be "[N/A]"
# (e.g. fan.speed on devices without controllable fan, or encoder/decoder
# utilization on older drivers). Such values are skipped silently.
_NVIDIA_FIELDS: tuple[tuple[str, str, int], ...] = (
    # (nvidia-smi field, metric key, decimal precision)
    ("utilization.gpu",            "GPU Load",       1),
    ("utilization.memory",         "GPU Mem BW",     1),
    ("utilization.encoder",        "GPU Encoder",    1),
    ("utilization.decoder",        "GPU Decoder",    1),
    ("temperature.gpu",            "GPU Temp",       1),
    ("fan.speed",                  "GPU Fan",        1),
    ("power.draw",                 "GPU Power",      1),
    ("clocks.current.graphics",    "GPU Clock",      0),
    ("clocks.current.memory",      "GPU Mem Clock",  0),
    ("memory.used",                "_mem_used",      0),
    ("memory.total",               "_mem_total",     0),
)
_PP_DPM_CLK_RE = re.compile(r":\s*(\d+(?:\.\d+)?)\s*MHz\b.*\*")


def _parse_nvidia_value(raw: str) -> float | None:
    s = raw.strip()
    if not s:
        return None
    # nvidia-smi may return "[N/A]", "[Not Supported]", etc.
    if s.startswith("[") or s.lower() in {"n/a", "not supported"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def read_nvidia() -> dict[str, float]:
    if not config.ENABLE_NVIDIA:
        return {}
    query = ",".join(f for f, _, _ in _NVIDIA_FIELDS)
    out = _run([
        "nvidia-smi",
        f"--query-gpu={query}",
        "--format=csv,noheader,nounits",
    ])
    if not out.strip():
        return {}
    parts = out.strip().splitlines()[0].split(",")
    if len(parts) < len(_NVIDIA_FIELDS):
        return {}

    raw: dict[str, float] = {}
    for (_, key, digits), value in zip(_NVIDIA_FIELDS, parts):
        v = _parse_nvidia_value(value)
        if v is None:
            continue
        raw[key] = round(v, digits) if digits else round(v)

    data: dict[str, float] = {k: v for k, v in raw.items() if not k.startswith("_")}

    # VRAM usage (% of total), shown in Unraid GPU Statistics as "Memory: NN%".
    mem_used = raw.get("_mem_used")
    mem_total = raw.get("_mem_total")
    if mem_used is not None and mem_total and mem_total > 0:
        data["GPU Mem Used"] = round(100.0 * mem_used / mem_total, 1)

    return data


# ---------- AMD / Intel GPU (sysfs) ----------------------------------------

def _discover_drm_cards() -> list[Path]:
    base = Path("/sys/class/drm")
    if not base.exists():
        return []
    return sorted((p for p in base.glob("card[0-9]*") if p.is_dir()), key=lambda p: p.name)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def _read_float(path: Path, scale: float = 1.0) -> float | None:
    raw = _read_text(path)
    if raw is None or raw == "":
        return None
    try:
        return float(raw) * scale
    except ValueError:
        return None


def _read_hwmon_float(device: Path, leaf: str, scale: float = 1.0) -> float | None:
    hwmon_root = device / "hwmon"
    if not hwmon_root.exists():
        return None
    for node in sorted(hwmon_root.glob("hwmon*")):
        value = _read_float(node / leaf, scale=scale)
        if value is not None:
            return value
    return None


def _card_vendor(card: Path) -> str | None:
    return _read_text(card / "device" / "vendor")


def _pick_card(vendor_hex: str) -> Path | None:
    target = vendor_hex.lower()
    for card in _discover_drm_cards():
        vendor = _card_vendor(card)
        if vendor and vendor.lower() == target:
            return card
    return None


def _parse_pp_dpm_clock(path: Path) -> float | None:
    raw = _read_text(path)
    if not raw:
        return None
    for line in raw.splitlines():
        m = _PP_DPM_CLK_RE.search(line)
        if m:
            try:
                return round(float(m.group(1)))
            except ValueError:
                return None
    return None


def read_amd_gpu() -> dict[str, float]:
    if not config.ENABLE_AMD:
        return {}
    card = _pick_card("0x1002")
    if card is None:
        return {}
    device = card / "device"
    data: dict[str, float] = {}

    load = _read_float(device / "gpu_busy_percent")
    if load is not None:
        data["GPU Load"] = round(load, 1)

    temp = _read_hwmon_float(device, "temp1_input", scale=0.001)
    if temp is not None:
        data["GPU Temp"] = round(temp, 1)

    power = _read_hwmon_float(device, "power1_average", scale=1e-6)
    if power is not None:
        data["GPU Power"] = round(power, 1)

    pwm = _read_hwmon_float(device, "pwm1")
    if pwm is not None:
        pwm_max = _read_hwmon_float(device, "pwm1_max") or 255.0
        if pwm_max > 0:
            data["GPU Fan"] = round(max(0.0, min(100.0, 100.0 * pwm / pwm_max)), 1)

    gfx_clk = _parse_pp_dpm_clock(device / "pp_dpm_sclk")
    if gfx_clk is not None:
        data["GPU Clock"] = gfx_clk

    mem_clk = _parse_pp_dpm_clock(device / "pp_dpm_mclk")
    if mem_clk is not None:
        data["GPU Mem Clock"] = mem_clk

    vram_used = _read_float(device / "mem_info_vram_used")
    vram_total = _read_float(device / "mem_info_vram_total")
    if vram_used is not None and vram_total and vram_total > 0:
        data["GPU Mem Used"] = round(100.0 * vram_used / vram_total, 1)

    return data


def read_intel_gpu() -> dict[str, float]:
    if not config.ENABLE_INTEL:
        return {}
    card = _pick_card("0x8086")
    if card is None:
        return {}
    device = card / "device"
    data: dict[str, float] = {}

    for leaf in ("gt_busy_percent", "gpu_busy_percent", "busy_percent"):
        load = _read_float(device / leaf)
        if load is not None:
            data["GPU Load"] = round(load, 1)
            break

    for leaf in ("temp1_input", "temp2_input"):
        temp = _read_hwmon_float(device, leaf, scale=0.001)
        if temp is not None:
            data["GPU Temp"] = round(temp, 1)
            break

    power = _read_hwmon_float(device, "power1_average", scale=1e-6)
    if power is not None:
        data["GPU Power"] = round(power, 1)

    for leaf in ("gt_cur_freq_mhz", "gt_act_freq_mhz", "rps_cur_freq_mhz"):
        clk = _read_float(device / leaf)
        if clk is not None:
            data["GPU Clock"] = round(clk)
            break

    mem_bw = _read_float(device / "mem_busy_percent")
    if mem_bw is not None:
        data["GPU Mem BW"] = round(mem_bw, 1)

    return data


# ---------- Disk I/O and CPU via psutil ------------------------------------

@dataclass
class _IOState:
    ts: float = 0.0
    per_disk: dict[str, tuple[int, int]] = field(default_factory=dict)


def _collect_psutil(state: _IOState, devices: Iterable[str]) -> dict[str, float]:
    if psutil is None:
        return {}
    data: dict[str, float] = {}
    try:
        data["CPU Load"] = round(psutil.cpu_percent(interval=None), 1)
    except Exception:
        log.debug("cpu_percent failed", exc_info=True)

    try:
        counters = psutil.disk_io_counters(perdisk=True) or {}
    except Exception:
        log.debug("disk_io_counters failed", exc_info=True)
        counters = {}

    now = time.monotonic()
    dt = now - state.ts if state.ts else 0.0
    state.ts = now

    for dev in devices:
        key = device_key(dev)
        c = counters.get(key)
        if c is None:
            continue
        prev = state.per_disk.get(key)
        state.per_disk[key] = (c.read_bytes, c.write_bytes)
        if prev and dt > 0:
            rd = max(0, (c.read_bytes - prev[0])) / dt / (1024 * 1024)
            wr = max(0, (c.write_bytes - prev[1])) / dt / (1024 * 1024)
            data[f"{key}_read"] = round(rd, 3)
            data[f"{key}_write"] = round(wr, 3)
        else:
            data[f"{key}_read"] = 0.0
            data[f"{key}_write"] = 0.0
    return data


# ---------- Storage ---------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS metrics (
    ts INTEGER NOT NULL,
    name TEXT NOT NULL,
    value REAL,
    PRIMARY KEY (ts, name)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(ts);
"""


class HistoryStore:
    """Thin SQLite wrapper for long-range history."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_DDL)

    def write(self, ts: int, metrics: dict[str, float]) -> None:
        rows = [(ts, k, v) for k, v in metrics.items() if v is not None]
        if not rows:
            return
        with self._lock:
            self._conn.executemany(
                "INSERT OR REPLACE INTO metrics(ts, name, value) VALUES (?, ?, ?)",
                rows,
            )

    def query(self, since: int, bucket_sec: int) -> dict[str, list]:
        """Return downsampled data: average value per time bucket.

        Returns {"times": [...], "metrics": {name: [values...]}}
        with aligned arrays (None for empty buckets).
        """
        bucket = max(1, int(bucket_sec))
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT (ts / ?) * ? AS bucket, name, AVG(value)
                FROM metrics
                WHERE ts >= ?
                GROUP BY bucket, name
                ORDER BY bucket ASC
                """,
                (bucket, bucket, since),
            )
            raw = cur.fetchall()

        by_time: dict[int, dict[str, float]] = {}
        names: set[str] = set()
        for ts_bucket, name, avg in raw:
            by_time.setdefault(int(ts_bucket), {})[name] = avg
            names.add(name)

        times = sorted(by_time.keys())
        metrics: dict[str, list] = {n: [] for n in names}
        for t in times:
            row = by_time[t]
            for n in names:
                metrics[n].append(row.get(n))
        return {"times": times, "metrics": metrics}

    def prune(self, older_than_ts: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM metrics WHERE ts < ?", (older_than_ts,))


# ---------- Main collector --------------------------------------------------

class Collector:
    """Background thread that periodically collects metrics."""

    def __init__(self) -> None:
        self.store = HistoryStore(config.DB_PATH)
        self._buffer: Deque[tuple[int, dict[str, float]]] = deque(
            maxlen=config.RING_BUFFER_SIZE
        )
        self._buf_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="collector", daemon=True)

        self._io_state = _IOState()
        self._smart_cache: dict[str, tuple[float, float | None]] = {}
        self._last_prune = 0.0
        self._smart_devices = list(config.SMART_DEVICES) or discover_smart_devices()
        if self._smart_devices:
            log.info("smart devices: %s", ", ".join(self._smart_devices))
        else:
            log.info("smart devices: none (SMART metrics disabled)")

    # --- Lifecycle ---
    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    # --- Public API ---
    def snapshot_live(self) -> dict:
        """Return latest points from the in-memory buffer."""
        with self._buf_lock:
            items = list(self._buffer)
        return self._shape(items)

    def snapshot_history(self, period: str) -> dict:
        """Return downsampled history for the selected period."""
        now = int(time.time())
        window = {
            "10m": 10 * 60,
            "1h": 60 * 60,
            "24h": 24 * 60 * 60,
            "1w": 7 * 24 * 60 * 60,
        }.get(period)
        if window is None:
            return {"times": [], "metrics": {}}

        # Target roughly 300 points per window.
        target_points = 300
        bucket = max(1, window // target_points)
        return self.store.query(now - window, bucket)

    # --- Internals ---
    @staticmethod
    def _shape(items: list[tuple[int, dict[str, float]]]) -> dict:
        times: list[int] = []
        metrics: dict[str, list] = {}
        names: set[str] = set()
        for _, snap in items:
            names.update(snap.keys())
        for ts, snap in items:
            times.append(ts)
            for n in names:
                metrics.setdefault(n, []).append(snap.get(n))
        return {"times": times, "metrics": metrics}

    def _collect_once(self, now: float) -> dict[str, float]:
        snapshot: dict[str, float] = {}
        snapshot.update(read_sensors())
        gpu = read_nvidia()
        if not gpu:
            gpu = read_amd_gpu()
        if not gpu:
            gpu = read_intel_gpu()
        snapshot.update(gpu)
        snapshot.update(_collect_psutil(self._io_state, self._smart_devices))

        # SMART with caching to avoid polling disks every second.
        for dev in self._smart_devices:
            key = device_key(dev)
            cached = self._smart_cache.get(key)
            if cached and (now - cached[0]) < config.SMART_TTL_SEC:
                temp = cached[1]
            else:
                temp = read_smart(dev)
                self._smart_cache[key] = (now, temp)
            if temp is not None:
                # Key names use snake_case (matching I/O metric prefixes).
                snapshot[f"{key}_temp"] = temp
        return snapshot

    def _run(self) -> None:
        log.info("collector started; interval=%.2fs", config.COLLECT_INTERVAL_SEC)
        # Warm up psutil: first cpu_percent call returns 0.0 baseline.
        if psutil is not None:
            try:
                psutil.cpu_percent(interval=None)
            except Exception:
                pass

        next_tick = time.monotonic()
        while not self._stop.is_set():
            try:
                now_wall = time.time()
                snap = self._collect_once(now_wall)
                ts = int(now_wall)
                with self._buf_lock:
                    self._buffer.append((ts, snap))
                self.store.write(ts, snap)

                # Periodic pruning of old records.
                if now_wall - self._last_prune > 3600:
                    cutoff = int(now_wall - config.HISTORY_RETENTION_DAYS * 86400)
                    self.store.prune(cutoff)
                    self._last_prune = now_wall
            except Exception:
                log.exception("collector iteration failed")

            next_tick += config.COLLECT_INTERVAL_SEC
            sleep_for = next_tick - time.monotonic()
            if sleep_for < 0:
                # If behind schedule, catch up without busy looping.
                next_tick = time.monotonic()
                sleep_for = config.COLLECT_INTERVAL_SEC
            self._stop.wait(sleep_for)
        log.info("collector stopped")
