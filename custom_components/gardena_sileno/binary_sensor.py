"""Binary Sensoren für Gardena Sileno Integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GardenaCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Binary Sensoren einrichten."""
    coordinator: GardenaCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([GardenaOnlineSensor(coordinator, entry)])


class GardenaOnlineSensor(CoordinatorEntity[GardenaCoordinator], BinarySensorEntity):
    """Online/Offline Status des Mähroboters."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "Online"
    _attr_icon = "mdi:wifi"

    def __init__(
        self,
        coordinator: GardenaCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialisierung."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_online"
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Geräteinformationen."""
        name = self.coordinator.data.get("name", "SILENO") if self.coordinator.data else "SILENO"
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"Gardena {name}",
            manufacturer="Gardena",
            model="SILENO",
        )

    @property
    def is_on(self) -> bool | None:
        """True wenn Mäher online."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("online", False)
