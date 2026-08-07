"""Diagnostics for NuVo NV-T2FAM."""

from homeassistant.components.diagnostics import async_redact_data

from .const import BAUD_RATE, CONNECTION_SERIAL, DOMAIN

TO_REDACT = {"host", "serial_path", "serial_device"}


async def async_get_config_entry_diagnostics(hass, entry):
    connection = hass.data[DOMAIN][entry.entry_id]
    state = connection.state
    config = dict(entry.data)
    connection_type = config.get("connection_type")
    endpoint = (
        {"serial_device": config.get("serial_path")}
        if connection_type == CONNECTION_SERIAL
        else {"host": config.get("host"), "port": config.get("port")}
    )
    return {
        "config": async_redact_data(config, TO_REDACT),
        "connection": {
            "status": "connected" if state.available else "disconnected",
            "connection_type": connection_type,
            "endpoint": async_redact_data(endpoint, TO_REDACT),
            "serial_settings": {
                "baud_rate": BAUD_RATE,
                "data_bits": 8,
                "parity": "none",
                "stop_bits": 1,
                "flow_control": "none",
            },
            "tuner": connection.tuner,
            "connected_at": state.connected_at,
            "disconnected_at": state.disconnected_at,
            "last_response_at": state.last_response_at,
            "reconnect_count": state.reconnect_count,
            "last_error": state.last_connection_error,
        },
        "tuner_state": {
            "powered": state.powered,
            "frequency": state.frequency,
            "station_name": state.station_name,
            "radio_text": state.radio_text,
            "preset": state.preset,
            "preset_name": state.preset_name,
            "version": state.version,
        },
    }
