"""Local TFIAC integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_TIMEOUT, DEFAULT_TIMEOUT
from .coordinator import TfiacCoordinator
from .tfiac_client import TfiacClient

PLATFORMS: list[Platform] = [Platform.CLIMATE]

type TfiacConfigEntry = ConfigEntry[TfiacCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TfiacConfigEntry) -> bool:
    """Set up TFIAC Local from a config entry."""
    client = TfiacClient(
        entry.data[CONF_HOST],
        timeout=entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
    )
    coordinator = TfiacCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TfiacConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: TfiacConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
