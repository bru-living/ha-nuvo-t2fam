"""Config flow for NuVo NV-T2FAM."""

import asyncio
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_CONNECTION_TYPE, CONF_SERIAL_PATH, CONF_TUNER, CONNECTION_SERIAL, CONNECTION_TCP, DEFAULT_PORT, DOMAIN
from .protocol import InvalidDeviceError, NuvoConnection

_LOGGER = logging.getLogger(__name__)


class NuvoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            return await self.async_step_connection(user_input)
        return self.async_show_form(step_id="user", data_schema=vol.Schema({vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_TCP): vol.In([CONNECTION_TCP, CONNECTION_SERIAL])}))

    async def async_step_connection(self, user_input=None) -> FlowResult:
        connection_type = self.context.get("connection_type")
        if user_input and CONF_CONNECTION_TYPE in user_input:
            connection_type = user_input[CONF_CONNECTION_TYPE]
            self.context["connection_type"] = connection_type
            user_input = None
        errors = {}
        if user_input is not None:
            data = {CONF_CONNECTION_TYPE: connection_type, **user_input}
            connection = NuvoConnection(data, data[CONF_TUNER], lambda: None)
            try:
                await connection.probe()
            except InvalidDeviceError:
                errors["base"] = "wrong_device"
            except (OSError, asyncio.TimeoutError, asyncio.IncompleteReadError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error while connecting to the NuVo tuner")
                errors["base"] = "unknown"
            else:
                endpoint = data.get(CONF_HOST, data.get(CONF_SERIAL_PATH))
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"NV-T2FAM tuner {data[CONF_TUNER]}", data=data)
        common = {vol.Required(CONF_TUNER, default="A"): vol.In(["A", "B"])}
        if connection_type == CONNECTION_SERIAL:
            schema = {vol.Required(CONF_SERIAL_PATH): str, **common}
        else:
            schema = {vol.Required(CONF_HOST): str, vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)), **common}
        return self.async_show_form(step_id="connection", data_schema=vol.Schema(schema), errors=errors)

    async def async_step_reconfigure(self, user_input=None) -> FlowResult:
        """Allow the endpoint and selected tuner to be changed in the UI."""
        entry = self._get_reconfigure_entry()
        current = dict(entry.data)
        connection_type = current[CONF_CONNECTION_TYPE]
        errors = {}
        if user_input is not None:
            data = {CONF_CONNECTION_TYPE: connection_type, **user_input}
            connection = NuvoConnection(data, data[CONF_TUNER], lambda: None)
            try:
                await connection.probe()
            except InvalidDeviceError:
                errors["base"] = "wrong_device"
            except (OSError, asyncio.TimeoutError, asyncio.IncompleteReadError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error while reconfiguring the NuVo tuner")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=data)

        common = {
            vol.Required(CONF_TUNER, default=current[CONF_TUNER]): vol.In(["A", "B"])
        }
        if connection_type == CONNECTION_SERIAL:
            schema = {
                vol.Required(CONF_SERIAL_PATH, default=current[CONF_SERIAL_PATH]): str,
                **common,
            }
        else:
            schema = {
                vol.Required(CONF_HOST, default=current[CONF_HOST]): str,
                vol.Required(CONF_PORT, default=current[CONF_PORT]): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                **common,
            }
        return self.async_show_form(
            step_id="reconfigure", data_schema=vol.Schema(schema), errors=errors
        )
