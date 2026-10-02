"""DataUpdateCoordinator for Ooma integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    EVENT_OOMA_INCOMING_CALL,
    EVENT_OOMA_MISSED_CALL,
    EVENT_OOMA_VOICEMAIL_RECEIVED,
)
from .ooma_client import OomaClient, OomaError, OomaAuthError

_LOGGER = logging.getLogger(__name__)


class OomaDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Class to manage fetching Ooma data and dispatching events."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: OomaClient,
        update_interval: timedelta,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.client = client
        self._last_call_id: Optional[str] = None
        self._last_voicemail_count: Optional[int] = None

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from Ooma Cloud."""
        try:
            call_logs = await self.client.get_call_logs(limit=10)
            voicemails = await self.client.get_voicemails()
            summary = await self.client.get_account_summary()

            data = {
                "call_logs": call_logs,
                "voicemails": voicemails,
                "account": summary,
            }

            self._check_for_events(data)
            return data

        except OomaAuthError as err:
            raise UpdateFailed(f"Authentication error with Ooma: {err}") from err
        except OomaError as err:
            raise UpdateFailed(f"Error communicating with Ooma: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error fetching Ooma data: {err}") from err

    def _check_for_events(self, data: Dict[str, Any]) -> None:
        """Inspect fetched data and fire Home Assistant events if new items detected."""
        call_logs = data.get("call_logs", [])
        if call_logs:
            latest_call = call_logs[0]
            call_id = latest_call.get("id")

            # Fire call event if a new call was detected
            if self._last_call_id is not None and call_id != self._last_call_id:
                event_type = (
                    EVENT_OOMA_MISSED_CALL
                    if latest_call.get("direction") == "missed"
                    else EVENT_OOMA_INCOMING_CALL
                )
                self.hass.bus.async_fire(
                    event_type,
                    {
                        "caller_name": latest_call.get("name"),
                        "caller_number": latest_call.get("number"),
                        "call_type": latest_call.get("direction"),
                        "duration": latest_call.get("duration"),
                        "timestamp": latest_call.get("timestamp"),
                    },
                )
                _LOGGER.debug("Fired Ooma call event: %s", latest_call)

            self._last_call_id = call_id

        # Check for new voicemail
        unread_vms = data.get("voicemails", {}).get("unread_count", 0)
        if self._last_voicemail_count is not None and unread_vms > self._last_voicemail_count:
            self.hass.bus.async_fire(
                EVENT_OOMA_VOICEMAIL_RECEIVED,
                {
                    "unread_count": unread_vms,
                    "new_count": unread_vms - self._last_voicemail_count,
                },
            )
            _LOGGER.debug("Fired Ooma voicemail event (unread: %s)", unread_vms)

        self._last_voicemail_count = unread_vms
