# Changelog

All notable changes to this project are documented here.

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
