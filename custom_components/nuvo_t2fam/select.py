"""Direct preset selection for preset bank 1."""

from homeassistant.components.select import SelectEntity

from .const import DOMAIN
from .entity import NuvoEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([NuvoPresetSelect(entry, hass.data[DOMAIN][entry.entry_id])])


class NuvoPresetSelect(NuvoEntity, SelectEntity):
    """Select one of the 20 presets in bank 1."""

    _attr_name = "Preset"
    _attr_icon = "mdi:playlist-music"
    def __init__(self, entry, connection):
        super().__init__(entry, connection, "preset_select")

    def _option_label(self, number: int) -> str:
        name = self.connection.state.preset_names.get(number)
        return f"{number}: {name}" if name else f"Preset {number}"

    @property
    def options(self):
        return [self._option_label(number) for number in range(1, 21)]

    @property
    def current_option(self):
        preset = self.connection.state.preset
        if preset is None:
            return None
        return self._option_label(preset)

    async def async_select_option(self, option: str) -> None:
        number = int(option.split(":", 1)[0]) if ":" in option else int(option.removeprefix("Preset "))
        await self.connection.send(f"PRESET1{number}")
