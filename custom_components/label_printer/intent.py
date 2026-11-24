"""Assist intent handler: PrintLabel."""

from __future__ import annotations

import logging
import re
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

# ── fuzzy clean-up of the dictated {text} wildcard ─────────────────────────
# The sentence file accepts many phrasings, but a wildcard can still swallow
# trailing modifiers ("soup with today's date please") or carry STT
# punctuation. normalize_label_text() strips that noise and converts a
# swallowed date/time phrase back into the date/time options.
_DATE = r"(?:(?:today'?s|todays|today|the|the\s+current|current)\s+)?date"
_TIME = r"(?:the\s+)?(?:current\s+)?time"
_DATETIME = rf"(?:{_DATE}\s+and\s+{_TIME}|{_TIME}\s+and\s+{_DATE}|{_DATE}\s+time)"
# Trailing modifier, e.g. "… with the date", "… and today's date and time".
# Bare "and date" is NOT accepted (could be real text, e.g. "figs and date");
# "and" needs an article/"today's" in front of date.
_TRAILING = re.compile(
    rf"[\s,;]+(?:"
    rf"(?:with|plus|including|showing)\s+(?P<dt1>{_DATETIME}|{_DATE}|{_TIME})"
    rf"|and\s+(?P<dt2>{_DATETIME}|(?:today'?s|todays|the|the\s+current)\s+date|the\s+time)"
    rf")\s*$",
    re.IGNORECASE,
)
# Text that is *only* a date phrase ("print the date on a label" can also
# match the plain-text pattern with text="the date").
_ONLY = re.compile(rf"^\s*(?P<dt>{_DATETIME}|{_DATE})\s*$", re.IGNORECASE)
_FILLER_TAIL = re.compile(
    r"[\s,;]+(?:please|thanks|thank\s+you|on\s+it|okay|ok)\s*$", re.IGNORECASE
)
_FILLER_HEAD = re.compile(r"^\s*(?:please|uh|um)[\s,]+", re.IGNORECASE)
_QUOTES = "\"'“”‘’`"


def normalize_label_text(text: str | None) -> tuple[str, bool, bool]:
    """Clean dictated label text.

    Returns (text, found_date, found_time). ``text`` may come back empty when
    the whole utterance was a date/time request.
    """
    if not text:
        return "", False, False
    t = " ".join(str(text).split())
    found_date = found_time = False

    for _ in range(4):  # peel layered tails: "soup with the date on it please."
        before = t
        t = t.rstrip(" .!?,;:")
        t = t.strip(_QUOTES).strip()
        t = _FILLER_HEAD.sub("", t)
        t = _FILLER_TAIL.sub("", t)
        m = _TRAILING.search(t)
        if m:
            phrase = (m.group("dt1") or m.group("dt2") or "").lower()
            if "date" in phrase:
                found_date = True
            if "time" in phrase:
                found_time = True
            t = t[: m.start()]
        if t == before:
            break

    m = _ONLY.match(t)
    if m:
        found_date = True
        if "time" in m.group("dt").lower():
            found_time = True
        t = ""

    return t.strip(" .!?,;:"), found_date, found_time



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
        vol.Optional("text"): cv.string,
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

        text, found_date, found_time = normalize_label_text(slot("text"))
        with_date = bool(slot("with_date", False)) or found_date
        with_time = bool(slot("with_time", False)) or found_time
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

        if not text and not (with_date or with_time or (offset_unit and count)):
            raise intent.IntentHandleError("What should the label say?")

        # Empty text + date/time prints a single-line date label
        # (needs add-on 1.2.0+).
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
            speech_extra = (
                " with the date and time" if with_time else " with today's date"
            )

        if with_time:
            payload["time"] = True
            if not speech_extra:
                speech_extra = " with the time"

        if copies and int(copies) > 1:
            payload["copies"] = int(copies)

        payload = apply_print_settings(payload, entry.options)

        try:
            await client.print_label(payload)
        except aiohttp.ClientResponseError as err:
            _LOGGER.error("Add-on rejected label %r: %s", payload, err)
            if err.status == 400 and not text:
                raise intent.IntentHandleError(
                    "The label printer add-on is too old to print date-only "
                    "labels. Update the add-on to 1.2.0 or later."
                ) from err
            raise intent.IntentHandleError(f"The printer add-on returned an error: {err.message}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("Failed to print label %r: %s", text, err)
            raise intent.IntentHandleError(f"Could not reach the printer: {err}") from err

        response = intent_obj.create_response()
        n = int(copies) if copies else 1
        what = f"{n} labels" if n > 1 else "a label"
        if text:
            response.async_set_speech(f"Printing {what} that say{'' if n > 1 else 's'} {text}{speech_extra}.")
        else:
            response.async_set_speech(f"Printing {what}{speech_extra}.")
        return response
