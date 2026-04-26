# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
### Changed

## [1.0.3] - 2026-04-26

### Fixed
- Release workflow parsing so tag pushes publish images successfully.

## [1.0.2] - 2026-04-25

### Added
- AMD GPU metric collection via sysfs/hwmon (`ENABLE_AMD=auto|true|false`).
- Intel GPU metric collection via sysfs/hwmon (`ENABLE_INTEL=auto|true|false`).
- Unraid template options for AMD/Intel GPU toggles.
- Documentation updates for AMD/Intel support.

## [1.0.1] - 2026-04-25

### Added
- Unraid CA template (`unraid/hw-monitor.xml`).
- CA maintainer profile (`ca_profile.xml`).
- Submission guidance for Unraid Community Applications.

## [1.0.0] - 2026-04-25

### Added
- Project bootstrap for public repository usage (`README`, `.env.example`, `.gitignore`).
- Docker Compose setup for one-command local deployment.
- Auto-detection of storage devices for SMART and disk I/O metrics.
- Auto mode for NVIDIA metrics (`ENABLE_NVIDIA=auto`).
- Configurable app title via `APP_TITLE`.
- CI workflow for Docker image build checks.
- Release workflow to publish container images to GHCR (and optionally Docker Hub).
- MIT license and contribution guide.
