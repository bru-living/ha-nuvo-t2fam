"""Direct FM tuning number entity."""

from homeassistant.components.number import NumberEntity
from homeassistant.const import UnitOfFrequency
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, MAX_FREQUENCY, MIN_FREQUENCY
from .entity import NuvoEntity


async def async_setup_entry(hass, entry, async_add_entities):
    connection = hass.data[DOMAIN][entry.entry_id]
    registry = er.async_get(hass)
    legacy_entity_id = registry.async_get_entity_id(
        "number", DOMAIN, f"{entry.entry_id}_preset_selection"
    )
    if legacy_entity_id:
        registry.async_remove(legacy_entity_id)
    async_add_entities(
        [
            NuvoFrequency(entry, connection),
            NuvoStationFrequency(entry, connection),
        ]
    )


class NuvoFrequency(NuvoEntity, NumberEntity):
    _attr_name = "FM frequency"
    _attr_native_min_value = MIN_FREQUENCY
    _attr_native_max_value = MAX_FREQUENCY
    _attr_native_step = 0.01
    _attr_native_unit_of_measurement = UnitOfFrequency.MEGAHERTZ
    _attr_icon = "mdi:radio-fm"

    def __init__(self, entry, connection):
        super().__init__(entry, connection, "frequency")

    @property
    def native_value(self):
        return self.connection.state.frequency

    async def async_set_native_value(self, value):
        await self.connection.tune(value)


class NuvoStationFrequency(NuvoEntity, NumberEntity):
    """Edit the saved frequency of the currently tuned local station."""

    _attr_name = "Station frequency"
    _attr_native_min_value = MIN_FREQUENCY
    _attr_native_max_value = MAX_FREQUENCY
    _attr_native_step = 0.01
    _attr_native_unit_of_measurement = UnitOfFrequency.MEGAHERTZ
    _attr_icon = "mdi:radio-tower"

    def __init__(self, entry, connection):
        super().__init__(entry, connection, "station_frequency")

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.connection.preset_catalog.preset_for_frequency(
                self.connection.state.frequency
            )
            is not None
        )

    @property
    def native_value(self):
        preset = self.connection.preset_catalog.preset_for_frequency(
            self.connection.state.frequency
        )
        return preset.frequency if preset else None

    async def async_set_native_value(self, value):
        await self.connection.preset_catalog.async_set_current_frequency(value)
