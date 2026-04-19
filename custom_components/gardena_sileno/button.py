"""Steuerungsbuttons für Gardena Sileno Integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    COMMAND_START_SECONDS_TO_OVERRIDE,
    COMMAND_PARK_UNTIL_NEXT_TASK,
    COMMAND_PARK_UNTIL_FURTHER_NOTICE,
    COMMAND_RESUME_SCHEDULE,
)
from .coordinator import GardenaCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class GardenaButtonEntityDescription(ButtonEntityDescription):
    """Beschreibung für Gardena Buttons."""
    command: str = ""
    duration: int = 0


BUTTON_DESCRIPTIONS: tuple[GardenaButtonEntityDescription, ...] = (
    GardenaButtonEntityDescription(
        key="start_mowing",
        name="Mähen starten",
        icon="mdi:play",
        command=COMMAND_START_SECONDS_TO_OVERRIDE,
        duration=3600,  # 1 Stunde
    ),
    GardenaButtonEntityDescription(
        key="park_until_next_task",
        name="Parken bis nächster Timer",
        icon="mdi:pause",
        command=COMMAND_PARK_UNTIL_NEXT_TASK,
    ),
    GardenaButtonEntityDescription(
        key="park_until_further_notice",
        name="Parken (dauerhaft)",
        icon="mdi:stop",
        command=COMMAND_PARK_UNTIL_FURTHER_NOTICE,
    ),
    GardenaButtonEntityDescription(
        key="resume_schedule",
        name="Zeitplan fortsetzen",
        icon="mdi:calendar-clock",
        command=COMMAND_RESUME_SCHEDULE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Buttons einrichten."""
    coordinator: GardenaCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        GardenaButton(coordinator, description, entry)
        for description in BUTTON_DESCRIPTIONS
    )


class GardenaButton(CoordinatorEntity[GardenaCoordinator], ButtonEntity):
    """Gardena Steuerungsbutton."""

    entity_description: GardenaButtonEntityDescription

    def __init__(
        self,
        coordinator: GardenaCoordinator,
        description: GardenaButtonEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialisierung."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
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

    async def async_press(self) -> None:
        """Button gedrückt – Befehl senden."""
        _LOGGER.info(
            "Sende Befehl: %s", self.entity_description.command
        )
        success = await self.coordinator.async_send_command(
            self.entity_description.command,
            self.entity_description.duration,
        )
        if success:
            await self.coordinator.async_request_refresh()
