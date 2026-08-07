# NuVo NV-T2FAM for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[![Open your Home Assistant instance and add this repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bru-living&repository=ha-nuvo-t2fam&category=integration)

A local, UI-configured custom integration for **one tuner (A or B)** of the NuVo NV-T2FAM. It intentionally supports FM only. It does not create AM, Sirius, DAB, or second-tuner entities.

Version 1.8.1 expands live diagnostics with the connection type, endpoint and full serial settings.

## Features

- Raw serial-over-TCP (including suitably configured Global Caché bridges)
- Local serial device at 57600 baud, 8N1
- Power/source control, direct FM tuning, seek up/down, preset next/previous
- Direct dropdown selection of presets 1-20 in preset bank 1
- Automatic preset names from the tuner (for example, `5: Radio Nova`)
- Current frequency, RDS station name, and RDS radio text
- Separate Home Assistant sensors for frequency, RDS metadata, and device version
- Diagnostic connection-status sensor with response timestamps, reconnect count, and last error
- Unsolicited status parsing, automatic reconnect with backoff, and diagnostics
- Startup `*VER` check that requires an NV-T2FAM response

## Install

### HACS custom repository

1. In HACS, open **Integrations > Custom repositories**.
2. Add `https://github.com/bru-living/ha-nuvo-t2fam` and select **Integration** as the category.
3. Install **NuVo NV-T2FAM**.
4. Restart Home Assistant.

### Manual

Copy `custom_components/nuvo_t2fam` into the `custom_components` directory under your Home Assistant configuration directory, then restart Home Assistant.

## Configure

Open **Settings > Devices & services > Add integration**, search for **NuVo NV-T2FAM**, then choose:

- **TCP**: hostname/IP and raw TCP port (often 4999; use the value configured on your bridge).
- **Serial**: local path such as `/dev/ttyUSB0`.
- **Tuner**: A or B. Only the selected tuner gets entities.

Configure the bridge for transparent/raw TCP, ASCII, 57600 baud, 8 data bits, no parity, 1 stop bit, and no flow control.

The setup and every Home Assistant startup send `*VER` and require the endpoint to identify itself as an `NV-T2FAM` before the integration loads.

## Change the connection

Open **Settings > Devices & services > NuVo NV-T2FAM**, use the three-dot menu, and select **Reconfigure**. Change the serial device path (or TCP host/port) and tuner. Home Assistant tests the new endpoint with `*VER` before saving it, then reloads the integration automatically.

Set a station with the **FM frequency** number entity or call `media_player.play_media` with a numeric MHz content ID, for example `99.9`.

## Named preset favourites

When the tuner reports a preset, the integration reads its built-in description and uses it in the Preset dropdown, such as **5: Radio Nova**. Names are learned as presets are tuned because the NV-T2FAM protocol does not provide a command to list every preset description at once. Presets not yet reported remain labelled **Preset 1**, **Preset 2**, and so on.

## Standalone operation

This integration is designed for a tuner that is **not attached to NuVoNet**. It uses the protocol's standalone global `*ON` and `*OFF` commands. NuVoNet operation is intentionally unsupported.

## Protocol scope

Commands are ASCII and CR-terminated. This integration uses global `ON`/`OFF` plus the selected tuner's `STATUS`, `FM<frequency-in-MHz>`, `SEEK+/-`, `PRESET+/-`, `CHAN`, `TITLE`, and `SRCFM`. Responses must begin with `#`; responses for the unselected tuner are ignored.

## Troubleshooting

Enable debug logging:

```yaml
logger:
  logs:
    custom_components.nuvo_t2fam: debug
```

Download diagnostics from the integration page; host/path values are redacted.

Report problems through the [GitHub issue tracker](https://github.com/bru-living/ha-nuvo-t2fam/issues). Remove credentials and public addresses from logs before posting them.
