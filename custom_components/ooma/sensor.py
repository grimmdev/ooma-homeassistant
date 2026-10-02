"""Sensor platform for Ooma integration."""

from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OomaDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ooma sensor entities based on a config entry."""
    coordinator: OomaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    username = entry.data.get("username", "account")
    device_info = DeviceInfo(
        identifiers={(DOMAIN, username)},
        name=f"Ooma ({username})",
        manufacturer="Ooma",
        model="Telo / Cloud Account",
    )

    entities = [
        OomaVoicemailSensor(coordinator, entry, device_info),
        OomaLastCallerSensor(coordinator, entry, device_info),
        OomaMissedCallsSensor(coordinator, entry, device_info),
        OomaStatusSensor(coordinator, entry, device_info),
    ]

    async_add_entities(entities)


class OomaBaseSensor(CoordinatorEntity[OomaDataUpdateCoordinator], SensorEntity):
    """Base sensor for Ooma entities."""

    def __init__(
        self,
        coordinator: OomaDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: DeviceInfo,
        key: str,
        name: str,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_name = f"Ooma {name}"
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = device_info


class OomaVoicemailSensor(OomaBaseSensor):
    """Sensor representing unread voicemail count."""

    def __init__(
        self, coordinator: OomaDataUpdateCoordinator, entry: ConfigEntry, device_info: DeviceInfo
    ) -> None:
        super().__init__(coordinator, entry, device_info, "voicemails", "Voicemails")
        self._attr_icon = "mdi:voicemail"

    @property
    def native_value(self) -> Optional[int]:
        """Return the unread voicemail count."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("voicemails", {}).get("unread_count", 0)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra voicemail attributes."""
        if not self.coordinator.data:
            return {}
        vm_data = self.coordinator.data.get("voicemails", {})
        return {
            "unread_count": vm_data.get("unread_count", 0),
            "total_count": vm_data.get("total_count", 0),
        }


class OomaLastCallerSensor(OomaBaseSensor):
    """Sensor showing the most recent caller."""

    def __init__(
        self, coordinator: OomaDataUpdateCoordinator, entry: ConfigEntry, device_info: DeviceInfo
    ) -> None:
        super().__init__(coordinator, entry, device_info, "last_caller", "Last Caller")
        self._attr_icon = "mdi:phone-incoming"

    @property
    def native_value(self) -> Optional[str]:
        """Return the name or number of the last caller."""
        if not self.coordinator.data:
            return None
        call_logs = self.coordinator.data.get("call_logs", [])
        if not call_logs:
            return "No Calls"
        latest = call_logs[0]
        return latest.get("name") or latest.get("number") or "Unknown"

    @property
    def icon(self) -> str:
        """Dynamic icon based on call direction."""
        if self.coordinator.data:
            call_logs = self.coordinator.data.get("call_logs", [])
            if call_logs:
                direction = call_logs[0].get("direction")
                if direction == "missed":
                    return "mdi:phone-missed"
                elif direction == "outbound":
                    return "mdi:phone-outgoing"
        return "mdi:phone-incoming"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return detailed attributes for the last call."""
        if not self.coordinator.data:
            return {}
        call_logs = self.coordinator.data.get("call_logs", [])
        if not call_logs:
            return {}
        latest = call_logs[0]
        return {
            "caller_name": latest.get("name"),
            "caller_number": latest.get("number"),
            "call_type": latest.get("direction"),
            "duration": latest.get("duration"),
            "timestamp": latest.get("timestamp"),
            "recent_calls": call_logs[:5],
        }


class OomaMissedCallsSensor(OomaBaseSensor):
    """Sensor tracking the count of recent missed calls."""

    def __init__(
        self, coordinator: OomaDataUpdateCoordinator, entry: ConfigEntry, device_info: DeviceInfo
    ) -> None:
        super().__init__(coordinator, entry, device_info, "missed_calls", "Missed Calls")
        self._attr_icon = "mdi:phone-missed"

    @property
    def native_value(self) -> Optional[int]:
        """Return count of recent missed calls."""
        if not self.coordinator.data:
            return None
        call_logs = self.coordinator.data.get("call_logs", [])
        return sum(1 for call in call_logs if call.get("direction") == "missed")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        if not self.coordinator.data:
            return {}
        call_logs = self.coordinator.data.get("call_logs", [])
        missed = [c for c in call_logs if c.get("direction") == "missed"]
        return {"missed_calls": missed}


class OomaStatusSensor(OomaBaseSensor):
    """Sensor showing device / cloud connectivity status."""

    def __init__(
        self, coordinator: OomaDataUpdateCoordinator, entry: ConfigEntry, device_info: DeviceInfo
    ) -> None:
        super().__init__(coordinator, entry, device_info, "status", "Status")
        self._attr_icon = "mdi:phone-classic"

    @property
    def native_value(self) -> Optional[str]:
        if not self.coordinator.data:
            return "unknown"
        is_connected = self.coordinator.data.get("account", {}).get("connected", True)
        return "connected" if is_connected else "disconnected"
