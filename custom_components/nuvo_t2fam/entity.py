"""Shared NuVo entity."""

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN


class NuvoEntity(Entity):
    _attr_has_entity_name = True

    def __init__(self, entry, connection, suffix: str) -> None:
        self.connection = connection
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"NuVo NV-T2FAM Tuner {connection.tuner}",
            manufacturer="NuVo",
            model="NV-T2FAM",
        )

    @property
    def available(self) -> bool:
        return self.connection.state.available

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.connection.add_listener(self.async_write_ha_state))
