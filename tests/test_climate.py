"""Climate entity behaviour tests for the TFIAC Local integration."""

import pytest

pytest.importorskip("pytest_homeassistant")

from unittest.mock import AsyncMock, patch  # noqa: E402

from homeassistant.components.climate import (  # noqa: E402
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import (  # noqa: E402
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    SERVICE_TURN_OFF,
)
from pytest_homeassistant.common import MockConfigEntry  # noqa: E402

from custom_components.tfiac_local.const import (  # noqa: E402
    CONF_DISPLAY_UNIT,
    CONF_PROTOCOL_UNIT,
    CONF_TIMEOUT,
    DOMAIN,
)

CLIENT_UPDATE = "custom_components.tfiac_local.tfiac_client.TfiacClient.async_update"
CLIENT_SET = "custom_components.tfiac_local.tfiac_client.TfiacClient.async_set_state"
CLIENT_OFF = "custom_components.tfiac_local.tfiac_client.TfiacClient.async_turn_off"

ENTITY = "climate.ac"

# Display unit C, protocol unit F.
DATA = {
    CONF_HOST: "192.0.2.10",
    CONF_NAME: "AC",
    CONF_DISPLAY_UNIT: "C",
    CONF_PROTOCOL_UNIT: "F",
    CONF_TIMEOUT: 5.0,
}


async def _setup(hass, make_status, **status_kwargs):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="tfiac_ac", data=DATA)
    entry.add_to_hass(hass)
    with patch(CLIENT_UPDATE, new=AsyncMock(return_value=make_status(**status_kwargs))):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_state_and_temperature_conversion(hass, make_status):
    """Protocol Fahrenheit values are exposed in the configured Celsius unit."""
    await _setup(
        hass, make_status, base_mode="cool", target_temp=72.0, current_temp=75.0
    )

    state = hass.states.get(ENTITY)
    assert state is not None
    assert state.state == HVACMode.COOL
    # 72 F -> 22.2 C, 75 F -> 23.9 C
    assert state.attributes[ATTR_TEMPERATURE] == pytest.approx(22.2, abs=0.1)
    assert state.attributes["current_temperature"] == pytest.approx(23.9, abs=0.1)


async def test_off_state_when_device_is_off(hass, make_status):
    """A powered-off device reports HVACMode.OFF."""
    await _setup(hass, make_status, is_on=False)
    assert hass.states.get(ENTITY).state == HVACMode.OFF


async def test_set_temperature_converts_to_protocol(hass, make_status):
    """Setting 24 C is converted to 75 F and sent to the device."""
    setmock = AsyncMock(return_value=make_status(target_temp=75.0))
    await _setup(hass, make_status)

    with patch(CLIENT_SET, new=setmock):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY, ATTR_TEMPERATURE: 24},
            blocking=True,
        )

    setmock.assert_awaited_once()
    kwargs = setmock.await_args.kwargs
    assert kwargs["target_temp"] == 75
    assert kwargs["power"] is True


async def test_set_hvac_mode_maps_to_protocol(hass, make_status):
    """Selecting cool sends the protocol 'cool' base mode."""
    setmock = AsyncMock(return_value=make_status(base_mode="cool"))
    await _setup(hass, make_status, base_mode="heat")

    with patch(CLIENT_SET, new=setmock):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY, ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )

    setmock.assert_awaited_once()
    assert setmock.await_args.kwargs["hvac_mode"] == "cool"


async def test_turn_off_calls_client(hass, make_status):
    """Turning the entity off calls the dedicated client method."""
    offmock = AsyncMock(return_value=make_status(is_on=False))
    await _setup(hass, make_status)

    with patch(CLIENT_OFF, new=offmock):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY},
            blocking=True,
        )

    offmock.assert_awaited_once()


async def test_no_deprecated_temperature_api_warning(hass, make_status, caplog):
    """The entity uses the native_* temperature API (HA 2026.11+)."""
    await _setup(hass, make_status)
    assert "native_temperature_unit" not in caplog.text
    assert "deprecated" not in caplog.text.lower()


@pytest.mark.parametrize(
    ("display_unit", "system", "requested", "expected_protocol", "shown_target"),
    [
        # Native C, HA metric: 24 C -> 75 F on the wire.
        ("C", "metric", 24, 75, 22.2),
        # Native C, HA imperial: 75 F -> 23.9 C native -> 75 F on the wire.
        ("C", "imperial", 75, 75, 72),
        # Native F, HA metric: 24 C -> 75.2 F native -> 75 F on the wire.
        ("F", "metric", 24, 75, 22.2),
        # Native F, HA imperial: 75 F passes straight through.
        ("F", "imperial", 75, 75, 72),
    ],
)
async def test_set_temperature_in_system_unit(
    hass, make_status, display_unit, system, requested, expected_protocol, shown_target
):
    """climate.set_temperature in the HA system unit reaches the device correctly."""
    from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

    hass.config.units = METRIC_SYSTEM if system == "metric" else US_CUSTOMARY_SYSTEM
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="tfiac_ac",
        data={**DATA, CONF_DISPLAY_UNIT: display_unit},
    )
    entry.add_to_hass(hass)
    with patch(CLIENT_UPDATE, new=AsyncMock(return_value=make_status(target_temp=72.0))):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # 72 F on the device is shown in the system unit.
    assert hass.states.get(ENTITY).attributes[ATTR_TEMPERATURE] == pytest.approx(
        shown_target, abs=0.1
    )

    setmock = AsyncMock(return_value=make_status(target_temp=75.0))
    with patch(CLIENT_SET, new=setmock):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY, ATTR_TEMPERATURE: requested},
            blocking=True,
        )
    assert setmock.await_args.kwargs["target_temp"] == expected_protocol
