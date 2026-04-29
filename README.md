# HW Monitor

![HW Monitor icon](assets/hw_monitor.png)

Small web dashboard for watching how hard your Linux box is working: temps, voltages, disk SMART, GPU load. Built for home servers and Unraid; runs in Docker or straight on the host.

Metrics are collected in a background thread so the UI stays snappy. Short history lives in memory, longer ranges in SQLite.

## What it shows

Live and historical graphs for CPU and GPU utilization, motherboard-style voltages from `lm-sensors`, disk temperatures via `smartctl`, plus SMART details when you need them.

## Auto-detection

- **Disks:** `SMART_DEVICES=auto` walks block devices (`/dev/sda`, `/dev/nvme0n1`, …).
- **NVIDIA:** `ENABLE_NVIDIA=auto` turns on when `nvidia-smi` exists.
- **AMD / Intel GPUs:** sysfs + hwmon when the stack exposes them (`ENABLE_AMD`, `ENABLE_INTEL`).

Pinned drives look like:

```bash
SMART_DEVICES=/dev/sda,/dev/nvme0n1
```

## Docker Compose

```bash
cp .env.example .env
```

Set at least `AUTH_PASS` and `SECRET_KEY`, tweak `SMART_DEVICES` if you want. Then:

```bash
docker compose up -d --build
```

Open `http://<host>:<PORT>` (default port 8181). History goes under `./data`.

## Running without Docker

You need Linux, Python 3.11+, `lm-sensors` and `smartmontools`. NVIDIA metrics need `nvidia-smi` on the PATH.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python server.py
```

Then browse to `http://127.0.0.1:8181`.

## Environment

See `.env.example` for everything. Most people touch `AUTH_PASS`, `SECRET_KEY`, disk list, and the `ENABLE_*` toggles (`auto`, `true`, or `false`).

## Image

Prebuilt containers live on GHCR (`ghcr.io/antond645-cpu/hw-monitor`). Each git tag publishes matching semver tags; `latest` follows the newest release.

## Unraid Community Applications

Included templates:

- `unraid/hw-monitor.xml`
- `ca_profile.xml`

**Own Apps feed:** Apps → Settings → add a custom repository with this XML:

`https://raw.githubusercontent.com/antond645-cpu/hw_monitor/main/unraid/hw-monitor.xml`

Refresh, search “HW Monitor”, install.

**Global CA listing:** submit the repo at [ca.unraid.net/submit](https://ca.unraid.net/submit) so it appears for everyone after review.

## Caveats

Apple and Windows hosts won’t expose the same sysfs/sensor surface—this targets Linux.

In Docker, SMART needs `/dev` (and usually `SYS_ADMIN` + `SYS_RAWIO` caps) mounted so `smartctl` can talk to drives. AMD and Intel GPU numbers depend heavily on kernel and Mesa/i915 versions.
