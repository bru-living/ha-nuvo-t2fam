"""Editable names for Home Assistant-owned station presets."""

from homeassistant.components.text import TextEntity, TextMode

from .const import DOMAIN
from .entity import NuvoEntity


async def async_setup_entry(hass, entry, async_add_entities):
    connection = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NuvoStationName(entry, connection)])


class NuvoStationName(NuvoEntity, TextEntity):
    """Edit the display name of the currently tuned discovered station."""

    _attr_name = "Station name"
    _attr_icon = "mdi:form-textbox"
    _attr_mode = TextMode.TEXT
    _attr_native_min = 0
    _attr_native_max = 64

    def __init__(self, entry, connection):
        super().__init__(entry, connection, "station_name_override")

    @property
    def _current_preset(self):
        return self.connection.preset_catalog.preset_for_frequency(
            self.connection.state.frequency
        )

    @property
    def native_value(self):
        preset = self._current_preset
        return preset.name if preset else None

    @property
    def available(self) -> bool:
        return super().available and self._current_preset is not None

    async def async_set_value(self, value: str) -> None:
        await self.connection.preset_catalog.async_set_current_name(value)
