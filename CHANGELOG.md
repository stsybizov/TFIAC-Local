# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [0.2.2] - 2026-05-31

### Added
- Default entity icon `mdi:air-conditioner` on the climate entity.
- Project icon and local brand assets (`custom_components/tfiac_local/brand/`)
  so the HACS brands validation passes without a brands-repo PR.

### Fixed
- Sorted `manifest.json` keys (domain, name, then alphabetical) to pass hassfest.

## [0.2.1] - 2026-05-31

### Fixed
- Climate entity now reflects commands **immediately**. Optimistic state is
  written via `async_write_ha_state()` and cleared on the next poll. Previously
  the UI lagged one command behind, because the device's status response is
  delayed several seconds after a `SetMessage`.

## [0.2.0] - 2026-05-31

### Added
- Config flow (UI setup) and an options flow for the polling interval.
- `DataUpdateCoordinator`-based polling and a device-registry entry.
- English and Russian translations.
- HACS metadata (`hacs.json`) and a validation workflow.
- Unit tests for the UDP/XML transport and Home Assistant integration tests
  (config/options flow, setup/unload, entity behaviour).

### Changed
- Migrated from the legacy YAML `climate` platform to config entries. An
  existing YAML block is imported automatically and then deprecated.
- `unique_id` is derived from the device-reported name instead of the host IP,
  so a DHCP lease change no longer duplicates the entity.
- Hardened the client: `defusedxml` parsing, XML-escaping of outgoing values,
  `SetMessage` ACK validation, and optimistic status after commands (the device
  status lags a few seconds behind a command).

### Notes
- Requires Home Assistant 2024.11 or newer.
- Verified live against real hardware: all HVAC/fan/swing tokens, °F protocol /
  °C display conversion, and end-to-end control through HA.

## [0.1.0]

Baseline imported from the original repository
[andreimindru96/home-assistant-tfiac-ac](https://github.com/andreimindru96/home-assistant-tfiac-ac).

### Added
- Initial local TFIAC integration: legacy YAML `climate` platform and a CLI.
