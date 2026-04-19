"""Konstanten für Gardena Sileno Integration."""

DOMAIN = "gardena_sileno"

# Konfigurationsschlüssel
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_LOCATION_ID = "location_id"

# API URLs
AUTH_URL = "https://api.authentication.husqvarnagroup.dev/v1/oauth2/token"
API_BASE_URL = "https://api.smart.gardena.dev/v2"
WEBSOCKET_URL = "https://api.smart.gardena.dev/v2/websocket"

# Update Interval als Fallback (Sekunden)
UPDATE_INTERVAL = 300

# Fehlercodes Deutsch
MOWER_ERROR_CODES = {
    "NO_MESSAGE": "Kein Fehler",
    "OUTSIDE_WORKING_AREA": "Außerhalb des Arbeitsbereichs",
    "NO_LOOP_SIGNAL": "Kein Schleifensignal",
    "WRONG_LOOP_SIGNAL": "Falsches Schleifensignal",
    "LOOP_SENSOR_PROBLEM_FRONT": "Frontschleifensensor defekt",
    "LOOP_SENSOR_PROBLEM_REAR": "Heckschleifensensor defekt",
    "LEFT_LOOP_SENSOR": "Linker Schleifensensor defekt",
    "RIGHT_LOOP_SENSOR": "Rechter Schleifensensor defekt",
    "WRONG_PIN": "Falscher PIN",
    "TRAPPED": "Feststeckend",
    "UPSIDE_DOWN": "Umgekippt",
    "LOW_BATTERY": "Niedriger Akkustand",
    "EMPTY_BATTERY": "Akku leer",
    "NO_DRIVE": "Kein Antrieb",
    "TEMPORARY_LIFT": "Vorübergehend angehoben",
    "LIFTED": "Angehoben",
    "STUCK_IN_CHARGING_STATION": "In Ladestation feststeckend",
    "CHARGING_STATION_BLOCKED": "Ladestation blockiert",
    "COLLISION_SENSOR_PROBLEM_REAR": "Heck-Kollisionssensor defekt",
    "COLLISION_SENSOR_PROBLEM_FRONT": "Front-Kollisionssensor defekt",
    "WHEEL_MOTOR_BLOCKED_RIGHT": "Rechter Radmotor blockiert",
    "WHEEL_MOTOR_BLOCKED_LEFT": "Linker Radmotor blockiert",
    "WHEEL_DRIVE_PROBLEM_RIGHT": "Rechtes Radantriebssystem defekt",
    "WHEEL_DRIVE_PROBLEM_LEFT": "Linkes Radantriebssystem defekt",
    "CUTTING_DRIVE": "Mähmotor defekt",
    "CUTTING_SYSTEM_BLOCKED": "Mähwerk blockiert",
    "ELECTRONIC_PROBLEM": "Elektronikproblem",
    "STEEP_SLOPE": "Zu steile Steigung",
    "CHARGING_SYSTEM_PROBLEM": "Ladesystemproblem",
    "STOP_BUTTON_FAIL": "Start/Stop-Taste defekt",
    "TILT_SENSOR_PROBLEM": "Neigungssensor defekt",
    "MOWER_TILTED": "Maximaler Neigungswinkel erreicht",
    "WHEEL_MOTOR_OVERLOADED_RIGHT": "Rechtes Rad überlastet",
    "WHEEL_MOTOR_OVERLOADED_LEFT": "Linkes Rad überlastet",
    "CUTTING_OVERLOAD": "Mähwerk überlastet",
    "BATTERY_PROBLEM": "Akkuproblem",
    "ALARM_MOWER_SWITCHED_OFF": "Alarm: Hauptschalter ausgeschaltet",
    "ALARM_MOWER_STOPPED": "Alarm: Stopp-Taste gedrückt",
    "ALARM_MOWER_LIFTED": "Alarm: Mäher angehoben",
    "ALARM_MOWER_TILTED": "Alarm: Mäher umgekippt",
    "ALARM_MOTION": "Alarm: Bewegung erkannt",
    "ALARM_GEOFENCE": "Alarm: Außerhalb des Geofence",
    "SLIPPED": "Gerutscht",
    "GPS_TRACKER_MODULE_ERROR": "GPS-Signalfehler",
    "WEAK_GPS_SIGNAL": "Schwaches GPS-Signal",
    "DIFFICULT_FINDING_HOME": "Schwierigkeiten beim Heimfinden",
    "LOOP_WIRE_BROKEN": "Begrenzungskabel unterbrochen",
    "COLLISION_SENSOR_ERROR": "Kollisionssensor defekt",
    "BATTERY_NEAR_END_OF_LIFE": "Akku fast am Ende der Lebensdauer",
    "BATTERY_FET_ERROR": "Akkuproblem (BMS)",
    "NO_CHARGING_STATION_SIGNAL": "Ladestation nicht verbunden",
    "RADAR_ERROR": "Radarsensorfehler",
    "MAP_NOT_VALID": "Karte ungültig",
    "WAIT_UPDATING": "Firmware-Update läuft",
    "WAIT_POWER_UP": "Mäher startet",
    "OFF_DISABLED": "Mäher deaktiviert",
    "OFF_HATCH_OPEN": "Klappe offen",
    "OFF_HATCH_CLOSED": "Klappe geschlossen",
    "PARKED_DAILY_LIMIT_REACHED": "Tageslimit erreicht",
    "UNKNOWN": "Unbekannter Fehler",
}

