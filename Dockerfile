FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8181

WORKDIR /app

# lm-sensors provides `sensors`, smartmontools provides `smartctl`.
# curl is used for HEALTHCHECK, tini handles proper PID 1 reaping.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        lm-sensors \
        smartmontools \
        libcap2-bin \
        curl \
        tini \
 && rm -rf /var/lib/apt/lists/* \
 # When running as non-root, supplementary capabilities (cap_sys_rawio for
 # SCSI/SAT IOCTL and cap_sys_admin for NVME_IOCTL_ADMIN_CMD) may not end up
 # in the effective set even with --privileged. Setting file capabilities on
 # smartctl grants only the privileges required for SMART reads.
 && setcap cap_sys_admin,cap_sys_rawio+eip /usr/sbin/smartctl

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py collector.py server.py index.html ./

# SQLite history directory (mount as a volume for persistence).
RUN mkdir -p /var/lib/hw_monitor

# User defaults compatible with Unraid (nobody:users = 99:100):
# shared volumes are typically owned by 99:100, so the container can write
# into /mnt/user/appdata/... without extra chown. Override via build args.
ARG PUID=99
ARG PGID=100
RUN (getent group ${PGID} || groupadd --gid ${PGID} app) \
 && (getent passwd ${PUID} || useradd --uid ${PUID} --gid ${PGID} \
        --no-create-home --shell /usr/sbin/nologin app) \
 && chown -R ${PUID}:${PGID} /app /var/lib/hw_monitor \
 # /dev/sd* and /dev/nvme* are usually root:disk (gid=6) with mode 660.
 # Without membership in disk, smartctl can fail with Permission denied and
 # HDD/NVMe temperatures stay empty. Add the runtime user to disk by name.
 && APP_USER="$(getent passwd ${PUID} | cut -d: -f1)" \
 && usermod -aG disk "${APP_USER}"

# Use USER by name, not uid:gid. This allows runc to call initgroups() and
# include supplementary groups (including disk), avoiding EACCES on /dev/*.
USER app

EXPOSE 8181

HEALTHCHECK --interval=30s --timeout=4s --start-period=10s --retries=3 \
    CMD ["/bin/sh", "-c", "curl -fsS http://127.0.0.1:${PORT:-8181}/healthz || exit 1"]

ENTRYPOINT ["/usr/bin/tini", "--"]

# gunicorn: one worker hosts the background Collector; threads handle requests.
CMD ["/bin/sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8181} --workers 1 --threads 8 --access-logfile - --error-logfile - server:app"]
