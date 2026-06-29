from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN


class LabelPrinterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            url = f"http://{user_input['host']}:{user_input['port']}/health"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status == 200:
                            await self.async_set_unique_id(
                                f"{user_input['host']}:{user_input['port']}"
                            )
                            self._abort_if_unique_id_configured()
                            return self.async_create_entry(
                                title="Label Printer", data=user_input
                            )
                        errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("host", default="localhost"): str,
                    vol.Required("port", default=8765): int,
                }
            ),
            errors=errors,
        )
