"""Sensors: printer status/diagnostics read from the PT-P750W."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LabelPrinterCoordinatorEntity


@dataclass(frozen=True, kw_only=True)
class LabelPrinterSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any] = lambda data: None


def _errors_text(data: dict[str, Any]) -> str | None:
    errs = data.get("errors") or []
    return ", ".join(errs) if errs else "OK"


SENSORS: tuple[LabelPrinterSensorDescription, ...] = (
    LabelPrinterSensorDescription(
        key="tape_width",
        translation_key="tape_width",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        value_fn=lambda d: d.get("tape_width_mm") or None,
    ),
    LabelPrinterSensorDescription(
        key="tape_color",
        translation_key="tape_color",
        value_fn=lambda d: d.get("tape_color"),
    ),
    LabelPrinterSensorDescription(
        key="font_color",
        translation_key="font_color",
        value_fn=lambda d: d.get("font_color"),
    ),
    LabelPrinterSensorDescription(
        key="media_type",
        translation_key="media_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("media_type"),
    ),
    LabelPrinterSensorDescription(
        key="battery",
        translation_key="battery",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("battery"),
    ),
    LabelPrinterSensorDescription(
        key="model",
        translation_key="model",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("model"),
    ),
    LabelPrinterSensorDescription(
        key="error",
        translation_key="error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_errors_text,
    ),
    LabelPrinterSensorDescription(
        key="phase",
        translation_key="phase",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("phase"),
    ),
    LabelPrinterSensorDescription(
        key="status_type",
        translation_key="status_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("status_type"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        LabelPrinterSensor(coordinator, entry, desc) for desc in SENSORS
    )


class LabelPrinterSensor(LabelPrinterCoordinatorEntity, SensorEntity):
    entity_description: LabelPrinterSensorDescription

    def __init__(self, coordinator, entry, description) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        if not self.printer_online:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
