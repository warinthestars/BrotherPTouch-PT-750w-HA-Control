from __future__ import annotations

import logging

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _normalize_host(raw: str) -> str:
    """Accept 'host', 'http://host', 'host/' — return bare host."""
    host = raw.strip()
    for prefix in ("http://", "https://"):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return host.strip("/").strip()


class LabelPrinterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return LabelPrinterOptionsFlow()

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            host = _normalize_host(user_input["host"])
            port = user_input["port"]
            url = f"http://{host}:{port}/health"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status == 200:
                            await self.async_set_unique_id(f"{host}:{port}")
                            self._abort_if_unique_id_configured()
                            return self.async_create_entry(
                                title="Label Printer",
                                data={"host": host, "port": port},
                            )
                        _LOGGER.error(
                            "Label printer health check %s returned HTTP %s",
                            url,
                            resp.status,
                        )
                        errors["base"] = "cannot_connect"
            except AbortFlow:
                raise
            except Exception as err:  # noqa: BLE001 — surfaced in the log on purpose
                _LOGGER.error(
                    "Label printer health check failed for %s — %s: %s",
                    url,
                    type(err).__name__,
                    err,
                )
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("host", default="local-label-printer"): str,
                    vol.Required("port", default=8765): int,
                }
            ),
            errors=errors,
        )


class LabelPrinterOptionsFlow(config_entries.OptionsFlow):
    """Options: status poll interval.

    Print settings (font size, autocut, ...) are managed through the
    integration's number/switch entities, not this form — but they live in
    the same options dict, so this form must preserve them on save.
    """

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, **user_input},
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                }
            ),
        )
