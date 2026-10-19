# Changelog

All notable changes to this project are documented here.

## 1.15.1 - 2026-10-19

- Add persistent Home Assistant station discovery and local presets, independent of the tuner hardware banks.
- Add station save/remove, visibility, editable names and frequency correction controls.
- Normalise discovered FM frequencies and preserve station and power state after scanning.
- Prefer editable station names for station-logo lookup and now-playing labels.
- Use discovered stations for media-player sources and Next/Previous, retaining hardware presets as a fallback.
- Expand the README with setup, station-management guidance, upgrade notes and screenshots of the new station controls.
- Add automated protocol tests to CI and correct a pre-existing empty-RDS test expectation.

Compatibility: once local stations exist, the media-player source list uses their station labels. Automations depending on numeric hardware preset labels should be reviewed. Station-logo lookup contacts the external Radio Browser directory and currently searches Irish stations.

## 1.8.7 - 2026-08-31

- Add generated station artwork for the Home Assistant media proxy.
- Improve station title handling for cleaner Bru Living and Home Assistant now-playing display.
- Update integration manifest to version 1.8.7.

## 1.8.5 - 2026-08-10

- Add presets 1-20 as a native media-player source selector for direct control from the more-info view.
- Show learned preset descriptions in the media-player preset selector.

## 1.8.4 - 2026-08-10

- Show the preset name or current FM frequency on the media player card when RDS is unavailable.
- Preserve up to two decimal places in the displayed FM frequency.

## 1.8.3 - 2026-08-10

- Add Tune up and Tune down buttons using the NV-T2FAM `TUNE+` and `TUNE-` commands.
- Refresh tuner status and RDS metadata after each manual tuning step.

## 1.8.2 - 2026-08-07

- Add HACS and Hassfest validation workflows.
- Correct manifest key ordering for Hassfest validation.
- Add repository metadata required for default HACS inclusion.

## 1.8.1 - 2026-08-07

- Show TCP or serial connection details in the diagnostic sensor.
- Include serial settings, endpoint type, timestamps, reconnect count, and the last error in downloaded diagnostics.
- Map media previous/next controls to previous/next tuner presets.
- Expose dedicated rewind/fast-forward seek buttons.
- Cache RDS metadata per FM frequency and recover it after rapid preset changes.
- Read preset descriptions reported by the tuner.
- Add BRU Living/NuVo Home Assistant brand assets.
