"""Config Flow für Gardena Sileno Integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_LOCATION_ID,
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
    CONF_SCHEDULE_END_TIME_1,
    CONF_SCHEDULE_END_TIME_2,
    CONF_MIN_REMAINING_MINUTES,
    WEEKDAYS,
)

_LOGGER = logging.getLogger(__name__)


async def validate_credentials(
    hass: HomeAssistant, client_id: str, client_secret: str
) -> dict:
    """Zugangsdaten prüfen und Token holen."""
    session = async_get_clientsession(hass)
    async with session.post(
        "https://api.authentication.husqvarnagroup.dev/v1/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
    ) as resp:
        if resp.status != 200:
            raise InvalidCredentials
        data = await resp.json()
        if "access_token" not in data:
            raise InvalidCredentials
        return data


async def get_locations(
    hass: HomeAssistant, client_id: str, access_token: str
) -> list[dict]:
    """Verfügbare Standorte abrufen."""
    session = async_get_clientsession(hass)
    async with session.get(
        "https://api.smart.gardena.dev/v2/locations",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Api-Key": client_id,
        },
    ) as resp:
        if resp.status != 200:
            raise CannotConnect
        data = await resp.json()
        locations = data.get("data", [])
        if not locations:
            raise NoLocations
        return locations


class GardenaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow für Gardena Sileno."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialisierung."""
        self._client_id: str | None = None
        self._client_secret: str | None = None
        self._access_token: str | None = None
        self._locations: list[dict] = []

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Options Flow zurückgeben."""
        return GardenaOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Erster Schritt: Zugangsdaten."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                token_data = await validate_credentials(
                    self.hass,
                    user_input[CONF_CLIENT_ID],
                    user_input[CONF_CLIENT_SECRET],
                )
                self._client_id = user_input[CONF_CLIENT_ID]
                self._client_secret = user_input[CONF_CLIENT_SECRET]
                self._access_token = token_data["access_token"]
                self._locations = await get_locations(
                    self.hass, self._client_id, self._access_token
                )
                return await self.async_step_location()
            except InvalidCredentials:
                errors["base"] = "invalid_credentials"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except NoLocations:
                errors["base"] = "no_locations"
            except Exception:
                _LOGGER.exception("Unbekannter Fehler")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_CLIENT_ID): str,
                vol.Required(CONF_CLIENT_SECRET): str,
            }),
            errors=errors,
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Zweiter Schritt: Standort auswählen."""
        if len(self._locations) == 1 and user_input is None:
            user_input = {CONF_LOCATION_ID: self._locations[0]["id"]}

        if user_input is not None:
            location_id = user_input[CONF_LOCATION_ID]
            location_name = next(
                (loc["attributes"]["name"] for loc in self._locations
                 if loc["id"] == location_id),
                "Garten",
            )
            await self.async_set_unique_id(location_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Gardena – {location_name}",
                data={
                    CONF_CLIENT_ID: self._client_id,
                    CONF_CLIENT_SECRET: self._client_secret,
                    CONF_LOCATION_ID: location_id,
                },
            )

        location_options = {
            loc["id"]: loc["attributes"]["name"] for loc in self._locations
        }
        return self.async_show_form(
            step_id="location",
            data_schema=vol.Schema({
                vol.Required(CONF_LOCATION_ID): vol.In(location_options),
            }),
        )


class GardenaOptionsFlow(config_entries.OptionsFlow):
    """Options Flow für nachträgliche Konfiguration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialisierung."""
        self._options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Erster Schritt – Rolltor."""
        return await self.async_step_cover()

    async def async_step_cover(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Rolltor-Konfiguration."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_schedule()

        cover_entities = {"": "Kein Rolltor"}
        entity_reg = er.async_get(self.hass)
        for entity in entity_reg.entities.values():
            if entity.domain == "cover":
                cover_entities[entity.entity_id] = (
                    entity.name or entity.original_name or entity.entity_id
                )

        return self.async_show_form(
            step_id="cover",
            data_schema=vol.Schema({
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
            }),
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
            data_schema=vol.Schema({
                vol.Required(
                    CONF_SCHEDULE_ENABLED,
                    default=self._options.get(CONF_SCHEDULE_ENABLED, False),
                ): bool,
                vol.Required(
                    CONF_SCHEDULE_DAYS,
                    default=self._options.get(CONF_SCHEDULE_DAYS, ["mon", "wed", "fri"]),
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
                    CONF_SCHEDULE_END_TIME_1,
                    default=self._options.get(CONF_SCHEDULE_END_TIME_1, "12:00"),
                ): str,
                vol.Optional(
                    CONF_SCHEDULE_TIME_2_ENABLED,
                    default=self._options.get(CONF_SCHEDULE_TIME_2_ENABLED, False),
                ): bool,
                vol.Optional(
                    CONF_SCHEDULE_TIME_2,
                    default=self._options.get(CONF_SCHEDULE_TIME_2, "14:00"),
                ): str,
                vol.Optional(
                    CONF_SCHEDULE_END_TIME_2,
                    default=self._options.get(CONF_SCHEDULE_END_TIME_2, "17:00"),
                ): str,
                vol.Optional(
                    CONF_MIN_REMAINING_MINUTES,
                    default=self._options.get(CONF_MIN_REMAINING_MINUTES, 30),
                ): vol.All(int, vol.Range(min=10, max=120)),
            }),
        )

    async def async_step_rain(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Regensperre-Konfiguration."""
        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

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
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_RAIN_SENSOR,
                    default=self._options.get(CONF_RAIN_SENSOR, ""),
                ): vol.In(rain_sensors),
                vol.Optional(
                    CONF_RAIN_THRESHOLD,
                    default=self._options.get(CONF_RAIN_THRESHOLD, 2.5),
                ): vol.All(float, vol.Range(min=0.1, max=20.0)),
            }),
        )


class InvalidCredentials(Exception):
    """Ungültige Zugangsdaten."""


class CannotConnect(Exception):
    """Verbindung fehlgeschlagen."""


class NoLocations(Exception):
    """Keine Standorte gefunden."""
