"""Label Printer integration: Brother PT-P750W via the label-printer add-on."""

from __future__ import annotations

import logging
from pathlib import Path

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import LabelPrinterClient
from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import LabelPrinterCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "button", "notify", "number", "sensor", "switch"]

MANAGED_MARKER = "# managed by label_printer"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = LabelPrinterClient(hass, entry.data[CONF_HOST], entry.data[CONF_PORT])

    # Gate setup on the ADD-ON being reachable — /config is answered from
    # memory and never touches the printer. The printer being off, asleep,
    # or unreachable must never block the integration from loading; that
    # state is surfaced through the Online/Problem entities instead.
    try:
        addon_config = await client.config()
    except (aiohttp.ClientError, TimeoutError) as err:
        raise ConfigEntryNotReady(f"Label printer add-on unreachable: {err}") from err
    _LOGGER.debug("Connected to add-on v%s: %s", addon_config.get("version"), addon_config)

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = LabelPrinterCoordinator(hass, client, scan_interval)
    # Non-blocking first refresh: a failure here marks entities unavailable
    # and the coordinator keeps retrying on its interval — setup proceeds.
    await coordinator.async_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "addon_config": addon_config,
        "entry": entry,
    }

    await _async_install_sentences(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # The PrintLabel intent handler is registered by HA's intent component,
    # which discovers intent.py as an integration platform and calls its
    # async_setup_intents() — no manual registration here.

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply option changes without a full reload.

    Print-setting options are read at print time, so only the poll interval
    needs to be pushed into the coordinator here. Reloading the entry instead
    would recreate every entity each time a switch is toggled.
    """
    from datetime import timedelta

    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if data:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        data["coordinator"].update_interval = timedelta(seconds=interval)


async def _async_install_sentences(hass: HomeAssistant) -> None:
    """Install the bundled Assist sentence file into config/custom_sentences/en/.

    HA does NOT load sentence files bundled inside custom integrations — only
    config/custom_sentences/<lang>/ is scanned. To keep setup zero-YAML we copy
    our file there and ask the conversation agent to reload.

    The copy is only overwritten while it still starts with the managed marker;
    if the user removes the marker to customize it, we leave it alone.
    """
    src = Path(__file__).parent / "sentences" / "en.yaml"
    dst_dir = Path(hass.config.path("custom_sentences", "en"))
    dst = dst_dir / "label_printer.yaml"

    def _sync() -> bool:
        src_text = src.read_text(encoding="utf-8")
        if dst.exists():
            dst_text = dst.read_text(encoding="utf-8")
            if not dst_text.startswith(MANAGED_MARKER):
                return False  # user customized; hands off
            if dst_text == src_text:
                return False
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst.write_text(src_text, encoding="utf-8")
        return True

    changed = await hass.async_add_executor_job(_sync)
    if changed:
        _LOGGER.info("Installed Assist sentences to %s", dst)
        if hass.services.has_service("conversation", "reload"):
            await hass.services.async_call("conversation", "reload", blocking=False)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
