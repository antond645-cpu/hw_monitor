# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project bootstrap for public repository usage (`README`, `.env.example`, `.gitignore`).
- Docker Compose setup for one-command local deployment.
- Auto-detection of storage devices for SMART and disk I/O metrics.
- Auto mode for NVIDIA metrics (`ENABLE_NVIDIA=auto`).
- Auto mode for AMD GPU metrics (`ENABLE_AMD=auto`) via sysfs/hwmon.
- Auto mode for Intel GPU metrics (`ENABLE_INTEL=auto`) via sysfs/hwmon.
- Configurable app title via `APP_TITLE`.
- CI workflow for Docker image build checks.
- Release workflow to publish container images to GHCR (and optionally Docker Hub).
- MIT license and contribution guide.

## [1.0.0] - 2026-04-25

### Added
- First public-ready release of HW Monitor.
