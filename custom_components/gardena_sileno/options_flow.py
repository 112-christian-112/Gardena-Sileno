"""Options Flow für Gardena Sileno Integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_COVER_ENTITY,
    CONF_COVER_OPEN_WAIT,
    CONF_COVER_CLOSE_WAIT,
    CONF_RAIN_SENSOR,
    CONF_RAIN_THRESHOLD,
    CONF_SCHEDULE_ENABLED,
    CONF_SCHEDULE_DAYS,
    CONF_SCHEDULE_TIME_1,
    CONF_SCHEDULE_TIME_2,
    CONF_SCHEDULE_TIME_1_ENABLED,
    CONF_SCHEDULE_TIME_2_ENABLED,
    WEEKDAYS,
)

_LOGGER = logging.getLogger(__name__)


class GardenaOptionsFlow(config_entries.OptionsFlow):
    """Options Flow für nachträgliche Konfiguration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialisierung."""
        self._options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Erster Schritt – Übersicht."""
        return await self.async_step_cover()

    async def async_step_cover(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Rolltor-Konfiguration."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_schedule()

        # Alle cover-Entitäten aus HA holen
        cover_entities = {
            "": "Kein Rolltor",
        }
        entity_reg = er.async_get(self.hass)
        for entity in entity_reg.entities.values():
            if entity.domain == "cover":
                cover_entities[entity.entity_id] = (
                    entity.name or entity.original_name or entity.entity_id
                )

        return self.async_show_form(
            step_id="cover",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_COVER_ENTITY,
                        default=self._options.get(CONF_COVER_ENTITY, ""),
                    ): vol.In(cover_entities),
                    vol.Optional(
                        CONF_COVER_OPEN_WAIT,
                        default=self._options.get(CONF_COVER_OPEN_WAIT, 30),
                    ): vol.All(int, vol.Range(min=5, max=120)),
                    vol.Optional(
                        CONF_COVER_CLOSE_WAIT,
                        default=self._options.get(CONF_COVER_CLOSE_WAIT, 60),
                    ): vol.All(int, vol.Range(min=5, max=300)),
                }
            ),
            description_placeholders={
                "cover_hint": "Wähle die cover-Entität deines Rolltors aus."
            },
        )

    async def async_step_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Mähplan-Konfiguration."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_rain()

        return self.async_show_form(
            step_id="schedule",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCHEDULE_ENABLED,
                        default=self._options.get(CONF_SCHEDULE_ENABLED, False),
                    ): bool,
                    vol.Required(
                        CONF_SCHEDULE_DAYS,
                        default=self._options.get(
                            CONF_SCHEDULE_DAYS,
                            ["mon", "wed", "fri"],
                        ),
                    ): cv.multi_select(WEEKDAYS),
                    vol.Optional(
                        CONF_SCHEDULE_TIME_1_ENABLED,
                        default=self._options.get(CONF_SCHEDULE_TIME_1_ENABLED, True),
                    ): bool,
                    vol.Optional(
                        CONF_SCHEDULE_TIME_1,
                        default=self._options.get(CONF_SCHEDULE_TIME_1, "09:00"),
                    ): str,
                    vol.Optional(
                        CONF_SCHEDULE_TIME_2_ENABLED,
                        default=self._options.get(CONF_SCHEDULE_TIME_2_ENABLED, False),
                    ): bool,
                    vol.Optional(
                        CONF_SCHEDULE_TIME_2,
                        default=self._options.get(CONF_SCHEDULE_TIME_2, "14:00"),
                    ): str,
                }
            ),
        )

    async def async_step_rain(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Regensperre-Konfiguration."""
        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        # Alle sensor-Entitäten die precipitation enthalten
        rain_sensors = {"": "Keinen Regensensor"}
        entity_reg = er.async_get(self.hass)
        for entity in entity_reg.entities.values():
            if entity.domain == "sensor" and any(
                x in (entity.entity_id + (entity.name or "")).lower()
                for x in ["rain", "precipitation", "regen", "neerslag", "buienradar"]
            ):
                rain_sensors[entity.entity_id] = (
                    entity.name or entity.original_name or entity.entity_id
                )

        return self.async_show_form(
            step_id="rain",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_RAIN_SENSOR,
                        default=self._options.get(CONF_RAIN_SENSOR, ""),
                    ): vol.In(rain_sensors),
                    vol.Optional(
                        CONF_RAIN_THRESHOLD,
                        default=self._options.get(CONF_RAIN_THRESHOLD, 2.5),
                    ): vol.All(float, vol.Range(min=0.1, max=20.0)),
                }
            ),
            description_placeholders={
                "rain_hint": "Buienradar: sensor.buienradar_precipitation (mm/h). Starkregen ab 2.5 mm/h."
            },
        )
