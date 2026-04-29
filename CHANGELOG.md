# Changelog

Changes worth knowing about land here.

Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing queued right now.

## [1.0.4] - 2026-04-29

### Changed

- README and contributor notes rewritten for clarity; added GHCR image pointer and stripped stiff boilerplate wording.
- Unraid CA template overview tweaked to sound less like canned copy.

### Added

- Workflow that opens a GitHub Release for each `v*` tag, using that version’s changelog entry as the description.

## [1.0.3] - 2026-04-26

### Fixed

- Release workflow so tag pushes reliably publish container images again.

## [1.0.2] - 2026-04-25

### Added

- AMD GPU graphs via sysfs/hwmon (`ENABLE_AMD`).
- Intel GPU graphs via sysfs/hwmon (`ENABLE_INTEL`).
- Matching Unraid template toggles plus docs.

## [1.0.1] - 2026-04-25

### Added

- Unraid XML template (`unraid/hw-monitor.xml`).
- Maintainer profile stub (`ca_profile.xml`).
- Steps for submitting to Community Applications.

## [1.0.0] - 2026-04-25

### Added

- First public drop: Flask UI, Compose file, SMART + sensor autodiscovery, NVIDIA auto mode, SQLite history.
- CI for Docker builds, release pipeline to GHCR (Docker Hub optional), MIT license, basic docs.
