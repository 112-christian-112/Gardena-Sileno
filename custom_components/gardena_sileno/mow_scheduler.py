"""Mähplan-Scheduler für Gardena Sileno."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    COMMAND_RESUME_SCHEDULE,
    COMMAND_PARK_UNTIL_FURTHER_NOTICE,
    WEEKDAY_MAP,
    WEEKDAYS,
)
from .coordinator import GardenaCoordinator

_LOGGER = logging.getLogger(__name__)

HOME_STATES = {
    "OK_CHARGING", "PARKED_TIMER", "PARKED_PARK_SELECTED",
    "PARKED_AUTOTIMER", "PARKED_MOWING_COMPLETED", "PARKED_RAIN",
}

MOWING_STATES = {
    "OK_CUTTING", "OK_CUTTING_TIMER_OVERRIDDEN",
    "OK_LEAVING", "OK_SEARCHING", "GOING_HOME",
}

WEEKDAY_LABEL_MAP = {v: k for k, v in WEEKDAYS.items()}


class GardenaScheduler:
    """Mähplan-Steuerung."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: GardenaCoordinator,
        entry_id: str,
    ) -> None:
        """Initialisierung."""
        self.hass = hass
        self._coordinator = coordinator
        self._entry_id = entry_id
        self._unsubscribers: list = []

        self._window_active = False
        self._window_end: datetime | None = None
        self._mowing_active = False
        self._cover_opened_by_us = False
        self._rain_paused = False
        self._waiting_for_full_battery = False

    # ── Entitäts-IDs ─────────────────────────────────────────────────────────

    def _eid(self, suffix: str) -> str:
        return f"{suffix}.gardena_sileno_{self._entry_id}_{suffix.split('.')[0] if '.' in suffix else suffix}"

    @property
    def _activity_eid(self) -> str:
        return "sensor.gardena_sileno_aktivitat"

    @property
    def _battery_eid(self) -> str:
        return "sensor.gardena_sileno_akkustand"

    @property
    def _schedule_enabled_eid(self) -> str:
        return "switch.gardena_sileno_zeitplan_aktiv"

    @property
    def _window_1_enabled_eid(self) -> str:
        return "switch.gardena_sileno_zeitfenster_1_aktiv"

    @property
    def _window_2_enabled_eid(self) -> str:
        return "switch.gardena_sileno_zeitfenster_2_aktiv"

    @property
    def _start_1_eid(self) -> str:
        return "time.gardena_sileno_zeitfenster_1_startzeit"

    @property
    def _end_1_eid(self) -> str:
        return "time.gardena_sileno_zeitfenster_1_endzeit"

    @property
    def _start_2_eid(self) -> str:
        return "time.gardena_sileno_zeitfenster_2_startzeit"

    @property
    def _end_2_eid(self) -> str:
        return "time.gardena_sileno_zeitfenster_2_endzeit"

    @property
    def _mow_days_eid(self) -> str:
        return "select.gardena_sileno_mahtage"

    @property
    def _cover_eid(self) -> str:
        return "select.gardena_sileno_rolltor"

    @property
    def _rain_sensor_eid(self) -> str:
        return "select.gardena_sileno_regensensor"

    @property
    def _rain_threshold_eid(self) -> str:
        return "number.gardena_sileno_starkregen_schwellwert"

    @property
    def _min_battery_eid(self) -> str:
        return "number.gardena_sileno_mindest_akkustand_zum_starten"

    @property
    def _min_remaining_eid(self) -> str:
        return "number.gardena_sileno_mindest_restzeit_im_zeitfenster"

    @property
    def _cover_open_wait_eid(self) -> str:
        return "number.gardena_sileno_rolltor_wartezeit_offnen"

    @property
    def _cover_close_wait_eid(self) -> str:
        return "number.gardena_sileno_rolltor_wartezeit_schliessen"

    # ── Hilfsmethoden zum Lesen der Entitäten ────────────────────────────────

    def _is_on(self, entity_id: str) -> bool:
        state = self.hass.states.get(entity_id)
        return state is not None and state.state == "on"

    def _get_str(self, entity_id: str, default: str = "") -> str:
        state = self.hass.states.get(entity_id)
        return state.state if state else default

    def _get_float(self, entity_id: str, default: float = 0.0) -> float:
        state = self.hass.states.get(entity_id)
        if not state:
            return default
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return default

    def _get_time(self, entity_id: str) -> time | None:
        state = self.hass.states.get(entity_id)
        if not state:
            return None
        try:
            parts = state.state.split(":")
            return time(int(parts[0]), int(parts[1]))
        except (ValueError, TypeError, IndexError):
            return None

    def _get_cover_entity_id(self) -> str | None:
        state = self.hass.states.get(self._cover_eid)
        if not state or state.state == "Kein Rolltor":
            return None
        if "(" in state.state:
            return state.state.split("(")[-1].rstrip(")")
        return None

    def _get_rain_sensor_entity_id(self) -> str | None:
        state = self.hass.states.get(self._rain_sensor_eid)
        if not state or state.state == "Kein Regensensor":
            return None
        if "(" in state.state:
            return state.state.split("(")[-1].rstrip(")")
        return None

    def _get_active_weekdays(self) -> list[str]:
        """Aktive Wochentage als Schlüssel."""
        state = self.hass.states.get(self._mow_days_eid)
        if not state:
            return []
        day_map = {
            "Montag": ["mon"], "Dienstag": ["tue"], "Mittwoch": ["wed"],
            "Donnerstag": ["thu"], "Freitag": ["fri"], "Samstag": ["sat"],
            "Sonntag": ["sun"],
            "Mo, Mi, Fr": ["mon", "wed", "fri"],
            "Mo, Di, Mi, Do, Fr": ["mon", "tue", "wed", "thu", "fri"],
            "Mo, Di, Mi, Do, Fr, Sa, So": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
            "Sa, So": ["sat", "sun"],
        }
        return day_map.get(state.state, [])

    # ── Start/Stop ────────────────────────────────────────────────────────────

    async def async_start(self) -> None:
        """Scheduler starten."""
        self._unsubscribers.append(
            async_track_time_change(self.hass, self._check_schedule, second=0)
        )
        self._unsubscribers.append(
            async_track_state_change_event(
                self.hass, [self._activity_eid], self._handle_activity_change
            )
        )
        self._unsubscribers.append(
            async_track_state_change_event(
                self.hass, [self._battery_eid], self._handle_battery_change
            )
        )
        _LOGGER.info("Gardena Scheduler gestartet")

    async def async_stop(self) -> None:
        """Scheduler stoppen."""
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()

    # ── Zeitplan ──────────────────────────────────────────────────────────────

    @callback
    def _check_schedule(self, now: datetime) -> None:
        """Prüft ob ein Zeitfenster startet oder endet."""
        if not self._is_on(self._schedule_enabled_eid):
            return

        # Wochentag prüfen
        current_weekday = WEEKDAY_MAP.get(now.weekday())
        if current_weekday not in self._get_active_weekdays():
            return

        current_time = now.strftime("%H:%M")

        # Zeitfenster 1
        if self._is_on(self._window_1_enabled_eid):
            t = self._get_time(self._start_1_eid)
            if t and current_time == t.strftime("%H:%M"):
                end_t = self._get_time(self._end_1_eid)
                if end_t:
                    self.hass.async_create_task(self._start_window(end_t))

        # Zeitfenster 2
        if self._is_on(self._window_2_enabled_eid):
            t = self._get_time(self._start_2_eid)
            if t and current_time == t.strftime("%H:%M"):
                end_t = self._get_time(self._end_2_eid)
                if end_t:
                    self.hass.async_create_task(self._start_window(end_t))

        # Zeitfenster-Ende prüfen
        if self._window_active and self._window_end:
            if now >= self._window_end:
                self.hass.async_create_task(self._end_window())

    # ── Zeitfenster ───────────────────────────────────────────────────────────

    async def _start_window(self, end_time: time) -> None:
        """Zeitfenster starten."""
        if self._window_active:
            return

        now = dt_util.now()
        self._window_end = now.replace(
            hour=end_time.hour, minute=end_time.minute, second=0
        )
        self._window_active = True
        self._rain_paused = False
        _LOGGER.info("Zeitfenster gestartet – Ende: %s", end_time)
        self._fire_event("window_started")

        await self._open_cover_if_configured()
        await self._try_start_mowing()

    async def _end_window(self) -> None:
        """Zeitfenster beenden."""
        if not self._window_active:
            return

        self._window_active = False
        self._window_end = None
        self._waiting_for_full_battery = False
        _LOGGER.info("Zeitfenster beendet")

        if self._mowing_active:
            await self._coordinator.async_send_command(COMMAND_PARK_UNTIL_FURTHER_NOTICE)
            self._fire_event("window_ended_mower_parked")
        else:
            await self._close_cover_if_configured()
            self._fire_event("window_ended")

    # ── Mäh-Steuerung ─────────────────────────────────────────────────────────

    async def _try_start_mowing(self) -> None:
        """Mäher starten wenn alle Bedingungen erfüllt."""
        if not self._window_active or self._mowing_active:
            return

        if not self._has_enough_time():
            _LOGGER.info("Nicht genug Zeit – Zeitfenster wird beendet")
            await self._end_window()
            return

        if await self._is_raining_heavily():
            _LOGGER.info("Starkregen – warte")
            self._rain_paused = True
            return

        if not self._is_battery_sufficient():
            _LOGGER.info(
                "Akku noch nicht ausreichend (min: %s%%) – warte",
                self._get_float(self._min_battery_eid, 95)
            )
            self._waiting_for_full_battery = True
            return

        _LOGGER.info("Starte Mäher")
        self._waiting_for_full_battery = False

        # Verbleibende Zeit im Fenster berechnen
        remaining_seconds = int((self._window_end - dt_util.now()).total_seconds())
        # Auf Vielfaches von 60 runden und auf max 6h begrenzen
        remaining_seconds = min((remaining_seconds // 60) * 60, 21600)
        remaining_seconds = max(remaining_seconds, 60)

        _LOGGER.info("Starte Mäher für %s Sekunden (%s Min)", remaining_seconds, remaining_seconds // 60)
        success = await self._coordinator.async_send_command(
            "START_SECONDS_TO_OVERRIDE", remaining_seconds
        )
        if success:
            self._mowing_active = True
            self._fire_event("mowing_started")

    def _is_battery_sufficient(self) -> bool:
        """Prüft ob Akku den Mindestwert erreicht hat."""
        if not self._coordinator.data:
            return False
        battery_level = self._coordinator.data.get("battery_level", 0)
        battery_state = self._coordinator.data.get("battery_state", "")
        min_level = self._get_float(self._min_battery_eid, 95)
        # Akku muss >= Mindestwert UND nicht mehr laden (oder voll)
        return battery_level >= min_level and battery_state in ("OK", "CHARGING")

    def _has_enough_time(self) -> bool:
        """Prüft ob noch genug Zeit im Fenster."""
        if not self._window_end:
            return False
        min_remaining = self._get_float(self._min_remaining_eid, 30)
        remaining = (self._window_end - dt_util.now()).total_seconds() / 60
        return remaining >= min_remaining

    # ── Zustandsänderungen ────────────────────────────────────────────────────

    @callback
    def _handle_activity_change(self, event) -> None:
        """Mäher-Aktivität geändert."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if not new_state:
            return

        new_activity = new_state.state
        old_activity = old_state.state if old_state else None

        if new_activity in HOME_STATES and old_activity in MOWING_STATES:
            self._mowing_active = False
            _LOGGER.info("Mäher heimgekehrt")
            if not self._window_active:
                # Zeitfenster abgelaufen – Rolltor schließen
                self.hass.async_create_task(self._close_cover_if_configured())
            else:
                # Zeitfenster noch aktiv – auf vollen Akku warten
                _LOGGER.info("Zeitfenster noch aktiv – warte auf Akku")
                self._waiting_for_full_battery = True

        elif new_activity in MOWING_STATES and old_activity not in MOWING_STATES:
            self._mowing_active = True

    @callback
    def _handle_battery_change(self, event) -> None:
        """Akkustand geändert."""
        if not self._window_active or not self._waiting_for_full_battery or self._mowing_active:
            return

        if self._is_battery_sufficient():
            _LOGGER.info("Akku ausreichend – starte Mäher")
            self.hass.async_create_task(self._try_start_mowing())

    # ── Rolltor ───────────────────────────────────────────────────────────────

    async def _open_cover_if_configured(self) -> None:
        """Rolltor öffnen."""
        cover_entity = self._get_cover_entity_id()
        if not cover_entity:
            return

        state = self.hass.states.get(cover_entity)
        if not state:
            return

        if state.state == "open":
            self._cover_opened_by_us = False
            return

        await self.hass.services.async_call(
            "cover", "open_cover", {"entity_id": cover_entity}
        )
        self._cover_opened_by_us = True
        wait = self._get_float(self._cover_open_wait_eid, 30)
        await asyncio.sleep(wait)

    async def _close_cover_if_configured(self) -> None:
        """Rolltor schließen."""
        if not self._cover_opened_by_us:
            return

        cover_entity = self._get_cover_entity_id()
        if not cover_entity:
            return

        state = self.hass.states.get(cover_entity)
        if not state or state.state == "closed":
            return

        wait = self._get_float(self._cover_close_wait_eid, 60)
        await asyncio.sleep(wait)
        await self.hass.services.async_call(
            "cover", "close_cover", {"entity_id": cover_entity}
        )
        self._cover_opened_by_us = False
        self._fire_event("cover_closed")

    # ── Regen ─────────────────────────────────────────────────────────────────

    async def _is_raining_heavily(self) -> bool:
        """Starkregen prüfen."""
        rain_sensor = self._get_rain_sensor_entity_id()
        if not rain_sensor:
            return False

        state = self.hass.states.get(rain_sensor)
        if not state:
            return False

        try:
            precipitation = float(state.state)
            threshold = self._get_float(self._rain_threshold_eid, 2.5)
            return precipitation >= threshold
        except (ValueError, TypeError):
            return False

    def _fire_event(self, event_type: str, extra: dict | None = None) -> None:
        """HA-Event feuern."""
        self.hass.bus.async_fire(f"{DOMAIN}_{event_type}", extra or {})
