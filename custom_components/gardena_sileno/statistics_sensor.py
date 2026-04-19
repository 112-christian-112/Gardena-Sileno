"""Statistik-Sensoren für Gardena Sileno – geschätzte Lade- und Mähdauer."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import GardenaCoordinator

_LOGGER = logging.getLogger(__name__)

# Aktivitätszustände
CHARGING_STATES = {"OK_CHARGING"}
MOWING_STATES = {"OK_CUTTING", "OK_CUTTING_TIMER_OVERRIDDEN"}
MOWING_END_STATES = {"OK_SEARCHING", "GOING_HOME", "OK_CHARGING", "PARKED_TIMER",
                     "PARKED_PARK_SELECTED", "PARKED_MOWING_COMPLETED", "PARKED_RAIN"}
CHARGING_END_STATES = {"OK_LEAVING", "OK_CUTTING", "OK_CUTTING_TIMER_OVERRIDDEN"}
INVALID_STATES = {"NONE", "STOPPED_IN_GARDEN"}
ERROR_STATES = {"ERROR"}

# Grenzwerte
MIN_CHARGING_MINUTES = 5
MAX_CHARGING_MINUTES = 240
MIN_MOWING_MINUTES = 10
MAX_MOWING_MINUTES = 480
MAX_BATTERY_START = 95  # Akku muss unter diesem Wert sein für valide Ladesession
HISTORY_DAYS = 30
MIN_SESSIONS_FOR_HIGH_CONFIDENCE = 10
MIN_SESSIONS_FOR_MEDIUM_CONFIDENCE = 4


def _get_confidence(sessions: int) -> str:
    """Konfidenz basierend auf Anzahl valider Sessions."""
    if sessions >= MIN_SESSIONS_FOR_HIGH_CONFIDENCE:
        return "hoch"
    elif sessions >= MIN_SESSIONS_FOR_MEDIUM_CONFIDENCE:
        return "mittel"
    elif sessions >= 1:
        return "niedrig"
    return "keine Daten"


def _format_duration(minutes: float) -> str:
    """Minuten in lesbares Format umwandeln."""
    if minutes < 1:
        return "< 1 Minute"
    elif minutes < 60:
        return f"{int(minutes)} Minuten"
    else:
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        if mins == 0:
            return f"{hours} Stunde{'n' if hours > 1 else ''}"
        return f"{hours}:{mins:02d} Stunden"


class GardenaStatisticsSensor(SensorEntity):
    """Basisklasse für Statistik-Sensoren."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: GardenaCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialisierung."""
        self.hass = hass
        self._coordinator = coordinator
        self._entry = entry
        self._activity_entity_id = "sensor.gardena_sileno_aktivitat"
        self._battery_entity_id = "sensor.gardena_sileno_akkustand"
        self._sessions: list[dict] = []
        self._current_session_start: datetime | None = None
        self._avg_duration: float | None = None
        self._unsubscribe = None

    @property
    def device_info(self) -> DeviceInfo:
        """Geräteinformationen."""
        name = self._coordinator.data.get("name", "SILENO") if self._coordinator.data else "SILENO"
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"Gardena {name}",
            manufacturer="Gardena",
            model="GARDENA smart Mower",
        )

    async def async_added_to_hass(self) -> None:
        """Wird aufgerufen wenn Entität zu HA hinzugefügt wird."""
        # Auf Zustandsänderungen hören
        self._unsubscribe = async_track_state_change_event(
            self.hass,
            [self._activity_entity_id],
            self._handle_state_change,
        )
        # Historische Daten laden
        await self._load_history()

    async def async_will_remove_from_hass(self) -> None:
        """Wird aufgerufen wenn Entität entfernt wird."""
        if self._unsubscribe:
            self._unsubscribe()

    async def _handle_state_change(self, event) -> None:
        """Zustandsänderung verarbeiten."""
        raise NotImplementedError

    async def _load_history(self) -> None:
        """Historische Daten laden und Sessions berechnen."""
        raise NotImplementedError

    def _get_battery_at_time(self, timestamp: datetime) -> float | None:
        """Akkustand zu einem bestimmten Zeitpunkt aus History holen."""
        try:
            battery_state = self.hass.states.get(self._battery_entity_id)
            if battery_state:
                return float(battery_state.state)
        except (ValueError, TypeError):
            pass
        return None


