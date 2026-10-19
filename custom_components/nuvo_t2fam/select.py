"""Direct preset selection for preset bank 1."""

from homeassistant.components.select import SelectEntity

from .const import DOMAIN
from .entity import NuvoEntity

async def async_setup_entry(hass, entry, async_add_entities):
    connection = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NuvoDiscoveredStationSelect(entry, connection),
            NuvoStationVisibilitySelect(entry, connection),
            NuvoPresetSelect(entry, connection),
        ]
    )


class NuvoDiscoveredStationSelect(NuvoEntity, SelectEntity):
    """Select an HA-local preset discovered from the FM band."""

    _attr_name = "Discovered station"
    _attr_icon = "mdi:radio-tower"

    def __init__(self, entry, connection):
        super().__init__(entry, connection, "discovered_station")

    @property
    def options(self):
        return [preset.label for preset in self.connection.preset_catalog.visible_presets]

    @property
    def current_option(self):
        preset = self.connection.preset_catalog.preset_for_frequency(
            self.connection.state.frequency
        )
        return preset.label if preset else None

    async def async_select_option(self, option: str) -> None:
        await self.connection.preset_catalog.async_select(option)


class NuvoStationVisibilitySelect(NuvoEntity, SelectEntity):
    """Hide or show individual discovered stations."""

    _attr_name = "Station visibility"
    _attr_icon = "mdi:eye-settings"

    def __init__(self, entry, connection):
        super().__init__(entry, connection, "station_visibility")

    @property
    def options(self):
        return [
            f"{'Hidden' if preset.hidden else 'Visible'}: {preset.label}"
            for preset in self.connection.preset_catalog.presets
        ]

    @property
    def current_option(self):
        current = self.connection.preset_catalog.preset_for_frequency(
            self.connection.state.frequency
        )
        if current is None:
            return None
        return f"{'Hidden' if current.hidden else 'Visible'}: {current.label}"

    async def async_select_option(self, option: str) -> None:
        prefix, label = option.split(": ", 1)
        await self.connection.preset_catalog.async_set_hidden(
            label, prefix == "Hidden"
        )


class NuvoPresetSelect(NuvoEntity, SelectEntity):
    """Select one of the 20 presets in bank 1."""

    _attr_name = "Hardware preset"
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
