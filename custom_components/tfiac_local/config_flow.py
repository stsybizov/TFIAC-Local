"""Config flow for the local TFIAC integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.util import slugify

from .const import (
    CONF_DISPLAY_UNIT,
    CONF_PROTOCOL_UNIT,
    CONF_TIMEOUT,
    DEFAULT_DISPLAY_UNIT,
    DEFAULT_NAME,
    DEFAULT_PROTOCOL_UNIT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .tfiac_client import TfiacClient, TfiacStatus, normalize_unit

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DISPLAY_UNIT, default=DEFAULT_DISPLAY_UNIT): vol.In(["C", "F"]),
        vol.Optional(CONF_PROTOCOL_UNIT, default=DEFAULT_PROTOCOL_UNIT): vol.In(["C", "F"]),
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(float),
    }
)


def _unique_id_from(status: TfiacStatus, host: str) -> str:
    """Build a stable unique id from the device name, falling back to host."""
    name = (status.device_name or "").strip()
    if name and name != DEFAULT_NAME:
        return f"tfiac_{slugify(name)}"
    return f"tfiac_{slugify(host)}"


async def _async_probe(host: str, timeout: float) -> TfiacStatus:
    """Connect to the device once to validate and read its identity."""
    client = TfiacClient(host, timeout=timeout)
    return await client.async_update(force=True)


class TfiacConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TFIAC Local."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step from the UI."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                normalize_unit(user_input[CONF_DISPLAY_UNIT])
                normalize_unit(user_input[CONF_PROTOCOL_UNIT])
            except ValueError:
                errors["base"] = "invalid_unit"
            else:
                try:
                    status = await _async_probe(
                        user_input[CONF_HOST], user_input[CONF_TIMEOUT]
                    )
                except Exception:  # noqa: BLE001 - any failure means unreachable
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(
                        _unique_id_from(status, user_input[CONF_HOST])
                    )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=user_input[CONF_NAME], data=user_input
                    )

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Import a configuration from configuration.yaml."""
        host = import_data[CONF_HOST]
        timeout = float(import_data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT))
        try:
            status = await _async_probe(host, timeout)
        except Exception:  # noqa: BLE001
            _LOGGER.warning("YAML import for TFIAC %s failed: device unreachable", host)
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(_unique_id_from(status, host))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=import_data.get(CONF_NAME, DEFAULT_NAME),
            data={
                CONF_HOST: host,
                CONF_NAME: import_data.get(CONF_NAME, DEFAULT_NAME),
                CONF_DISPLAY_UNIT: normalize_unit(
                    import_data.get(CONF_DISPLAY_UNIT, DEFAULT_DISPLAY_UNIT)
                ),
                CONF_PROTOCOL_UNIT: normalize_unit(
                    import_data.get(CONF_PROTOCOL_UNIT, DEFAULT_PROTOCOL_UNIT)
                ),
                CONF_TIMEOUT: timeout,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return TfiacOptionsFlow()


class TfiacOptionsFlow(OptionsFlow):
    """Handle TFIAC Local options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=3600)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
