"""NuVo NV-T2FAM integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_TUNER, DOMAIN, PLATFORMS
from .presets import LocalPresetCatalog
from .protocol import InvalidDeviceError, NuvoConnection


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    connection = NuvoConnection(dict(entry.data), entry.data[CONF_TUNER], lambda: None)
    try:
        await connection.probe()
    except (OSError, TimeoutError, InvalidDeviceError) as err:
        raise ConfigEntryNotReady(f"Unable to verify NV-T2FAM: {err}") from err
    connection.preset_catalog = LocalPresetCatalog(hass, entry.entry_id, connection)
    await connection.preset_catalog.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = connection
    await connection.start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    connection = hass.data[DOMAIN].pop(entry.entry_id)
    await connection.preset_catalog.async_stop()
    await connection.stop()
    return True
