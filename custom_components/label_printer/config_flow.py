from __future__ import annotations

import logging

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _normalize_host(raw: str) -> str:
    """Accept 'host', 'http://host', 'host/' — return bare host.

    'localhost' is stored as 127.0.0.1: the add-on publishes its port on the
    host's IPv4 interfaces, and 'localhost' can resolve to ::1 first, which
    would fail even though the add-on is reachable.
    """
    host = raw.strip()
    for prefix in ("http://", "https://"):
        if host.startswith(prefix):
            host = host[len(prefix):]
    host = host.strip("/").strip()
    if host.lower() == "localhost":
        return "127.0.0.1"
    return host


async def _check_addon(host: str, port: int) -> str | None:
    """Probe the add-on's /health. Returns None on success, error key on failure."""
    url = f"http://{host}:{port}/health"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    return None
                _LOGGER.error(
                    "Label printer health check %s returned HTTP %s", url, resp.status
                )
                return "cannot_connect"
    except Exception as err:  # noqa: BLE001 — surfaced in the log on purpose
        _LOGGER.error(
            "Label printer health check failed for %s — %s: %s",
            url,
            type(err).__name__,
            err,
        )
        return "cannot_connect"


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
            error = await _check_addon(host, port)
            if error is None:
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Label Printer",
                    data={"host": host, "port": port},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    # The add-on publishes port 8765 on the host, so
                    # localhost works regardless of how the add-on was
                    # installed (local copy vs add-on repository — the
                    # latter gets a Supervisor-generated <hash>- hostname
                    # prefix that users shouldn't have to care about).
                    vol.Required("host", default="localhost"): str,
                    vol.Required("port", default=8765): int,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        """Change the add-on host/port without deleting the entry.

        Lets users switch between localhost (default; uses the port the
        add-on publishes on the host) and the add-on's internal hostname,
        or point at a print server running elsewhere.
        """
        entry = self._get_reconfigure_entry()
        errors = {}

        if user_input is not None:
            host = _normalize_host(user_input["host"])
            port = user_input["port"]
            error = await _check_addon(host, port)
            if error is None:
                return self.async_update_reload_and_abort(
                    entry,
                    data={"host": host, "port": port},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "host", default=entry.data.get("host", "localhost")
                    ): str,
                    vol.Required("port", default=entry.data.get("port", 8765)): int,
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
