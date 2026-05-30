"""Setup/unload and options tests for the TFIAC Local integration."""

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from unittest.mock import AsyncMock, patch  # noqa: E402

from homeassistant.config_entries import ConfigEntryState  # noqa: E402
from homeassistant.const import (  # noqa: E402
    CONF_HOST,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
)
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.tfiac_local.const import (  # noqa: E402
    CONF_DISPLAY_UNIT,
    CONF_PROTOCOL_UNIT,
    CONF_TIMEOUT,
    DOMAIN,
)

CLIENT_UPDATE = "custom_components.tfiac_local.tfiac_client.TfiacClient.async_update"

DATA = {
    CONF_HOST: "192.0.2.10",
    CONF_NAME: "AC",
    CONF_DISPLAY_UNIT: "C",
    CONF_PROTOCOL_UNIT: "F",
    CONF_TIMEOUT: 5.0,
}


def _entry() -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, unique_id="tfiac_ac", data=DATA)


async def test_setup_and_unload(hass, make_status):
    """The entry loads, creates the entity, and unloads cleanly."""
    entry = _entry()
    entry.add_to_hass(hass)

    with patch(CLIENT_UPDATE, new=AsyncMock(return_value=make_status())):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("climate.ac") is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_on_connection_error(hass):
    """A device that cannot be reached puts the entry into retry state."""
    entry = _entry()
    entry.add_to_hass(hass)

    with patch(CLIENT_UPDATE, new=AsyncMock(side_effect=OSError("down"))):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_options_flow_updates_scan_interval(hass, make_status):
    """Changing the polling interval via options reloads the entry."""
    entry = _entry()
    entry.add_to_hass(hass)

    with patch(CLIENT_UPDATE, new=AsyncMock(return_value=make_status())):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_SCAN_INTERVAL: 60}
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 60
