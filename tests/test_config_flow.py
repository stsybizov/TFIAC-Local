"""Tests for the TFIAC Local config flow.

Requires pytest-homeassistant-custom-component (see requirements_test.txt).
Run on a Python version supported by Home Assistant (3.12/3.13).
"""

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from unittest.mock import AsyncMock, patch  # noqa: E402

from homeassistant import config_entries  # noqa: E402
from homeassistant.const import CONF_HOST, CONF_NAME  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.tfiac_local.const import (  # noqa: E402
    CONF_DISPLAY_UNIT,
    CONF_PROTOCOL_UNIT,
    CONF_TIMEOUT,
    DOMAIN,
)

CLIENT_UPDATE = "custom_components.tfiac_local.tfiac_client.TfiacClient.async_update"

USER_INPUT = {
    CONF_HOST: "192.0.2.10",
    CONF_NAME: "AC",
    CONF_DISPLAY_UNIT: "C",
    CONF_PROTOCOL_UNIT: "F",
    CONF_TIMEOUT: 5.0,
}


async def test_user_flow_creates_entry(hass, make_status):
    """A valid user flow creates an entry with a name-derived unique id."""
    with patch(CLIENT_UPDATE, new=AsyncMock(return_value=make_status(name="Living Room"))):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["result"].unique_id == "tfiac_living_room"
    assert result2["data"][CONF_HOST] == "192.0.2.10"


async def test_user_flow_cannot_connect(hass):
    """An unreachable device surfaces a cannot_connect error."""
    with patch(CLIENT_UPDATE, new=AsyncMock(side_effect=OSError("boom"))):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_duplicate_aborts(hass, make_status):
    """A device already configured aborts with already_configured."""
    MockConfigEntry(
        domain=DOMAIN, unique_id="tfiac_living_room", data=USER_INPUT
    ).add_to_hass(hass)

    with patch(CLIENT_UPDATE, new=AsyncMock(return_value=make_status(name="Living Room"))):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_import_flow_creates_entry(hass, make_status):
    """A YAML import creates an entry."""
    with patch(CLIENT_UPDATE, new=AsyncMock(return_value=make_status(name="Bedroom"))):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_HOST: "192.0.2.20", CONF_NAME: "Bedroom AC"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "tfiac_bedroom"