# Aktivitätscodes Deutsch
MOWER_ACTIVITY_TEXTS = {
    "PAUSED": "Pausiert",
    "PAUSED_IN_CS": "Pausiert in Ladestation",
    "OK_CUTTING": "Mähen (Zeitplan)",
    "OK_CUTTING_TIMER_OVERRIDDEN": "Mähen (manuell)",
    "OK_SEARCHING": "Sucht Ladestation",
    "OK_LEAVING": "Verlässt Ladestation",
    "OK_CHARGING": "Lädt (Akku zu niedrig)",
    "PARKED_TIMER": "Geparkt (Timer)",
    "PARKED_PARK_SELECTED": "Geparkt (manuell)",
    "PARKED_AUTOTIMER": "Geparkt (Gras zu niedrig)",
    "PARKED_FROST": "Geparkt (Frost)",
    "PARKED_NO_LIGHT": "Geparkt (zu dunkel)",
    "PARKED_MOWING_COMPLETED": "Geparkt (Mähen abgeschlossen)",
    "PARKED_RAIN": "Geparkt (Regen)",
    "STOPPED_IN_GARDEN": "Gestoppt im Garten",
    "INITIATE_NEXT_ACTION": "Bereitet nächste Aktion vor",
    "SEARCHING_FOR_SATELLITES": "Sucht GPS-Satelliten",
    "NONE": "Keine Aktivität",
}

# Statuscodes Deutsch
MOWER_STATE_TEXTS = {
    "OK": "OK",
    "WARNING": "Warnung",
    "ERROR": "Fehler",
    "UNAVAILABLE": "Nicht verfügbar",
}

# Mäher-Befehle
COMMAND_START_SECONDS_TO_OVERRIDE = "START_SECONDS_TO_OVERRIDE"
COMMAND_PARK_UNTIL_NEXT_TASK = "PARK_UNTIL_NEXT_TASK"
COMMAND_PARK_UNTIL_FURTHER_NOTICE = "PARK_UNTIL_FURTHER_NOTICE"
COMMAND_RESUME_SCHEDULE = "RESUME_SCHEDULE"

# Options Flow Konfigurationsschlüssel
CONF_COVER_ENTITY = "cover_entity"
CONF_COVER_OPEN_WAIT = "cover_open_wait"
CONF_COVER_CLOSE_WAIT = "cover_close_wait"
CONF_RAIN_SENSOR = "rain_sensor"
CONF_RAIN_THRESHOLD = "rain_threshold"
CONF_SCHEDULE_ENABLED = "schedule_enabled"
CONF_SCHEDULE_DAYS = "schedule_days"
CONF_SCHEDULE_TIME_1 = "schedule_time_1"
CONF_SCHEDULE_TIME_2 = "schedule_time_2"
CONF_SCHEDULE_TIME_1_ENABLED = "schedule_time_1_enabled"
CONF_SCHEDULE_TIME_2_ENABLED = "schedule_time_2_enabled"

# Wochentage
WEEKDAYS = {
    "mon": "Montag",
    "tue": "Dienstag",
    "wed": "Mittwoch",
    "thu": "Donnerstag",
    "fri": "Freitag",
    "sat": "Samstag",
    "sun": "Sonntag",
}

# Python weekday() → Kürzel
WEEKDAY_MAP = {
    0: "mon",
    1: "tue",
    2: "wed",
    3: "thu",
    4: "fri",
    5: "sat",
    6: "sun",
}

# Neue Schedule-Konstanten
CONF_SCHEDULE_END_TIME_1 = "schedule_end_time_1"
CONF_SCHEDULE_END_TIME_2 = "schedule_end_time_2"
CONF_MIN_REMAINING_MINUTES = "min_remaining_minutes"
