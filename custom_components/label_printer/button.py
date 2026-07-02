"""Button entities: feed & cut, test print."""

from __future__ import annotations

import logging

import aiohttp
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import LabelPrinterClient
from .const import DOMAIN
from .entity import device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    client = hass.data[DOMAIN][entry.entry_id]["client"]
    async_add_entities(
        [
            FeedButton(client, entry),
            TestPrintButton(client, entry),
        ]
    )


class LabelPrinterButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, client: LabelPrinterClient, entry: ConfigEntry, key: str) -> None:
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = device_info(entry)


class FeedButton(LabelPrinterButton):
    def __init__(self, client, entry) -> None:
        super().__init__(client, entry, "feed")

    async def async_press(self) -> None:
        try:
            await self._client.feed()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HomeAssistantError(f"Feed failed: {err}") from err


class TestPrintButton(LabelPrinterButton):
    def __init__(self, client, entry) -> None:
        super().__init__(client, entry, "test_print")

    async def async_press(self) -> None:
        try:
            await self._client.test_print()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HomeAssistantError(f"Test print failed: {err}") from err
