"""Sensoren für Gardena Sileno Integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GardenaCoordinator
from .statistics_sensor import GardenaChargingTimeSensor, GardenaMowingTimeSensor

_LOGGER = logging.getLogger(__name__)


@dataclass
class GardenaSensorEntityDescription(SensorEntityDescription):
    """Beschreibung für Gardena Sensoren."""
    data_key: str = ""
    attr_keys: list[str] | None = None


SENSOR_DESCRIPTIONS: tuple[GardenaSensorEntityDescription, ...] = (
    GardenaSensorEntityDescription(
        key="state",
        name="Status",
        icon="mdi:robot-mower",
        data_key="state",
        attr_keys=["state_raw"],
    ),
    GardenaSensorEntityDescription(
        key="activity",
        name="Aktivität",
        icon="mdi:robot-mower-outline",
        data_key="activity",
        attr_keys=["activity_raw"],
    ),
    GardenaSensorEntityDescription(
        key="error",
        name="Letzter Fehler",
        icon="mdi:alert-circle",
        data_key="error",
        attr_keys=["error_code", "error_timestamp"],
    ),
    GardenaSensorEntityDescription(
        key="battery_level",
        name="Akkustand",
        icon="mdi:battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        data_key="battery_level",
        attr_keys=["battery_state"],
    ),
    GardenaSensorEntityDescription(
        key="operating_hours",
        name="Betriebsstunden",
        icon="mdi:clock-outline",
        native_unit_of_measurement="h",
        state_class=SensorStateClass.TOTAL_INCREASING,
        data_key="operating_hours",
    ),
    GardenaSensorEntityDescription(
        key="rf_link_level",
        name="Signalstärke",
        icon="mdi:signal",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        data_key="rf_link_level",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensoren einrichten."""
    coordinator: GardenaCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = [
        GardenaSensor(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS
    ]

    # Statistik-Sensoren hinzufügen
    entities.extend([
        GardenaChargingTimeSensor(hass, coordinator, entry),
        GardenaMowingTimeSensor(hass, coordinator, entry),
    ])

    # Scheduler-Status-Sensor
    scheduler = hass.data[DOMAIN][entry.entry_id]["scheduler"]
    entities.append(GardenaSchedulerStatusSensor(hass, coordinator, scheduler, entry))

    async_add_entities(entities)


class GardenaSensor(CoordinatorEntity[GardenaCoordinator], SensorEntity):
    """Gardena Sensor Entität."""

    entity_description: GardenaSensorEntityDescription

    def __init__(
        self,
        coordinator: GardenaCoordinator,
        description: GardenaSensorEntityDescription,
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
        data = self.coordinator.data or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"Gardena {data.get('name', 'SILENO')}",
            manufacturer="Gardena",
            model=data.get("model_type", "SILENO"),
            serial_number=data.get("serial", None),
        )

    @property
    def native_value(self) -> Any:
        """Aktueller Wert."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.data_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zusätzliche Attribute."""
        if not self.coordinator.data or not self.entity_description.attr_keys:
            return {}
        return {
            key: self.coordinator.data.get(key)
            for key in self.entity_description.attr_keys
            if key in self.coordinator.data
        }


class GardenaSchedulerStatusSensor(SensorEntity):
    """Sensor für den aktuellen Zeitplan-Status."""

    _attr_name = "Zeitplan Status"
    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: GardenaCoordinator,
        scheduler,
        entry: ConfigEntry,
    ) -> None:
        """Initialisierung."""
        self.hass = hass
        self._coordinator = coordinator
        self._scheduler = scheduler
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_scheduler_status"

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

    @property
    def native_value(self) -> str:
        """Aktueller Zeitplan-Status als lesbarer Text."""
        try:
            from homeassistant.util import dt as dt_util
            scheduler = self._scheduler

            if not scheduler._is_on(scheduler._schedule_enabled_eid):
                return "Zeitplan deaktiviert"

            if scheduler._window_active and scheduler._window_end:
                end_str = scheduler._window_end.strftime("%H:%M")
                if scheduler._mowing_active:
                    return f"Zeitfenster aktiv bis {end_str}"
                elif scheduler._rain_paused:
                    return f"Pausiert wegen Regen (bis {end_str})"
                elif scheduler._waiting_for_full_battery:
                    battery = self._coordinator.data.get("battery_level", 0) if self._coordinator.data else 0
                    min_bat = int(scheduler._get_float(scheduler._min_battery_eid, 95))
                    return f"Warte auf Akku ({battery}% von {min_bat}%)"
                else:
                    return f"Zeitfenster aktiv bis {end_str}"

            return self._get_next_schedule_text()
        except Exception as e:
            return f"Fehler: {e}"

    def _get_next_schedule_text(self) -> str:
        """Nächsten Mähtermin berechnen."""
        from homeassistant.util import dt as dt_util
        from datetime import timedelta

        scheduler = self._scheduler
        now = dt_util.now()

        active_days = scheduler._get_active_weekdays()
        if not active_days:
            return "Keine Mähtage konfiguriert"

        day_names = {
            "mon": "Mo", "tue": "Di", "wed": "Mi",
            "thu": "Do", "fri": "Fr", "sat": "Sa", "sun": "So"
        }
        weekday_to_key = {
            0: "mon", 1: "tue", 2: "wed", 3: "thu",
            4: "fri", 5: "sat", 6: "sun"
        }

        # Zeitfenster sammeln
        windows = []
        if scheduler._is_on(scheduler._window_1_enabled_eid):
            t = scheduler._get_time(scheduler._start_1_eid)
            if t:
                windows.append(t)
        if scheduler._is_on(scheduler._window_2_enabled_eid):
            t = scheduler._get_time(scheduler._start_2_eid)
            if t:
                windows.append(t)

        if not windows:
            return "Keine Zeitfenster aktiv"

        # Nächsten Termin in den nächsten 7 Tagen suchen
        for days_ahead in range(8):
            check_date = now + timedelta(days=days_ahead)
            check_key = weekday_to_key.get(check_date.weekday())

            if check_key not in active_days:
                continue

            for window_time in sorted(windows):
                candidate = check_date.replace(
                    hour=window_time.hour,
                    minute=window_time.minute,
                    second=0,
                    microsecond=0,
                )
                if candidate > now:
                    day_label = "Heute" if days_ahead == 0 else (
                        "Morgen" if days_ahead == 1 else
                        day_names.get(check_key, check_key)
                    )
                    return f"Nächste Mähzeit: {day_label} {window_time.strftime('%H:%M')}"

        return "Kein Termin in den nächsten 7 Tagen"

    @property
    def extra_state_attributes(self) -> dict:
        """Zusätzliche Attribute."""
        scheduler = self._scheduler
        return {
            "fenster_aktiv": scheduler._window_active,
            "maeht": scheduler._mowing_active,
            "regen_pause": scheduler._rain_paused,
            "warte_auf_akku": scheduler._waiting_for_full_battery,
            "fenster_ende": scheduler._window_end.isoformat() if scheduler._window_end else None,
        }

    async def async_update(self) -> None:
        """Wird automatisch aktualisiert."""
        self.async_write_ha_state()
