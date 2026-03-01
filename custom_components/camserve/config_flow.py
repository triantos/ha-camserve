"""Config flow for Camserve integration."""

from __future__ import annotations

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN

DEFAULT_URL = "http://camserve.home.triantos.com:8080"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host", default=DEFAULT_URL): str,
    }
)


class CamserveConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Camserve."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input["host"].rstrip("/")

            # Prevent duplicate entries
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            # Validate connection
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{host}/api/system", timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        resp.raise_for_status()
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="Camserve",
                    data={"host": host},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
