"""Select Entitäten für Gardena Sileno Integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, WEEKDAYS
from .coordinator import GardenaCoordinator

_LOGGER = logging.getLogger(__name__)

# Wochentage als Optionen
WEEKDAY_OPTIONS = list(WEEKDAYS.values())
WEEKDAY_KEY_BY_LABEL = {v: k for k, v in WEEKDAYS.items()}
WEEKDAY_LABEL_BY_KEY = WEEKDAYS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Select Entitäten einrichten."""
    coordinator: GardenaCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = [
        GardenaMowDaysSelect(coordinator, entry),
        GardenaCoverSelect(coordinator, entry),
        GardenaRainSensorSelect(coordinator, entry),
    ]

    async_add_entities(entities)


class GardenaMowDaysSelect(SelectEntity, RestoreEntity):
    """Auswahl der Mähtage."""

    _attr_name = "Mähtage"
    _attr_icon = "mdi:calendar-week"
    # Mehrfachauswahl simulieren mit kommagetrentem String
    _attr_options = [
        "Montag", "Dienstag", "Mittwoch", "Donnerstag",
        "Freitag", "Samstag", "Sonntag",
        # Kombinationen
        "Mo, Mi, Fr", "Mo, Di, Mi, Do, Fr",
        "Mo, Di, Mi, Do, Fr, Sa, So",
        "Sa, So",
    ]

    def __init__(self, coordinator: GardenaCoordinator, entry: ConfigEntry) -> None:
        """Initialisierung."""
        self._attr_unique_id = f"{entry.entry_id}_mow_days"
        self._attr_current_option = "Mo, Mi, Fr"
        self._entry = entry
        self._coordinator = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        data = self._coordinator.data or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"Gardena {data.get('name', 'SILENO')}",
            manufacturer="Gardena",
            model=data.get("model_type", "GARDENA smart Mower"),
            serial_number=data.get("serial"),
        )

    def get_active_weekday_keys(self) -> list[str]:
        """Aktive Wochentage als Schlüssel zurückgeben."""
        day_map = {
            "Montag": "mon", "Dienstag": "tue", "Mittwoch": "wed",
            "Donnerstag": "thu", "Freitag": "fri", "Samstag": "sat",
            "Sonntag": "sun",
            "Mo, Mi, Fr": ["mon", "wed", "fri"],
            "Mo, Di, Mi, Do, Fr": ["mon", "tue", "wed", "thu", "fri"],
            "Mo, Di, Mi, Do, Fr, Sa, So": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
            "Sa, So": ["sat", "sun"],
        }
        result = day_map.get(self._attr_current_option, [])
        if isinstance(result, str):
            return [result]
        return result

    async def async_added_to_hass(self) -> None:
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in self._attr_options:
            self._attr_current_option = last_state.state

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()


class GardenaCoverSelect(SelectEntity, RestoreEntity):
    """Auswahl des Rolltors."""

    _attr_name = "Rolltor"
    _attr_icon = "mdi:garage"

    def __init__(self, coordinator: GardenaCoordinator, entry: ConfigEntry) -> None:
        """Initialisierung."""
        self._attr_unique_id = f"{entry.entry_id}_cover_select"
        self._attr_current_option = "Kein Rolltor"
        self._attr_options = ["Kein Rolltor"]
        self._entry = entry
        self._coordinator = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        data = self._coordinator.data or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"Gardena {data.get('name', 'SILENO')}",
            manufacturer="Gardena",
            model=data.get("model_type", "GARDENA smart Mower"),
            serial_number=data.get("serial"),
        )

    async def async_added_to_hass(self) -> None:
        """Verfügbare Cover-Entitäten laden."""
        await self._update_options()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in self._attr_options:
            self._attr_current_option = last_state.state

    async def _update_options(self) -> None:
        """Cover-Entitäten aus HA laden."""
        options = ["Kein Rolltor"]
        entity_reg = async_get_entity_registry(self.hass)
        for entity in entity_reg.entities.values():
            if entity.domain == "cover":
                label = entity.name or entity.original_name or entity.entity_id
                options.append(f"{label} ({entity.entity_id})")
        self._attr_options = options

    def get_cover_entity_id(self) -> str | None:
        """Cover-Entitäts-ID aus aktuellem Wert extrahieren."""
        if self._attr_current_option == "Kein Rolltor":
            return None
        # Format: "Name (entity_id)"
        if "(" in self._attr_current_option:
            return self._attr_current_option.split("(")[-1].rstrip(")")
        return None

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()


class GardenaRainSensorSelect(SelectEntity, RestoreEntity):
    """Auswahl des Regensensors."""

    _attr_name = "Regensensor"
    _attr_icon = "mdi:weather-rainy"

    def __init__(self, coordinator: GardenaCoordinator, entry: ConfigEntry) -> None:
        """Initialisierung."""
        self._attr_unique_id = f"{entry.entry_id}_rain_sensor_select"
        self._attr_current_option = "Kein Regensensor"
        self._attr_options = ["Kein Regensensor"]
        self._entry = entry
        self._coordinator = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        data = self._coordinator.data or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"Gardena {data.get('name', 'SILENO')}",
            manufacturer="Gardena",
            model=data.get("model_type", "GARDENA smart Mower"),
            serial_number=data.get("serial"),
        )

    async def async_added_to_hass(self) -> None:
        """Verfügbare Sensor-Entitäten laden."""
        await self._update_options()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in self._attr_options:
            self._attr_current_option = last_state.state

    async def _update_options(self) -> None:
        """Regen-Sensoren aus HA laden."""
        options = ["Kein Regensensor"]
        entity_reg = async_get_entity_registry(self.hass)
        for entity in entity_reg.entities.values():
            if entity.domain == "sensor":
                entity_id_lower = entity.entity_id.lower()
                name_lower = (entity.name or entity.original_name or "").lower()
                if any(
                    x in entity_id_lower or x in name_lower
                    for x in ["rain", "precipitation", "regen", "neerslag", "buienradar", "niederschlag"]
                ):
                    label = entity.name or entity.original_name or entity.entity_id
                    options.append(f"{label} ({entity.entity_id})")
        self._attr_options = options

    def get_sensor_entity_id(self) -> str | None:
        """Sensor-Entitäts-ID extrahieren."""
        if self._attr_current_option == "Kein Regensensor":
            return None
        if "(" in self._attr_current_option:
            return self._attr_current_option.split("(")[-1].rstrip(")")
        return None

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()
