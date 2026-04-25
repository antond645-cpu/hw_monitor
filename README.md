# HW Monitor

![HW Monitor icon](assets/hw_monitor.png)

Lightweight hardware monitoring for Linux, built with Python + Flask:
- CPU, GPU, and disk temperatures
- CPU and GPU utilization
- Voltage rails via `lm-sensors`
- SMART disk data via `smartctl`
- Historical metrics in SQLite with UI charts

## Hardware Auto-Detection

- **Disks:** default `SMART_DEVICES=auto` scans physical block devices (`/dev/sdX`, `/dev/nvmeXnY`, etc.).
- **NVIDIA GPU:** default `ENABLE_NVIDIA=auto` enables GPU metrics only when `nvidia-smi` is available.
- **AMD GPU:** default `ENABLE_AMD=auto` enables metrics via `/sys/class/drm` + hwmon.
- **Intel GPU:** default `ENABLE_INTEL=auto` enables metrics via `/sys/class/drm` + hwmon.
- **CPU and voltages:** collected through `lm-sensors` (`sensors` command).

If you want explicit disk targets, set for example:
- `SMART_DEVICES=/dev/sda,/dev/nvme0n1`

## Quick Start (Docker Compose)

1. Copy the environment template:

```bash
cp .env.example .env
```

2. Update at least:
- `AUTH_PASS`
- `SECRET_KEY`

3. Optional: adjust `SMART_DEVICES` for your host.

4. Start:

```bash
docker compose up -d --build
```

5. Open:
- `http://<host>:<PORT>`

History is persisted in `./data`.

## Local Run (No Docker)

### Requirements
- Linux
- Python 3.11+
- `lm-sensors` (`sensors`)
- `smartmontools` (`smartctl`)
- optional: `nvidia-smi` for NVIDIA metrics

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

Key settings:
- `APP_TITLE` - UI title
- `AUTH_PASS` - login password
- `SECRET_KEY` - Flask session signing key
- `PORT` - service port
- `SMART_DEVICES` - comma-separated list or `auto`
- `ENABLE_NVIDIA` - `true` / `false` / `auto`
- `ENABLE_AMD` - `true` / `false` / `auto`
- `ENABLE_INTEL` - `true` / `false` / `auto`
- `DB_PATH` - SQLite history path
- `HISTORY_RETENTION_DAYS` - history retention window
- `VOLTAGE_MAPPING` - manual voltage mapping (optional)

## Release and Publishing

Recommended release files are already included:
- `README.md`
- `.env.example`
- `docker-compose.yml`
- `Dockerfile`
- `.gitignore`
- `CHANGELOG.md`
- `CONTRIBUTING.md`

### 1) Push Repository

```bash
git init
git add .
git commit -m "feat: initial public-ready release"
git branch -M main
git remote add origin https://github.com/<you>/hw_monitor.git
git push -u origin main
```

### 2) CI Build Check

Workflow included:
- `.github/workflows/ci.yml` - validates Docker image build on push and PR.

### 3) Create a Tagged Release

```bash
git tag v1.0.0
git push origin v1.0.0
```

Tag push triggers:
- `.github/workflows/release.yml`

It publishes automatically to GHCR:
- `ghcr.io/<github_owner>/hw-monitor:v1.0.0`
- `ghcr.io/<github_owner>/hw-monitor:1.0`
- `ghcr.io/<github_owner>/hw-monitor:latest`

It can also publish to Docker Hub if these secrets are configured:
- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

### 4) Deploy from Published Image

In `docker-compose.yml`, replace `build: .` with:

```yaml
image: ghcr.io/<github_owner>/hw-monitor:latest
```

Then run:

```bash
docker compose up -d
```

## Unraid Apps (Community Applications)

This repository includes Unraid CA files:
- `unraid/hw-monitor.xml`
- `ca_profile.xml`

### Option A: Show in your own Apps tab now (custom source)

1. In Unraid, open `Apps` -> `Settings`.
2. Add a custom source/repository using this XML URL:

`https://raw.githubusercontent.com/antond645-cpu/hw_monitor/main/unraid/hw-monitor.xml`

3. Refresh Apps and search for `HW Monitor`.

### Option B: Publish into the public CA index

Submit this repository in the CA submit portal:
- [https://ca.unraid.net/submit](https://ca.unraid.net/submit)

After review/approval by CA maintainers, the app becomes searchable for all users in Community Applications.

## Notes

- On macOS/Windows, Linux-specific sensors may be unavailable.
- SMART in containers requires `/dev` access and capabilities (`SYS_ADMIN`, `SYS_RAWIO`).
- AMD/Intel GPU metrics are sysfs-based and available fields depend on kernel + driver support.
