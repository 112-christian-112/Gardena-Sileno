"""Time Entitäten für Gardena Sileno Integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import time

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import GardenaCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class GardenaTimeEntityDescription(TimeEntityDescription):
    """Beschreibung für Gardena Time Entitäten."""
    default_time: time = time(9, 0)


TIME_DESCRIPTIONS: tuple[GardenaTimeEntityDescription, ...] = (
    GardenaTimeEntityDescription(
        key="schedule_start_1",
        name="Zeitfenster 1 Startzeit",
        icon="mdi:clock-start",
        default_time=time(9, 0),
    ),
    GardenaTimeEntityDescription(
        key="schedule_end_1",
        name="Zeitfenster 1 Endzeit",
        icon="mdi:clock-end",
        default_time=time(12, 0),
    ),
    GardenaTimeEntityDescription(
        key="schedule_start_2",
        name="Zeitfenster 2 Startzeit",
        icon="mdi:clock-start",
        default_time=time(14, 0),
    ),
    GardenaTimeEntityDescription(
        key="schedule_end_2",
        name="Zeitfenster 2 Endzeit",
        icon="mdi:clock-end",
        default_time=time(17, 0),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Time Entitäten einrichten."""
    coordinator: GardenaCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        GardenaTime(coordinator, description, entry)
        for description in TIME_DESCRIPTIONS
    )


class GardenaTime(TimeEntity, RestoreEntity):
    """Gardena Time Entität."""

    entity_description: GardenaTimeEntityDescription

    def __init__(
        self,
        coordinator: GardenaCoordinator,
        description: GardenaTimeEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialisierung."""
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_native_value = description.default_time
        self._entry = entry
        self._coordinator = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        """Geräteinformationen."""
        data = self._coordinator.data or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"Gardena {data.get('name', 'SILENO')}",
            manufacturer="Gardena",
            model=data.get("model_type", "GARDENA smart Mower"),
            serial_number=data.get("serial"),
        )

    async def async_added_to_hass(self) -> None:
        """Gespeicherten Zustand wiederherstellen."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                h, m, s = last_state.state.split(":")
                self._attr_native_value = time(int(h), int(m), int(s))
            except (ValueError, TypeError):
                self._attr_native_value = self.entity_description.default_time

    async def async_set_value(self, value: time) -> None:
        """Zeit setzen."""
        self._attr_native_value = value
        self.async_write_ha_state()
