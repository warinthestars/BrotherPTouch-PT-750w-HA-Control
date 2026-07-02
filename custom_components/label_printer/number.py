"""Number entities: per-job print settings (font size, feed amount)."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import OPT_FEED_AMOUNT, OPT_FONT_SIZE, PRINT_SETTING_DEFAULTS
from .entity import device_info


@dataclass(frozen=True, kw_only=True)
class LabelPrinterNumberDescription(NumberEntityDescription):
    option_key: str = ""


NUMBERS: tuple[LabelPrinterNumberDescription, ...] = (
    LabelPrinterNumberDescription(
        key="font_size",
        translation_key="font_size",
        option_key=OPT_FONT_SIZE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.BOX,
        native_unit_of_measurement="pt",
        entity_category=EntityCategory.CONFIG,
    ),
    LabelPrinterNumberDescription(
        key="feed_amount",
        translation_key="feed_amount",
        option_key=OPT_FEED_AMOUNT,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(LabelPrinterNumber(entry, desc) for desc in NUMBERS)


class LabelPrinterNumber(NumberEntity):
    """A print setting stored in the config entry's options.

    Values are read at print time by apply_print_settings(), so no add-on
    call happens here — just persistence. Font size 0 means "use the add-on
    default" (auto-fit cap from the add-on configuration).
    """

    _attr_has_entity_name = True
    entity_description: LabelPrinterNumberDescription

    def __init__(self, entry: ConfigEntry, description: LabelPrinterNumberDescription) -> None:
        self._entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = device_info(entry)

    @property
    def native_value(self) -> float:
        return self._entry.options.get(
            self.entity_description.option_key,
            PRINT_SETTING_DEFAULTS[self.entity_description.option_key],
        )

    async def async_set_native_value(self, value: float) -> None:
        options = {**self._entry.options, self.entity_description.option_key: int(value)}
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        self.async_write_ha_state()
