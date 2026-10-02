"""Config flow for Ooma integration."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)
from .ooma_client import OomaClient, OomaAuthError, OomaConnectionError, OomaError, clean_username

_LOGGER = logging.getLogger(__name__)


class OomaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ooma."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial user step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            raw_username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            normalized_username = clean_username(raw_username)

            # Unique ID by normalized username/phone
            await self.async_set_unique_id(normalized_username.lower())
            self._abort_if_unique_id_configured()

            client = OomaClient(normalized_username, password)

            try:
                await client.login()
            except OomaAuthError:
                errors["base"] = "invalid_auth"
            except OomaConnectionError:
                errors["base"] = "cannot_connect"
            except OomaError:
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected exception during Ooma auth validation")
                errors["base"] = "unknown"
            finally:
                await client.close()

            if not errors:
                return self.async_create_entry(
                    title=f"Ooma ({normalized_username})",
                    data={
                        CONF_USERNAME: normalized_username,
                        CONF_PASSWORD: password,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OomaOptionsFlowHandler(config_entry)


class OomaOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Ooma."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=current_interval,
                ): vol.All(vol.Coerce(int), vol.Clamp(min=15, max=300)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
