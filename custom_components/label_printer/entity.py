"""Shared entity bases for the Label Printer integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LabelPrinterCoordinator


def device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Label Printer",
        manufacturer="Brother",
        model="PT-P750W",
    )


class LabelPrinterCoordinatorEntity(CoordinatorEntity[LabelPrinterCoordinator]):
    """Base for entities backed by the /status coordinator."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: LabelPrinterCoordinator, entry: ConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = device_info(entry)

    @property
    def printer_online(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.get("online"))
