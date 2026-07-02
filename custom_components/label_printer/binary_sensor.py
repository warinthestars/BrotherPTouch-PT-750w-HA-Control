"""Binary sensors: printer connectivity and error state."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LabelPrinterCoordinatorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [
            PrinterOnlineSensor(coordinator, entry),
            PrinterProblemSensor(coordinator, entry),
        ]
    )


class PrinterOnlineSensor(LabelPrinterCoordinatorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "online")

    @property
    def is_on(self) -> bool:
        return self.printer_online

    @property
    def extra_state_attributes(self) -> dict | None:
        if self.coordinator.data and not self.printer_online:
            return {"detail": self.coordinator.data.get("detail")}
        return None


class PrinterProblemSensor(LabelPrinterCoordinatorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "problem")

    @property
    def is_on(self) -> bool | None:
        if not self.printer_online:
            return None
        return bool(self.coordinator.data.get("errors"))

    @property
    def extra_state_attributes(self) -> dict | None:
        if self.printer_online:
            return {"errors": self.coordinator.data.get("errors", [])}
        return None
