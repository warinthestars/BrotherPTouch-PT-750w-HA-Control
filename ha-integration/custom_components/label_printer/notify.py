from __future__ import annotations

import logging

import aiohttp
from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [LabelPrinterNotifyEntity(data["host"], data["port"], entry.entry_id)]
    )


class LabelPrinterNotifyEntity(NotifyEntity):
    _attr_has_entity_name = True
    _attr_name = None  # entity inherits the device name

    def __init__(self, host: str, port: int, entry_id: str) -> None:
        self._url = f"http://{host}:{port}/print"
        self._attr_unique_id = f"label_printer_{entry_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Label Printer",
            manufacturer="Brother",
            model="PT-P750W",
        )

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send message to the label printer (prints the message as a label)."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._url,
                    json={"text": message},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    resp.raise_for_status()
                    _LOGGER.debug("Printed label: %r", message)
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to print label %r: %s", message, err)
            raise
