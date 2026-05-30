"""Data update coordinator for the local TFIAC integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .tfiac_client import TfiacClient, TfiacStatus

_LOGGER = logging.getLogger(__name__)


class TfiacCoordinator(DataUpdateCoordinator[TfiacStatus]):
    """Coordinate polling of a single TFIAC device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: TfiacClient,
    ) -> None:
        interval = timedelta(
            seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{client.host}",
            update_interval=interval,
        )
        self.client = client

    async def _async_update_data(self) -> TfiacStatus:
        """Fetch the latest device status."""
        try:
            return await self.client.async_update(force=True)
        except Exception as err:  # noqa: BLE001 - surfaced as UpdateFailed
            raise UpdateFailed(
                f"Error communicating with TFIAC at {self.client.host}: {err}"
            ) from err