class GardenaChargingTimeSensor(GardenaStatisticsSensor):
    """Geschätzte verbleibende Ladezeit."""

    _attr_icon = "mdi:battery-charging"
    _attr_name = "Geschätzte Ladezeit"

    def __init__(self, hass, coordinator, entry) -> None:
        """Initialisierung."""
        super().__init__(hass, coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_charging_time_estimate"
        self._valid_sessions: list[float] = []  # Dauer in Minuten
        self._session_start: datetime | None = None
        self._session_start_battery: float | None = None

    @property
    def native_value(self) -> str:
        """Geschätzte verbleibende Ladezeit."""
        if not self._coordinator.data:
            return "Unbekannt"

        activity_raw = self._coordinator.data.get("activity_raw", "") if self._coordinator.data else ""

        # Nicht am Laden
        if activity_raw not in CHARGING_STATES:
            return "Nicht am Laden"

        # Noch keine Session gestartet
        if not self._session_start:
            return "Berechne..."

        # Keine Durchschnittsdaten
        if not self._valid_sessions:
            elapsed = (dt_util.utcnow() - self._session_start).total_seconds() / 60
            return f"Lädt seit {_format_duration(elapsed)}"

        avg = sum(self._valid_sessions) / len(self._valid_sessions)
        elapsed = (dt_util.utcnow() - self._session_start).total_seconds() / 60
        remaining = max(0, avg - elapsed)

        if remaining < 1:
            return "Fast fertig"
        return f"Noch ~{_format_duration(remaining)}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zusätzliche Attribute."""
        attrs: dict[str, Any] = {
            "konfidenz": _get_confidence(len(self._valid_sessions)),
            "basiert_auf_sessions": len(self._valid_sessions),
        }

        if self._valid_sessions:
            avg = sum(self._valid_sessions) / len(self._valid_sessions)
            attrs["durchschnitt_minuten"] = round(avg, 1)

        if self._session_start:
            elapsed = (dt_util.utcnow() - self._session_start).total_seconds() / 60
            attrs["aktuelle_session_minuten"] = round(elapsed, 1)
            if self._session_start_battery is not None:
                attrs["akku_bei_start"] = self._session_start_battery

        return attrs

    async def _load_history(self) -> None:
        """Historische Ladesessions laden."""
        try:
            start_time = dt_util.utcnow() - timedelta(days=HISTORY_DAYS)

            states = await get_instance(self.hass).async_add_executor_job(
                get_significant_states,
                self.hass,
                start_time,
                None,
                [self._activity_entity_id, self._battery_entity_id],
            )

            activity_states = states.get(self._activity_entity_id, [])
            battery_states = states.get(self._battery_entity_id, [])

            self._valid_sessions = self._extract_charging_sessions(
                activity_states, battery_states
            )

            _LOGGER.debug(
                "Ladezeit: %d valide Sessions geladen", len(self._valid_sessions)
            )

            # Aktuelle Session prüfen
            current = self.hass.states.get(self._activity_entity_id)
            if current and current.state in CHARGING_STATES:
                self._session_start = current.last_changed
                battery = self._get_battery_at_time(self._session_start)
                self._session_start_battery = battery

            self.async_write_ha_state()

        except Exception as e:
            _LOGGER.error("Fehler beim Laden der Ladehistorie: %s", e)

    def _extract_charging_sessions(
        self, activity_states: list, battery_states: list
    ) -> list[float]:
        """Valide Ladesessions aus History extrahieren."""
        valid_durations = []
        session_start = None
        session_start_battery = None

        # Battery-States als Dict für schnellen Zugriff
        battery_by_time = {}
        for state in battery_states:
            try:
                battery_by_time[state.last_changed] = float(state.state)
            except (ValueError, TypeError):
                pass

        def get_battery_near(timestamp: datetime) -> float | None:
            """Nächsten Akkustand zum Zeitpunkt holen."""
            best = None
            best_diff = timedelta(minutes=10)
            for ts, val in battery_by_time.items():
                diff = abs(ts - timestamp)
                if diff < best_diff:
                    best_diff = diff
                    best = val
            return best

        for i, state in enumerate(activity_states):
            activity = state.state

            # Session startet
            if activity in CHARGING_STATES and session_start is None:
                battery_at_start = get_battery_near(state.last_changed)

                # Akku muss unter MAX_BATTERY_START sein
                if battery_at_start is not None and battery_at_start >= MAX_BATTERY_START:
                    _LOGGER.debug(
                        "Ladesession übersprungen: Akku bereits bei %s%%",
                        battery_at_start,
                    )
                    continue

                session_start = state.last_changed
                session_start_battery = battery_at_start

            # Session endet
            elif activity in CHARGING_END_STATES and session_start is not None:
                duration = (state.last_changed - session_start).total_seconds() / 60

                # Validierung
                if MIN_CHARGING_MINUTES <= duration <= MAX_CHARGING_MINUTES:
                    valid_durations.append(duration)
                    _LOGGER.debug(
                        "Valide Ladesession: %.1f Minuten (Akku bei Start: %s%%)",
                        duration,
                        session_start_battery,
                    )
                else:
                    _LOGGER.debug(
                        "Ladesession ungültig: %.1f Minuten (außerhalb Grenzen)",
                        duration,
                    )

                session_start = None
                session_start_battery = None

            # Session durch Fehler unterbrochen
            elif activity in ERROR_STATES and session_start is not None:
                _LOGGER.debug("Ladesession durch Fehler unterbrochen")
                session_start = None
                session_start_battery = None

        # Nur letzte 20 Sessions für Durchschnitt
        return valid_durations[-20:]

    async def _handle_state_change(self, event) -> None:
        """Zustandsänderung des Aktivitätssensors verarbeiten."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if not new_state:
            return

        new_activity = new_state.attributes.get("activity_raw", new_state.state)
        old_activity = old_state.attributes.get("activity_raw", old_state.state) if old_state else None

        # Neue Ladesession startet
        if new_activity in CHARGING_STATES and old_activity not in CHARGING_STATES:
            battery = self._get_battery_at_time(dt_util.utcnow())

            if battery is not None and battery >= MAX_BATTERY_START:
                _LOGGER.debug("Ladesession ignoriert: Akku bei %s%%", battery)
                self._session_start = None
                return

            self._session_start = dt_util.utcnow()
            self._session_start_battery = battery
            _LOGGER.debug("Neue Ladesession gestartet (Akku: %s%%)", battery)

        # Ladesession endet
        elif old_activity in CHARGING_STATES and new_activity in CHARGING_END_STATES:
            if self._session_start:
                duration = (dt_util.utcnow() - self._session_start).total_seconds() / 60

                if MIN_CHARGING_MINUTES <= duration <= MAX_CHARGING_MINUTES:
                    self._valid_sessions.append(duration)
                    # Maximal 20 Sessions behalten
                    if len(self._valid_sessions) > 20:
                        self._valid_sessions.pop(0)
                    _LOGGER.info("Ladesession abgeschlossen: %.1f Minuten", duration)

                self._session_start = None
                self._session_start_battery = None

        # Session durch Fehler/Unterbrechung beendet
        elif old_activity in CHARGING_STATES and new_activity in (ERROR_STATES | INVALID_STATES):
            self._session_start = None
            self._session_start_battery = None

        self.async_write_ha_state()


class GardenaMowingTimeSensor(GardenaStatisticsSensor):
    """Geschätzte verbleibende Mähdauer."""

    _attr_icon = "mdi:timer-outline"
    _attr_name = "Geschätzte Mähdauer"

    def __init__(self, hass, coordinator, entry) -> None:
        """Initialisierung."""
        super().__init__(hass, coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_mowing_time_estimate"
        self._valid_sessions: list[float] = []
        self._session_start: datetime | None = None
        self._session_type: str | None = None  # SCHEDULE oder MANUAL

    @property
    def native_value(self) -> str:
        """Geschätzte verbleibende Mähdauer."""
        if not self._coordinator.data:
            return "Unbekannt"

        activity_raw = self._coordinator.data.get("activity_raw", "") if self._coordinator.data else ""

        if activity_raw not in MOWING_STATES:
            return "Mäht nicht"

        if not self._session_start:
            return "Berechne..."

        # Manuelle Sessions separat behandeln
        sessions = self._get_relevant_sessions(activity_raw)

        if not sessions:
            elapsed = (dt_util.utcnow() - self._session_start).total_seconds() / 60
            return f"Mäht seit {_format_duration(elapsed)}"

        avg = sum(sessions) / len(sessions)
        elapsed = (dt_util.utcnow() - self._session_start).total_seconds() / 60
        remaining = max(0, avg - elapsed)

        if remaining < 1:
            return "Fast fertig"
        return f"Noch ~{_format_duration(remaining)}"

    def _get_relevant_sessions(self, current_activity: str) -> list[float]:
        """Relevante Sessions basierend auf aktuellem Mähtyp."""
        # Manuelle und geplante Sessions trennen
        if current_activity == "OK_CUTTING_TIMER_OVERRIDDEN":
            return [s for s in self._valid_sessions if s.get("type") == "MANUAL"]
        return [s["duration"] for s in self._valid_sessions if s.get("type") == "SCHEDULE"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zusätzliche Attribute."""
        activity_raw = self._coordinator.data.get("activity_raw", "") if self._coordinator.data else ""
        relevant = self._get_relevant_sessions(activity_raw)

        attrs: dict[str, Any] = {
            "konfidenz": _get_confidence(len(relevant)),
            "basiert_auf_sessions": len(relevant),
            "gesamt_sessions": len(self._valid_sessions),
        }

        if relevant:
            avg = sum(relevant) / len(relevant)
            attrs["durchschnitt_minuten"] = round(avg, 1)

        if self._session_start:
            elapsed = (dt_util.utcnow() - self._session_start).total_seconds() / 60
            attrs["aktuelle_session_minuten"] = round(elapsed, 1)
            attrs["session_typ"] = self._session_type

        return attrs

    async def _load_history(self) -> None:
        """Historische Mähsessions laden."""
        try:
            start_time = dt_util.utcnow() - timedelta(days=HISTORY_DAYS)

            states = await get_instance(self.hass).async_add_executor_job(
                get_significant_states,
                self.hass,
                start_time,
                None,
                [self._activity_entity_id],
            )

            activity_states = states.get(self._activity_entity_id, [])
            self._valid_sessions = self._extract_mowing_sessions(activity_states)

            _LOGGER.debug(
                "Mähdauer: %d valide Sessions geladen", len(self._valid_sessions)
            )

            # Aktuelle Session prüfen
            current = self.hass.states.get(self._activity_entity_id)
            if current and current.state in MOWING_STATES:
                self._session_start = current.last_changed
                self._session_type = (
                    "MANUAL"
                    if current.state == "OK_CUTTING_TIMER_OVERRIDDEN"
                    else "SCHEDULE"
                )

            self.async_write_ha_state()

        except Exception as e:
            _LOGGER.error("Fehler beim Laden der Mähhistorie: %s", e)

    def _extract_mowing_sessions(self, activity_states: list) -> list[dict]:
        """Valide Mähsessions aus History extrahieren."""
        valid_sessions = []
        session_start = None
        session_type = None
        has_error = False

        for state in activity_states:
            activity = state.state

            # Session startet
            if activity in MOWING_STATES and session_start is None:
                session_start = state.last_changed
                session_type = (
                    "MANUAL" if activity == "OK_CUTTING_TIMER_OVERRIDDEN" else "SCHEDULE"
                )
                has_error = False

            # Fehler während Session
            elif activity in ERROR_STATES and session_start is not None:
                has_error = True

            # Session endet
            elif activity in MOWING_END_STATES and session_start is not None:
                if not has_error:
                    duration = (
                        state.last_changed - session_start
                    ).total_seconds() / 60

                    if MIN_MOWING_MINUTES <= duration <= MAX_MOWING_MINUTES:
                        valid_sessions.append({
                            "duration": duration,
                            "type": session_type,
                        })
                        _LOGGER.debug(
                            "Valide Mähsession: %.1f Minuten (%s)",
                            duration,
                            session_type,
                        )
                    else:
                        _LOGGER.debug(
                            "Mähsession ungültig: %.1f Minuten", duration
                        )
                else:
                    _LOGGER.debug("Mähsession mit Fehler übersprungen")

                session_start = None
                session_type = None
                has_error = False

            # Durch Pause unterbrochen – Session ungültig
            elif activity == "PAUSED" and session_start is not None:
                _LOGGER.debug("Mähsession durch Pause unterbrochen")
                session_start = None
                session_type = None

        # Nur letzte 20 Sessions
        return valid_sessions[-20:]

    async def _handle_state_change(self, event) -> None:
        """Zustandsänderung verarbeiten."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if not new_state:
            return

        new_activity = new_state.attributes.get("activity_raw", new_state.state)
        old_activity = old_state.attributes.get("activity_raw", old_state.state) if old_state else None

        # Neue Mähsession
        if new_activity in MOWING_STATES and old_activity not in MOWING_STATES:
            self._session_start = dt_util.utcnow()
            self._session_type = (
                "MANUAL" if new_activity == "OK_CUTTING_TIMER_OVERRIDDEN" else "SCHEDULE"
            )
            _LOGGER.debug("Neue Mähsession gestartet (%s)", self._session_type)

        # Mähsession endet normal
        elif old_activity in MOWING_STATES and new_activity in MOWING_END_STATES:
            if self._session_start:
                duration = (dt_util.utcnow() - self._session_start).total_seconds() / 60

                if MIN_MOWING_MINUTES <= duration <= MAX_MOWING_MINUTES:
                    self._valid_sessions.append({
                        "duration": duration,
                        "type": self._session_type,
                    })
                    if len(self._valid_sessions) > 20:
                        self._valid_sessions.pop(0)
                    _LOGGER.info("Mähsession abgeschlossen: %.1f Minuten", duration)

                self._session_start = None
                self._session_type = None

        # Durch Pause/Fehler unterbrochen
        elif old_activity in MOWING_STATES and new_activity in (
            ERROR_STATES | INVALID_STATES | {"PAUSED"}
        ):
            _LOGGER.debug("Mähsession unterbrochen durch: %s", new_activity)
            self._session_start = None
            self._session_type = None

        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Statistik-Sensoren einrichten."""
    coordinator: GardenaCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities([
        GardenaChargingTimeSensor(hass, coordinator, entry),
        GardenaMowingTimeSensor(hass, coordinator, entry),
    ])
