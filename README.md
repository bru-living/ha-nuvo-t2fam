# NuVo NV-T2FAM for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[![Open your Home Assistant instance and add this repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bru-living&repository=ha-nuvo-t2fam&category=integration)

A local, UI-configured custom integration for **one tuner (A or B)** of the NuVo NV-T2FAM. It intentionally supports FM only. It does not create AM, Sirius, DAB, or second-tuner entities.

## Screenshots

### Device controls and connection diagnostics

![NuVo NV-T2FAM device page showing power, frequency, seek and preset controls](docs/images/device-overview.png)

### Media player details

![NuVo NV-T2FAM media player showing the current FM frequency and preset controls](docs/images/media-player-details.png)

The current release also adds a preset/source selector to the media-player details view. Home Assistant displays controls according to the available space and frontend version.

## Features

### Tuner controls

| Home Assistant entity | What it provides |
| --- | --- |
| **Media player** | Power on/off, current tuner state, current frequency, RDS station name and radio text. Previous/next selects the previous/next preset, and the source selector provides direct access to presets 1-20. Numeric `media_player.play_media` calls tune directly to an FM frequency. |
| **FM frequency number** | Direct tuning from 87.50 to 108.00 MHz in 0.01 MHz steps. |
| **Preset select** | Direct selection of all 20 presets in preset bank 1. Learned tuner descriptions are shown as friendly names, for example `5: Radio Nova`. |
| **Control buttons** | Power on/off, tune up/down by one FM step, seek forward/backward to the next station, and next/previous preset. Seek buttons use fast-forward/rewind icons; preset buttons use next/previous icons. |
| **State sensors** | Current FM frequency, current preset number, preset name, RDS station name and RDS radio text. |
| **Diagnostic sensors** | Device firmware/hardware version and live connection status. |

When a station has no RDS, the media player card falls back to the preset name or the current FM frequency instead of showing a blank title.

The controls deliberately distinguish between:

- **Tune up/down**: move by one tuner frequency step using `TUNE+` or `TUNE-`.
- **Seek forward/backward**: scan to the next receivable FM station using `SEEK+` or `SEEK-`.
- **Previous/next**: move through the tuner's stored presets using `PRESET-` or `PRESET+`.

### RDS and preset handling

- Parses both command responses and unsolicited tuner updates.
- Shows the RDS station name and radio text on the media player and as separate sensors.
- Falls back to the learned preset name or exact FM frequency when a station supplies no RDS.
- Polls RDS repeatedly after tuning, seeking or changing preset because some stations and tuners take time to return metadata.
- Keeps valid RDS data when the tuner briefly returns an empty response.
- Caches RDS by frequency so known station information can be restored when returning to a station during rapid preset changes.
- Learns preset descriptions as each preset is tuned and uses them as friendly names in the preset dropdown.
- Updates preset state immediately while waiting for the tuner response, making repeated preset changes responsive.

### Connections and reliability

- UI configuration for either a raw serial-over-TCP bridge or a local serial device.
- Compatible with transparent TCP serial bridges, including suitably configured Global Caché devices.
- Uses the NV-T2FAM serial settings: ASCII, 57600 baud, 8 data bits, no parity, 1 stop bit, no flow control, and carriage-return command termination.
- Tests the endpoint with `*VER` during initial setup, reconfiguration and Home Assistant startup, and requires an NV-T2FAM version response.
- Reconfigure flow for changing TCP host/port, serial device path, or selected tuner without removing the integration.
- Serialized and paced command writes for reliable operation through slower serial-over-TCP bridges.
- Automatic reconnection with backoff, response monitoring, and silent-connection detection.

### Diagnostics and troubleshooting

- A connection-status sensor remains available while disconnected.
- Live diagnostic attributes include connection type, TCP host/port or serial path, tuner, serial settings, connection timestamps, last response, reconnect count and last error.
- Downloadable Home Assistant diagnostics include connection and tuner state while redacting the TCP host or serial device path.
- Debug logging records transmitted commands, received responses, parsing and connection activity.

### Intentional scope

- Supports the **NuVo NV-T2FAM only**.
- Creates entities for **one configurable tuner, A or B**, rather than both tuners.
- Supports **FM only**; AM, Sirius and DAB are deliberately excluded.
- Designed for standalone operation without NuVoNet and uses the standalone global `*ON` and `*OFF` commands.

## Install

### HACS custom repository

1. In HACS, open **Integrations > Custom repositories**.
2. Add `https://github.com/bru-living/ha-nuvo-t2fam` and select **Integration** as the category.
3. Search for **Bru** if the custom repository is not found under its full integration name, then install **NuVo NV-T2FAM**.
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

Commands are ASCII and CR-terminated. This integration uses global `ON`/`OFF` plus the selected tuner's `STATUS`, `FM<frequency-in-MHz>`, `TUNE+/-`, `SEEK+/-`, `PRESET+/-`, `CHAN`, `TITLE`, and `SRCFM`. Responses must begin with `#`; responses for the unselected tuner are ignored.

## Troubleshooting

Enable debug logging:

```yaml
logger:
  logs:
    custom_components.nuvo_t2fam: debug
```

Download diagnostics from the integration page; host/path values are redacted.

Report problems through the [GitHub issue tracker](https://github.com/bru-living/ha-nuvo-t2fam/issues). Remove credentials and public addresses from logs before posting them.
