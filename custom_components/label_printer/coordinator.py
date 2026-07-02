"""Status polling coordinator for the label-printer add-on."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LabelPrinterClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LabelPrinterCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls GET /status.

    The add-on answers HTTP 200 with {"online": false, ...} when the printer
    itself is unreachable, so an UpdateFailed here means the *add-on* is down.
    """

    def __init__(
        self, hass: HomeAssistant, client: LabelPrinterClient, scan_interval: int
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.status()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Add-on unreachable: {err}") from err
