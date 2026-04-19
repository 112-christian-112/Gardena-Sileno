"""Switch Entitäten für Gardena Sileno Integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import GardenaCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class GardenaSwitchEntityDescription(SwitchEntityDescription):
    """Beschreibung für Gardena Switch Entitäten."""
    default_state: bool = False


SWITCH_DESCRIPTIONS: tuple[GardenaSwitchEntityDescription, ...] = (
    GardenaSwitchEntityDescription(
        key="schedule_enabled",
        name="Zeitplan aktiv",
        icon="mdi:calendar-clock",
        default_state=False,
    ),
    GardenaSwitchEntityDescription(
        key="schedule_window_1_enabled",
        name="Zeitfenster 1 aktiv",
        icon="mdi:clock-start",
        default_state=True,
    ),
    GardenaSwitchEntityDescription(
        key="schedule_window_2_enabled",
        name="Zeitfenster 2 aktiv",
        icon="mdi:clock-start",
        default_state=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Switch Entitäten einrichten."""
    coordinator: GardenaCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        GardenaSwitch(coordinator, description, entry)
        for description in SWITCH_DESCRIPTIONS
    )


class GardenaSwitch(SwitchEntity, RestoreEntity):
    """Gardena Switch Entität."""

    entity_description: GardenaSwitchEntityDescription

    def __init__(
        self,
        coordinator: GardenaCoordinator,
        description: GardenaSwitchEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialisierung."""
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_is_on = description.default_state
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
        if last_state:
            self._attr_is_on = last_state.state == "on"

    async def async_turn_on(self, **kwargs) -> None:
        """Einschalten."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Ausschalten."""
        self._attr_is_on = False
        self.async_write_ha_state()
