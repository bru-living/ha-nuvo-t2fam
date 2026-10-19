"""Home Assistant-owned FM station discovery and preset storage."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import logging
import math

from homeassistant.helpers.storage import Store

from .const import DOMAIN, MAX_FREQUENCY, MIN_FREQUENCY

_LOGGER = logging.getLogger(__name__)
_STORAGE_VERSION = 1
_MAX_STATIONS = 50
_FM_CHANNEL_STEP = 0.1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LocalPreset:
    """A station preset stored by Home Assistant rather than the tuner."""

    frequency: float
    first_seen: str
    last_seen: str
    rds_name: str | None = None
    custom_name: str | None = None
    hidden: bool = False

    @property
    def name(self) -> str:
        """Prefer a manual override, then RDS, then a frequency fallback."""
        return self.custom_name or self.rds_name or f"FM {self.frequency:g}"

    @property
    def label(self) -> str:
        frequency = f"{self.frequency:.2f}".rstrip("0").rstrip(".")
        return f"{self.name} · {frequency} FM"


def _station_frequency(value: float) -> float:
    """Use the 100 kHz broadcast channel, not a tuner fine-tune offset."""
    return round(
        math.floor(float(value) / _FM_CHANNEL_STEP + 0.5) * _FM_CHANNEL_STEP,
        1,
    )


class LocalPresetCatalog:
    """Discover stations with the tuner and persist them in HA storage."""

    def __init__(self, hass, entry_id: str, connection) -> None:
        self.hass = hass
        self.connection = connection
        self._store = Store(hass, _STORAGE_VERSION, f"{DOMAIN}.{entry_id}.presets")
        self._presets: dict[str, LocalPreset] = {}
        self._scan_task: asyncio.Task | None = None
        self._rds_save_task: asyncio.Task | None = None
        self._remove_connection_listener = connection.add_listener(
            self._handle_connection_update
        )
        self.status = "Never scanned"
        self.last_scan_started: str | None = None
        self.last_scan_finished: str | None = None
        self.last_scan_error: str | None = None
        self.last_scan_found = 0

    @property
    def scanning(self) -> bool:
        return self._scan_task is not None and not self._scan_task.done()

    @property
    def presets(self) -> list[LocalPreset]:
        return sorted(self._presets.values(), key=lambda item: item.frequency)

    @property
    def visible_presets(self) -> list[LocalPreset]:
        return [preset for preset in self.presets if not preset.hidden]

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        for item in data.get("presets", []):
            try:
                stored = dict(item)
                legacy_name = stored.pop("name", None)
                stored["frequency"] = _station_frequency(stored["frequency"])
                preset = LocalPreset(**stored)
                if (
                    not preset.custom_name
                    and legacy_name
                    and legacy_name != preset.rds_name
                    and not legacy_name.startswith("FM ")
                ):
                    preset.custom_name = legacy_name
                self._presets[self._key(preset.frequency)] = preset
            except (TypeError, ValueError):
                _LOGGER.warning("Ignored an invalid stored NuVo station preset: %r", item)

    async def async_save(self) -> None:
        await self._store.async_save(
            {"presets": [asdict(preset) for preset in self.presets]}
        )

    async def async_stop(self) -> None:
        """Cancel and await an active scan before the integration unloads."""
        self._remove_connection_listener()
        for task in (self._scan_task, self._rds_save_task):
            if task is None or task.done():
                continue
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def _handle_connection_update(self) -> None:
        """Adopt RDS received after scanning unless a custom name overrides it."""
        frequency = self.connection.state.frequency
        rds_name = self.connection.state.station_name
        preset = self.preset_for_frequency(frequency)
        if preset is None or not rds_name:
            return
        cleaned_name = rds_name.strip()
        if not cleaned_name or preset.rds_name == cleaned_name:
            return
        preset.rds_name = cleaned_name
        preset.last_seen = _utc_now()
        if self._rds_save_task is None or self._rds_save_task.done():
            self._rds_save_task = self.hass.async_create_task(
                self._async_save_rds_update(), "Save NuVo RDS station name"
            )

    async def _async_save_rds_update(self) -> None:
        await self.async_save()
        self.connection.notify()

    def start_scan(self) -> bool:
        """Start a background scan and return False if one is already running."""
        if self.scanning:
            return False
        self._scan_task = self.hass.async_create_task(
            self._async_scan(), "Discover NuVo FM stations"
        )
        return True

    def preset_for_label(self, label: str) -> LocalPreset | None:
        return next((item for item in self.presets if item.label == label), None)

    def preset_for_frequency(self, frequency: float | None) -> LocalPreset | None:
        if frequency is None:
            return None
        return self._presets.get(self._key(frequency))

    async def async_select(self, label: str) -> None:
        preset = self.preset_for_label(label)
        if preset is None:
            raise ValueError(f"Unknown discovered station: {label}")
        await self.connection.tune(preset.frequency)

    async def async_set_hidden(self, label: str, hidden: bool) -> None:
        """Hide or show a station without losing its name or frequency."""
        preset = self.preset_for_label(label)
        if preset is None:
            raise ValueError(f"Unknown discovered station: {label}")
        preset.hidden = hidden
        await self.async_save()
        self.connection.notify()

    async def async_delete_current(self) -> None:
        """Permanently remove the currently tuned discovered station."""
        preset = self.preset_for_frequency(self.connection.state.frequency)
        if preset is None:
            raise ValueError("Tune a discovered station before removing it")
        self._presets.pop(self._key(preset.frequency), None)
        await self.async_save()
        self.connection.notify()

    async def async_set_current_name(self, value: str) -> None:
        """Set or clear the manual name for the currently tuned local preset."""
        preset = self.preset_for_frequency(self.connection.state.frequency)
        if preset is None:
            raise ValueError("Tune a discovered station before editing its name")
        preset.custom_name = value.strip() or None
        await self.async_save()
        self.connection.notify()

    async def async_set_current_frequency(self, value: float) -> None:
        """Move the currently tuned local preset to a new FM frequency."""
        preset = self.preset_for_frequency(self.connection.state.frequency)
        if preset is None:
            raise ValueError("Tune a discovered station before editing its frequency")
        new_frequency = round(float(value), 2)
        if not 87.5 <= new_frequency <= 108.0:
            raise ValueError("FM frequency must be between 87.5 and 108.0 MHz")
        old_key = self._key(preset.frequency)
        new_key = self._key(new_frequency)
        if new_key != old_key and new_key in self._presets:
            raise ValueError("Another discovered station already uses that frequency")
        self._presets.pop(old_key)
        preset.frequency = new_frequency
        preset.last_seen = _utc_now()
        self._presets[new_key] = preset
        await self.connection.tune(new_frequency)
        await self.async_save()
        self.connection.notify()

    async def async_save_current(self) -> bool:
        """Save the currently tuned station as a local preset."""
        frequency = self.connection.state.frequency
        if frequency is None:
            raise ValueError("Tune an FM station before saving it")
        normalised = _station_frequency(frequency)
        key = self._key(normalised)
        if key in self._presets:
            return False
        now = _utc_now()
        self._presets[key] = LocalPreset(
            frequency=normalised,
            first_seen=now,
            last_seen=now,
            rds_name=self.connection.state.station_name or None,
        )
        await self.async_save()
        self.connection.notify()
        return True

    async def async_step(self, direction: int) -> bool:
        """Tune the next or previous local preset, wrapping at band edges."""
        presets = self.visible_presets
        if not presets:
            return False
        current = self.preset_for_frequency(self.connection.state.frequency)
        index = (
            presets.index(current)
            if current in presets
            else (-1 if direction > 0 else 0)
        )
        target = presets[(index + direction) % len(presets)]
        await self.connection.tune(target.frequency)
        return True

    async def _async_scan(self) -> None:
        original_power = self.connection.state.powered
        original_frequency = self.connection.state.frequency
        self.last_scan_started = _utc_now()
        self.last_scan_finished = None
        self.last_scan_error = None
        self.last_scan_found = 0
        self.status = "Starting scan"
        self.connection.notify()

        try:
            if not self.connection.state.available:
                raise ConnectionError("NuVo tuner is not connected")
            if original_power is False:
                await self.connection.send_global("ON")
                await asyncio.sleep(0.5)
            await self.connection.send("SRCFM", refresh_metadata=False)
            await self.connection.tune(MIN_FREQUENCY, refresh_metadata=False)
            await self._wait_for_frequency(MIN_FREQUENCY, timeout=5)

            seen: set[str] = set()
            seek_fallback_used = False
            try:
                for _ in range(_MAX_STATIONS):
                    previous = self.connection.state.frequency
                    self.status = f"Seeking above {previous or MIN_FREQUENCY:.2f} FM"
                    self.connection.notify()
                    await self.connection.send("SEEK+", refresh_metadata=False)
                    frequency = await self._wait_for_frequency_change(
                        previous, timeout=15
                    )
                    key = self._key(frequency)
                    if key in seen:
                        break
                    seen.add(key)
                    station_name = await self._read_rds_name(frequency)
                    await self._record_station(frequency, station_name)
            except TimeoutError:
                seek_fallback_used = True
                self.status = "Seek unavailable; sweeping FM frequencies"
                self.connection.notify()
                await self._async_frequency_sweep(seen)

            # SEEK only reports stations above the tuner's signal threshold.
            # Always verify the full band so weaker stations are not omitted.
            if not seek_fallback_used:
                self.status = "Verifying all FM frequencies"
                self.connection.notify()
                await self._async_frequency_sweep(seen)

            self.status = f"Scan complete · {self.last_scan_found} stations found"
        except asyncio.CancelledError:
            self.status = "Scan cancelled"
            raise
        except (ConnectionError, OSError, TimeoutError, ValueError) as err:
            self.last_scan_error = f"{type(err).__name__}: {err}"
            self.status = f"Scan failed · {err}"
            _LOGGER.error("NuVo station discovery failed: %s", self.last_scan_error)
        finally:
            try:
                if original_frequency is not None and self.connection.state.available:
                    await self.connection.tune(original_frequency)
                    await self._wait_for_frequency(original_frequency, timeout=5)
                if original_power is False and self.connection.state.available:
                    await self.connection.send_global("OFF")
            except (ConnectionError, OSError, TimeoutError, ValueError) as err:
                restore_error = f"Could not restore tuner state: {err}"
                self.last_scan_error = (
                    f"{self.last_scan_error}; {restore_error}"
                    if self.last_scan_error
                    else restore_error
                )
                self.status = f"Scan finished · {restore_error}"
                _LOGGER.error("NuVo station scan restore failed: %s", err)
            self.last_scan_finished = _utc_now()
            self.connection.notify()

    async def _record_station(
        self, frequency: float, station_name: str | None
    ) -> None:
        """Persist one tuner stop, keeping custom names and hidden state."""
        now = _utc_now()
        station_frequency = _station_frequency(frequency)
        key = self._key(station_frequency)
        existing = self._presets.get(key)
        if existing is None:
            preset = LocalPreset(
                frequency=station_frequency,
                rds_name=station_name,
                first_seen=now,
                last_seen=now,
            )
        else:
            existing.rds_name = station_name or existing.rds_name
            existing.last_seen = now
            preset = existing
        self._presets[key] = preset
        self.last_scan_found += 1
        self.status = f"Found {preset.label}"
        await self.async_save()
        self.connection.notify()

    async def _async_frequency_sweep(self, seen: set[str]) -> None:
        """Fallback for tuners whose SEEK command does not report a stop."""
        steps = int(round((MAX_FREQUENCY - MIN_FREQUENCY) / 0.1)) + 1
        for index in range(steps):
            frequency = round(MIN_FREQUENCY + index * 0.1, 1)
            self.status = f"Sweeping {frequency:.1f} FM"
            self.connection.notify()
            await self.connection.tune(frequency, refresh_metadata=False)
            await asyncio.sleep(0.8)
            await self.connection.send("CHAN", refresh_metadata=False)
            await self.connection.send("TITLE", refresh_metadata=False)
            await asyncio.sleep(0.35)
            if self.connection.state.station_name:
                actual = self.connection.state.frequency or frequency
                key = self._key(actual)
                if key not in seen:
                    seen.add(key)
                    await self._record_station(actual, self.connection.state.station_name)

    async def _read_rds_name(self, frequency: float) -> str | None:
        """Give RDS a bounded opportunity to decode at the current station."""
        for delay in (0.75, 1.25, 2.0):
            await asyncio.sleep(delay)
            await self.connection.send("CHAN", refresh_metadata=False)
            await self.connection.send("TITLE", refresh_metadata=False)
            await asyncio.sleep(0.25)
            if self._key(self.connection.state.frequency or 0) != self._key(frequency):
                return None
            if self.connection.state.station_name:
                return self.connection.state.station_name.strip()
        return None

    async def _wait_for_frequency_change(
        self, previous: float | None, timeout: float
    ) -> float:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        previous_key = self._key(previous) if previous is not None else None
        while loop.time() < deadline:
            frequency = self.connection.state.frequency
            if frequency is not None and self._key(frequency) != previous_key:
                return frequency
            await asyncio.sleep(0.2)
        raise TimeoutError("tuner did not finish seeking")

    async def _wait_for_frequency(self, expected: float, timeout: float) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        expected_key = self._key(expected)
        while loop.time() < deadline:
            frequency = self.connection.state.frequency
            if frequency is not None and self._key(frequency) == expected_key:
                return
            await asyncio.sleep(0.2)
        raise TimeoutError(f"tuner did not report {expected:g} FM")

    @staticmethod
    def _key(frequency: float | None) -> str:
        return f"{_station_frequency(float(frequency)):.1f}"
