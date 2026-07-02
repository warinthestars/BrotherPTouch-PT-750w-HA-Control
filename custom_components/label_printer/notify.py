"""Notify entity: prints the message as a label."""

from __future__ import annotations

import logging

import aiohttp
from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import LabelPrinterClient, apply_print_settings
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LabelPrinterNotifyEntity(data["client"], entry)])


class LabelPrinterNotifyEntity(NotifyEntity):
    _attr_has_entity_name = True
    _attr_name = None  # entity inherits the device name

    def __init__(self, client: LabelPrinterClient, entry: ConfigEntry) -> None:
        self._client = client
        self._entry = entry
        self._attr_unique_id = f"label_printer_{entry.entry_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Label Printer",
            manufacturer="Brother",
            model="PT-P750W",
        )

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Print the message as a label. A title, if given, becomes line 2."""
        # notify's message/title pair maps onto our two label lines:
        # message = big line 1, title (if given) = smaller line 2.
        payload: dict = {"text": message}
        if title:
            payload["line2"] = title
        payload = apply_print_settings(payload, self._entry.options)
        try:
            await self._client.print_label(payload)
            _LOGGER.debug("Printed label: %r", message)
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("Failed to print label %r: %s", message, err)
            raise
