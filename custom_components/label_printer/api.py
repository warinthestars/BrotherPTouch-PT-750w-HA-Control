"""HTTP client for the label-printer add-on."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    OPT_AUTOCUT,
    OPT_CHAIN_PRINT,
    OPT_FEED_AMOUNT,
    OPT_FONT_SIZE,
    OPT_HALF_CUT,
    OPT_HIGH_DPI,
    OPT_MIRROR,
    PRINT_SETTING_DEFAULTS,
)

# Print jobs can legitimately take a while (multi-copy, printer wake-up);
# the add-on caps printer I/O at 90 s, so allow a bit more than that.
PRINT_TIMEOUT = aiohttp.ClientTimeout(total=120)
# Status/config must fail fast — the coordinator's first refresh runs during
# config entry setup, and a slow answer here stalls HA's setup of the entry.
STATUS_TIMEOUT = aiohttp.ClientTimeout(total=20)


def apply_print_settings(payload: dict[str, Any], options: Mapping[str, Any]) -> dict[str, Any]:
    """Merge entity-configured print settings into a /print payload.

    Explicit keys already in the payload win over entity settings.
    """
    settings: dict[str, Any] = {}
    font_size = options.get(OPT_FONT_SIZE, PRINT_SETTING_DEFAULTS[OPT_FONT_SIZE])
    if font_size:
        settings["font_size"] = font_size
    settings["autocut"] = bool(options.get(OPT_AUTOCUT, PRINT_SETTING_DEFAULTS[OPT_AUTOCUT]))
    settings["mirror"] = bool(options.get(OPT_MIRROR, PRINT_SETTING_DEFAULTS[OPT_MIRROR]))
    settings["half_cut"] = bool(options.get(OPT_HALF_CUT, PRINT_SETTING_DEFAULTS[OPT_HALF_CUT]))
    settings["high_dpi"] = bool(options.get(OPT_HIGH_DPI, PRINT_SETTING_DEFAULTS[OPT_HIGH_DPI]))
    settings["chain_print"] = bool(
        options.get(OPT_CHAIN_PRINT, PRINT_SETTING_DEFAULTS[OPT_CHAIN_PRINT])
    )
    settings["feed_amount"] = int(
        options.get(OPT_FEED_AMOUNT, PRINT_SETTING_DEFAULTS[OPT_FEED_AMOUNT])
    )
    return {**settings, **payload}


class LabelPrinterClient:
    """Thin async client for the add-on's HTTP API."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        self._session = async_get_clientsession(hass)
        self.base_url = f"http://{host}:{port}"

    async def print_label(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._session.post(
            f"{self.base_url}/print", json=payload, timeout=PRINT_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def status(self) -> dict[str, Any]:
        async with self._session.get(
            f"{self.base_url}/status", timeout=STATUS_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def config(self) -> dict[str, Any]:
        async with self._session.get(
            f"{self.base_url}/config", timeout=STATUS_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def feed(self) -> None:
        async with self._session.post(f"{self.base_url}/feed", timeout=PRINT_TIMEOUT) as resp:
            resp.raise_for_status()

    async def test_print(self) -> None:
        async with self._session.post(f"{self.base_url}/test", timeout=PRINT_TIMEOUT) as resp:
            resp.raise_for_status()
