"""Assist intent handler: PrintLabel."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
import homeassistant.helpers.config_validation as cv

from .api import apply_print_settings
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

INTENT_PRINT_LABEL = "PrintLabel"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Register intents — called by HA's intent component.

    A module named intent.py inside an integration is discovered as an
    'intent' integration platform, and HA requires this entry point.
    """
    intent.async_register(hass, PrintLabelIntentHandler(hass))


class PrintLabelIntentHandler(intent.IntentHandler):
    """Handle the PrintLabel intent from Assist."""

    intent_type = INTENT_PRINT_LABEL
    slot_schema = {
        vol.Required("text"): cv.string,
        vol.Optional("with_date"): vol.Coerce(bool),
        vol.Optional("with_time"): vol.Coerce(bool),
        vol.Optional("count"): vol.Coerce(int),
        vol.Optional("offset_unit"): cv.string,
        vol.Optional("copies"): vol.Coerce(int),
    }

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        slots = self.async_validate_slots(intent_obj.slots)

        def slot(name: str, default: Any = None) -> Any:
            return slots.get(name, {}).get("value", default)

        text: str = slot("text")
        with_date = bool(slot("with_date", False))
        with_time = bool(slot("with_time", False))
        count = slot("count")
        offset_unit = slot("offset_unit")
        copies = slot("copies")

        # Use the first configured entry (single-printer assumption)
        entries = self.hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise intent.IntentHandleError("No label printer is configured.")
        entry = entries[0]

        data = self.hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if not data:
            raise intent.IntentHandleError("Label printer is not available.")
        client = data["client"]

        payload: dict[str, Any] = {"text": text}
        speech_extra = ""

        if offset_unit and count:
            if offset_unit == "weeks":
                payload["date"] = {"offset_weeks": int(count)}
                speech_extra = f", dated {count} weeks from now"
            else:
                payload["date"] = {"offset_days": int(count)}
                speech_extra = f", dated {count} days from now"
        elif with_date:
            payload["date"] = {}
            speech_extra = " with today's date"

        if with_time:
            payload["time"] = True
            if not speech_extra:
                speech_extra = " with the time"

        if copies and int(copies) > 1:
            payload["copies"] = int(copies)

        payload = apply_print_settings(payload, entry.options)

        try:
            await client.print_label(payload)
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("Failed to print label %r: %s", text, err)
            raise intent.IntentHandleError(f"Could not reach the printer: {err}") from err

        response = intent_obj.create_response()
        if copies and int(copies) > 1:
            response.async_set_speech(
                f"Printing {copies} labels that say {text}{speech_extra}."
            )
        else:
            response.async_set_speech(f"Printing a label that says {text}{speech_extra}.")
        return response
