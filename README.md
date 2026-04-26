# HW Monitor

![HW Monitor icon](assets/hw_monitor.png)

A lightweight hardware monitoring dashboard for Linux and Unraid.

## Features

- Live and historical charts
- CPU, GPU, and disk temperatures
- CPU and GPU utilization
- Voltage rails from `lm-sensors`
- SMART disk telemetry from `smartctl`
- SQLite-backed metric history

## Hardware Auto-Detection

- **Disks:** `SMART_DEVICES=auto` scans physical block devices (`/dev/sdX`, `/dev/nvmeXnY`, ...).
- **NVIDIA:** `ENABLE_NVIDIA=auto` uses `nvidia-smi` when available.
- **AMD:** `ENABLE_AMD=auto` uses `/sys/class/drm` and hwmon.
- **Intel:** `ENABLE_INTEL=auto` uses `/sys/class/drm` and hwmon.
- **CPU and voltages:** read via `lm-sensors` (`sensors`).

To pin disk targets manually:
- `SMART_DEVICES=/dev/sda,/dev/nvme0n1`

## Quick Start (Docker Compose)

1. Copy the environment template:

```bash
cp .env.example .env
```

2. Update at least:
- `AUTH_PASS`
- `SECRET_KEY`

3. Optionally adjust `SMART_DEVICES`.

4. Start:

```bash
docker compose up -d --build
```

5. Open:
- `http://<host>:<PORT>`

Metric history is stored in `./data`.

## Local Run (No Docker)

### Requirements
- Linux
- Python 3.11+
- `lm-sensors` (`sensors`)
- `smartmontools` (`smartctl`)
- optional `nvidia-smi` for NVIDIA metrics

### Install and Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python server.py
```

Then open `http://127.0.0.1:8181`.

## Environment Variables

Key settings are provided in `.env.example`. Most deployments only need:
- `AUTH_PASS`
- `SECRET_KEY`
- `SMART_DEVICES` (`auto` or explicit list)
- `ENABLE_NVIDIA`, `ENABLE_AMD`, `ENABLE_INTEL` (`auto|true|false`)

## Unraid Apps (Community Applications)

This repository includes:
- `unraid/hw-monitor.xml`
- `ca_profile.xml`

### Option A: Show in your own Apps tab now (custom source)

1. In Unraid, open `Apps` -> `Settings`.
2. Add a custom source/repository using this XML URL:

`https://raw.githubusercontent.com/antond645-cpu/hw_monitor/main/unraid/hw-monitor.xml`

3. Refresh Apps and search for `HW Monitor`.

### Option B: Publish into the public CA index

Submit this repository via:
- [https://ca.unraid.net/submit](https://ca.unraid.net/submit)

After CA review and index refresh, the app becomes searchable for all users.

## Notes

- On macOS/Windows, Linux-specific sensors may be unavailable.
- In containers, SMART needs `/dev` access and capabilities (`SYS_ADMIN`, `SYS_RAWIO`).
- AMD/Intel GPU fields depend on kernel and driver support.
