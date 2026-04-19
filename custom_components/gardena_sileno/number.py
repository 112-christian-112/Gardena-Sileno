"""Number Entitäten für Gardena Sileno Integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import GardenaCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class GardenaNumberEntityDescription(NumberEntityDescription):
    """Beschreibung für Gardena Number Entitäten."""
    default_value: float = 0.0


NUMBER_DESCRIPTIONS: tuple[GardenaNumberEntityDescription, ...] = (
    GardenaNumberEntityDescription(
        key="min_battery_start",
        name="Mindest-Akkustand zum Starten",
        icon="mdi:battery-charging",
        native_min_value=80,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        mode=NumberMode.SLIDER,
        default_value=95,
    ),
    GardenaNumberEntityDescription(
        key="min_remaining_minutes",
        name="Mindest-Restzeit im Zeitfenster",
        icon="mdi:timer-outline",
        native_min_value=10,
        native_max_value=120,
        native_step=5,
        native_unit_of_measurement="min",
        mode=NumberMode.SLIDER,
        default_value=30,
    ),
    GardenaNumberEntityDescription(
        key="cover_open_wait",
        name="Rolltor Wartezeit Öffnen",
        icon="mdi:timer",
        native_min_value=5,
        native_max_value=120,
        native_step=5,
        native_unit_of_measurement="s",
        mode=NumberMode.SLIDER,
        default_value=30,
    ),
    GardenaNumberEntityDescription(
        key="cover_close_wait",
        name="Rolltor Wartezeit Schließen",
        icon="mdi:timer",
        native_min_value=5,
        native_max_value=300,
        native_step=5,
        native_unit_of_measurement="s",
        mode=NumberMode.SLIDER,
        default_value=60,
    ),
    GardenaNumberEntityDescription(
        key="rain_threshold",
        name="Starkregen-Schwellwert",
        icon="mdi:weather-pouring",
        native_min_value=0.1,
        native_max_value=20.0,
        native_step=0.1,
        native_unit_of_measurement="mm/h",
        mode=NumberMode.BOX,
        default_value=2.5,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Number Entitäten einrichten."""
    coordinator: GardenaCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        GardenaNumber(coordinator, description, entry)
        for description in NUMBER_DESCRIPTIONS
    )


class GardenaNumber(NumberEntity, RestoreEntity):
    """Gardena Number Entität."""

    entity_description: GardenaNumberEntityDescription

    def __init__(
        self,
        coordinator: GardenaCoordinator,
        description: GardenaNumberEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialisierung."""
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_native_value = description.default_value
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
                self._attr_native_value = float(last_state.state)
            except (ValueError, TypeError):
                self._attr_native_value = self.entity_description.default_value

    async def async_set_native_value(self, value: float) -> None:
        """Wert setzen."""
        self._attr_native_value = value
        self.async_write_ha_state()
