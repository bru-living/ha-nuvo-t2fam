"""Power, tuning, seek, and preset buttons."""

import asyncio

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .entity import NuvoEntity

BUTTONS = (
    ("power_on", "Power on", "ON", "mdi:power", True),
    ("power_off", "Power off", "OFF", "mdi:power-off", True),
    ("tune_up", "Tune up", "TUNE+", "mdi:plus-circle-outline", False),
    ("tune_down", "Tune down", "TUNE-", "mdi:minus-circle-outline", False),
    ("seek_up", "Seek forward", "SEEK+", "mdi:fast-forward", False),
    ("seek_down", "Seek backward", "SEEK-", "mdi:rewind", False),
    ("preset_next", "Next preset", "PRESET+", "mdi:skip-next", False),
    ("preset_previous", "Previous preset", "PRESET-", "mdi:skip-previous", False),
)


async def async_setup_entry(hass, entry, async_add_entities):
    connection = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [NuvoButton(entry, connection, *item) for item in BUTTONS]
        + [
            NuvoStationDiscoveryButton(entry, connection),
            NuvoStationSaveButton(entry, connection),
            NuvoStationDeleteButton(entry, connection),
        ]
    )


class NuvoButton(NuvoEntity, ButtonEntity):
    def __init__(self, entry, connection, key, name, command, icon, global_command):
        super().__init__(entry, connection, key)
        self._attr_name = name
        self._command = command
        self._global_command = global_command
        self._attr_icon = icon

    async def async_press(self):
        if self._global_command:
            await self.connection.send_global(self._command)
        else:
            await self.connection.send(self._command)
        await asyncio.sleep(0.35)
        await self.connection.send("STATUS")


class NuvoStationDiscoveryButton(NuvoEntity, ButtonEntity):
    """Start a non-blocking scan for receivable FM stations."""

    _attr_name = "Discover FM stations"
    _attr_icon = "mdi:radio-tower"

    def __init__(self, entry, connection):
        super().__init__(entry, connection, "discover_fm_stations")

    @property
    def available(self) -> bool:
        return super().available and not self.connection.preset_catalog.scanning

    async def async_press(self):
        self.connection.preset_catalog.start_scan()


class NuvoStationDeleteButton(NuvoEntity, ButtonEntity):
    """Permanently remove the currently tuned local station."""

    _attr_name = "Remove current station"
    _attr_icon = "mdi:delete-outline"

    def __init__(self, entry, connection):
        super().__init__(entry, connection, "remove_current_station")

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.connection.preset_catalog.preset_for_frequency(
                self.connection.state.frequency
            )
            is not None
        )

    async def async_press(self):
        await self.connection.preset_catalog.async_delete_current()


class NuvoStationSaveButton(NuvoEntity, ButtonEntity):
    """Save a manually tuned station to the HA-local catalogue."""

    _attr_name = "Save current station"
    _attr_icon = "mdi:content-save-plus-outline"

    def __init__(self, entry, connection):
        super().__init__(entry, connection, "save_current_station")

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.connection.state.frequency is not None
            and self.connection.preset_catalog.preset_for_frequency(
                self.connection.state.frequency
            )
            is None
        )

    async def async_press(self):
        await self.connection.preset_catalog.async_save_current()
