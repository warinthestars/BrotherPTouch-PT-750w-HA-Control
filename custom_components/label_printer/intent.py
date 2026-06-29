from __future__ import annotations

import logging

import aiohttp
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

INTENT_PRINT_LABEL = "PrintLabel"


class PrintLabelIntentHandler(intent.IntentHandler):
    """Handle the PrintLabel intent from Assist."""

    intent_type = INTENT_PRINT_LABEL
    slot_schema = {vol.Required("text"): cv.string}

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        text = intent_obj.slots["text"]["value"]

        # Use the first configured entry (single-printer assumption)
        entries = self.hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise intent.IntentHandleError("No label printer is configured.")

        data = self.hass.data.get(DOMAIN, {}).get(entries[0].entry_id)
        if not data:
            raise intent.IntentHandleError("Label printer is not available.")

        url = f"http://{data['host']}:{data['port']}/print"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={"text": text},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    resp.raise_for_status()
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to print label %r: %s", text, err)
            raise intent.IntentHandleError(f"Could not reach the printer: {err}") from err

        response = intent_obj.create_response()
        response.async_set_speech(f"Printing a label that says {text}.")
        return response
