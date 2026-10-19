"""Informational sensors for the NuVo NV-T2FAM."""

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory, UnitOfFrequency

from .const import BAUD_RATE, CONNECTION_SERIAL, DOMAIN
from .entity import NuvoEntity


@dataclass(frozen=True, kw_only=True)
class NuvoSensorDescription:
    key: str
    name: str
    icon: str
    native_unit: str | None = None
    device_class: SensorDeviceClass | None = None
    entity_category: EntityCategory | None = None


SENSORS = (
    NuvoSensorDescription(
        key="connection_status",
        name="Connection status",
        icon="mdi:lan-connect",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NuvoSensorDescription(
        key="frequency",
        name="Current FM frequency",
        icon="mdi:radio-fm",
        native_unit=UnitOfFrequency.MEGAHERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
    ),
    NuvoSensorDescription(
        key="station_name",
        name="RDS station name",
        icon="mdi:radio-tower",
    ),
    NuvoSensorDescription(
        key="radio_text",
        name="RDS radio text",
        icon="mdi:text-long",
    ),
    NuvoSensorDescription(
        key="preset",
        name="Current preset",
        icon="mdi:playlist-music",
    ),
    NuvoSensorDescription(
        key="preset_name",
        name="Preset name",
        icon="mdi:playlist-star",
    ),
    NuvoSensorDescription(
        key="version",
        name="Device version",
        icon="mdi:information-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NuvoSensorDescription(
        key="station_discovery",
        name="Station discovery",
        icon="mdi:radio-tower",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    connection = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        NuvoStateSensor(entry, connection, description) for description in SENSORS
    )


class NuvoStateSensor(NuvoEntity, SensorEntity):
    """Expose one field from the shared tuner state."""

    def __init__(self, entry, connection, description: NuvoSensorDescription):
        super().__init__(entry, connection, f"sensor_{description.key}")
        self.description = description
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_native_unit_of_measurement = description.native_unit
        self._attr_device_class = description.device_class
        self._attr_entity_category = description.entity_category

    @property
    def native_value(self) -> Any:
        if self.description.key == "connection_status":
            return "Connected" if self.connection.state.available else "Disconnected"
        if self.description.key == "station_discovery":
            return self.connection.preset_catalog.status
        return getattr(self.connection.state, self.description.key)

    @property
    def available(self) -> bool:
        if self.description.key == "connection_status":
            return True
        return super().available

    @property
    def extra_state_attributes(self):
        if self.description.key == "station_discovery":
            catalog = self.connection.preset_catalog
            return {
                "scanning": catalog.scanning,
                "preset_count": len(catalog.presets),
                "found_this_scan": catalog.last_scan_found,
                "last_scan_started": catalog.last_scan_started,
                "last_scan_finished": catalog.last_scan_finished,
                "last_scan_error": catalog.last_scan_error,
                "stations": [preset.label for preset in catalog.presets],
            }
        if self.description.key != "connection_status":
            return None
        state = self.connection.state
        config = self.connection.config
        connection_type = config.get("connection_type")
        attributes = {
            "connection_type": connection_type,
            "tuner": self.connection.tuner,
            "baud_rate": BAUD_RATE,
            "data_bits": 8,
            "parity": "none",
            "stop_bits": 1,
            "flow_control": "none",
            "connected_at": state.connected_at,
            "disconnected_at": state.disconnected_at,
            "last_response_at": state.last_response_at,
            "reconnect_count": state.reconnect_count,
            "last_error": state.last_connection_error,
        }
        if connection_type == CONNECTION_SERIAL:
            attributes["serial_device"] = config.get("serial_path")
        else:
            attributes["host"] = config.get("host")
            attributes["port"] = config.get("port")
        return attributes
