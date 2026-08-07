"""Seek and preset buttons."""

import asyncio

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .entity import NuvoEntity

BUTTONS = (
    ("power_on", "Power on", "ON", "mdi:power", True),
    ("power_off", "Power off", "OFF", "mdi:power-off", True),
    ("seek_up", "Seek forward", "SEEK+", "mdi:fast-forward", False),
    ("seek_down", "Seek backward", "SEEK-", "mdi:rewind", False),
    ("preset_next", "Next preset", "PRESET+", "mdi:skip-next", False),
    ("preset_previous", "Previous preset", "PRESET-", "mdi:skip-previous", False),
)


async def async_setup_entry(hass, entry, async_add_entities):
    connection = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NuvoButton(entry, connection, *item) for item in BUTTONS])


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
