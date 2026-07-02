"""Switch entities: per-job print settings (autocut, mirror, half-cut, ...)."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    OPT_AUTOCUT,
    OPT_CHAIN_PRINT,
    OPT_HALF_CUT,
    OPT_HIGH_DPI,
    OPT_MIRROR,
    PRINT_SETTING_DEFAULTS,
)
from .entity import device_info


@dataclass(frozen=True, kw_only=True)
class LabelPrinterSwitchDescription(SwitchEntityDescription):
    option_key: str = ""


SWITCHES: tuple[LabelPrinterSwitchDescription, ...] = (
    LabelPrinterSwitchDescription(
        key="autocut",
        translation_key="autocut",
        option_key=OPT_AUTOCUT,
        entity_category=EntityCategory.CONFIG,
    ),
    LabelPrinterSwitchDescription(
        key="mirror",
        translation_key="mirror",
        option_key=OPT_MIRROR,
        entity_category=EntityCategory.CONFIG,
    ),
    LabelPrinterSwitchDescription(
        key="half_cut",
        translation_key="half_cut",
        option_key=OPT_HALF_CUT,
        entity_category=EntityCategory.CONFIG,
    ),
    LabelPrinterSwitchDescription(
        key="chain_print",
        translation_key="chain_print",
        option_key=OPT_CHAIN_PRINT,
        entity_category=EntityCategory.CONFIG,
    ),
    LabelPrinterSwitchDescription(
        key="high_dpi",
        translation_key="high_dpi",
        option_key=OPT_HIGH_DPI,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(LabelPrinterSwitch(entry, desc) for desc in SWITCHES)


class LabelPrinterSwitch(SwitchEntity):
    """A boolean print setting stored in the config entry's options."""

    _attr_has_entity_name = True
    entity_description: LabelPrinterSwitchDescription

    def __init__(self, entry: ConfigEntry, description: LabelPrinterSwitchDescription) -> None:
        self._entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = device_info(entry)

    @property
    def is_on(self) -> bool:
        return bool(
            self._entry.options.get(
                self.entity_description.option_key,
                PRINT_SETTING_DEFAULTS[self.entity_description.option_key],
            )
        )

    async def _set(self, value: bool) -> None:
        options = {**self._entry.options, self.entity_description.option_key: value}
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)
