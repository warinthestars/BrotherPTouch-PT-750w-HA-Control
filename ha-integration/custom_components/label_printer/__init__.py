from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent as intent_helper

from .const import DOMAIN
from .intent import PrintLabelIntentHandler
PLATFORMS = ["notify"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Registering here means Assist works the moment the integration is set up.
    # async_register replaces any previous handler with the same intent_type,
    # so multiple config entries (future multi-printer support) won't stack up.
    intent_helper.async_register(hass, PrintLabelIntentHandler(hass))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True
