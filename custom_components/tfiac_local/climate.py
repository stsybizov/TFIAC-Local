"""Home Assistant climate platform for local TFIAC devices."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.unit_conversion import TemperatureConverter

from . import TfiacConfigEntry
from .const import (
    CONF_DISPLAY_UNIT,
    CONF_PROTOCOL_UNIT,
    CONF_TIMEOUT,
    DEFAULT_DISPLAY_UNIT,
    DEFAULT_NAME,
    DEFAULT_PROTOCOL_UNIT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    FAN_MODES,
    SWING_MODES,
)
from .coordinator import TfiacCoordinator
from .tfiac_client import TfiacStatus, normalize_unit

_LOGGER = logging.getLogger(__name__)

PROTOCOL_TO_HVAC = {
    "cool": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "dehumi": HVACMode.DRY,
    "fan": HVACMode.FAN_ONLY,
    "selfFeel": HVACMode.AUTO,
}

HVAC_TO_PROTOCOL = {
    HVACMode.COOL: "cool",
    HVACMode.HEAT: "heat",
    HVACMode.DRY: "dehumi",
    HVACMode.FAN_ONLY: "fan",
    HVACMode.AUTO: "selfFeel",
}

# Legacy YAML schema, kept only to trigger an import into a config entry.
PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DISPLAY_UNIT, default=DEFAULT_DISPLAY_UNIT): vol.In(
            ["C", "F", "c", "f"]
        ),
        vol.Optional(CONF_PROTOCOL_UNIT, default=DEFAULT_PROTOCOL_UNIT): vol.In(
            ["C", "F", "c", "f"]
        ),
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(float),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import a legacy YAML configuration into a config entry."""
    _LOGGER.warning(
        "Configuring TFIAC Local via configuration.yaml is deprecated and will be "
        "imported into the UI. You can remove the YAML block after restart."
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=dict(config)
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TfiacConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the TFIAC climate entity from a config entry."""
    async_add_entities([TfiacClimateEntity(entry.runtime_data, entry)])


class TfiacClimateEntity(CoordinatorEntity[TfiacCoordinator], ClimateEntity):
    """Representation of a TFIAC air conditioner."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_fan_modes = FAN_MODES
    _attr_swing_modes = SWING_MODES
    _attr_target_temperature_step = 1.0
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self, coordinator: TfiacCoordinator, entry: TfiacConfigEntry
    ) -> None:
        super().__init__(coordinator)
        display_unit = normalize_unit(
            entry.data.get(CONF_DISPLAY_UNIT, DEFAULT_DISPLAY_UNIT)
        )
        self._display_unit = (
            UnitOfTemperature.CELSIUS
            if display_unit == "C"
            else UnitOfTemperature.FAHRENHEIT
        )
        self._protocol_unit = normalize_unit(
            entry.data.get(CONF_PROTOCOL_UNIT, DEFAULT_PROTOCOL_UNIT)
        )
        self._attr_unique_id = entry.unique_id or entry.entry_id
        self._attr_hvac_modes = [HVACMode.OFF, *HVAC_TO_PROTOCOL.keys()]
        self._attr_min_temp = self._convert_from_protocol(61)
        self._attr_max_temp = self._convert_from_protocol(88)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=entry.data.get(CONF_NAME, DEFAULT_NAME),
            manufacturer="TFIAC",
            model="Local UDP AC",
        )
        # Optimistic state applied right after a command. The device's status
        # response lags several seconds behind a command, so we display the
        # requested state immediately and let the next poll reconcile it.
        self._optimistic: TfiacStatus | None = None

    @property
    def _status(self) -> TfiacStatus | None:
        """Return the optimistic status if set, else the coordinator data."""
        return self._optimistic or self.coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Fresh data polled from the device supersedes any optimistic state."""
        self._optimistic = None
        super()._handle_coordinator_update()

    def _set_optimistic(self, status: TfiacStatus) -> None:
        """Display the requested state immediately after a command."""
        self._optimistic = status
        self.async_write_ha_state()

    @property
    def temperature_unit(self) -> str:
        """Return the unit used by Home Assistant."""
        return self._display_unit

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        if self._status is None:
            return None
        if not self._status.is_on:
            return HVACMode.OFF
        return PROTOCOL_TO_HVAC.get(self._status.base_mode, HVACMode.AUTO)

    @property
    def current_temperature(self) -> float | None:
        """Return the current measured temperature."""
        if self._status is None or self._status.current_temp is None:
            return None
        return round(self._convert_from_protocol(self._status.current_temp), 1)

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        if self._status is None:
            return None
        return round(self._convert_from_protocol(self._status.target_temp), 1)

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        return None if self._status is None else self._status.fan_mode

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        return None if self._status is None else self._status.swing_mode

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            return
        target = self._convert_to_protocol(float(kwargs[ATTR_TEMPERATURE]))
        await self._apply(target_temp=target, power=True)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return
        await self._apply(hvac_mode=HVAC_TO_PROTOCOL[hvac_mode], power=True)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        await self._apply(fan_mode=fan_mode, power=True)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode."""
        await self._apply(swing_mode=swing_mode)

    async def async_turn_on(self) -> None:
        """Turn the AC on."""
        self._set_optimistic(await self.coordinator.client.async_turn_on())

    async def async_turn_off(self) -> None:
        """Turn the AC off."""
        self._set_optimistic(await self.coordinator.client.async_turn_off())

    def _convert_from_protocol(self, value: float) -> float:
        """Convert a protocol temperature into the configured HA unit."""
        protocol_unit = (
            UnitOfTemperature.CELSIUS
            if self._protocol_unit == "C"
            else UnitOfTemperature.FAHRENHEIT
        )
        return TemperatureConverter.convert(value, protocol_unit, self._display_unit)

    def _convert_to_protocol(self, value: float) -> float:
        """Convert a Home Assistant temperature into the protocol unit."""
        protocol_unit = (
            UnitOfTemperature.CELSIUS
            if self._protocol_unit == "C"
            else UnitOfTemperature.FAHRENHEIT
        )
        converted = TemperatureConverter.convert(
            value, self._display_unit, protocol_unit
        )
        return round(converted)

    async def _apply(self, **kwargs: Any) -> None:
        """Send a state update and display the requested state optimistically."""
        self._set_optimistic(await self.coordinator.client.async_set_state(**kwargs))
