# Gardena SILENO – Home Assistant Integration

Eine vollständige Home Assistant Custom Integration für den Gardena SILENO Mähroboter. Vollständige Steuerung ohne die Gardena App – inklusive intelligentem Zeitplan, automatischer Rolltor-Steuerung und Regensperre.

> ⚠️ **Inoffizielle Integration** – nicht von Gardena/Husqvarna unterstützt oder gesponsert.

---

## Features

- 🔄 **Echtzeit-Updates** via Gardena Websocket API (REST-Polling als Fallback)
- 📅 **Intelligenter Zeitplan** – vollständig in Home Assistant konfigurierbar, Gardena App wird nicht mehr benötigt
- 🔁 **Automatische Mähzyklen** – Mäher startet nach dem Laden selbständig neu solange das Zeitfenster aktiv ist
- 🚗 **Rolltor-Steuerung** – beliebige `cover` Entität aus HA wählbar (Shelly, Z-Wave, Zigbee, etc.)
- 🌧 **Regensperre** – Buienradar oder beliebiger Niederschlagssensor konfigurierbar
- 🔋 **Akkustandüberwachung** – konfigurierbarer Mindest-Akkustand zum Starten
- 📊 **Statistik-Sensoren** – geschätzte Lade- und Mähdauer aus historischen Daten
- 🌍 **Vollständige Fehlermeldungen** – über 50 Fehlercodes auf Deutsch übersetzt
- 📱 **Push-Benachrichtigungen** – über HA Mobile App (via Automationen)

---

## Voraussetzungen

- Home Assistant 2024.1 oder neuer
- Gardena Smart Gateway
- Gardena SILENO Mähroboter
- Account im [Husqvarna Developer Portal](https://developer.husqvarnagroup.cloud)

---

## Installation

### Manuell

1. Den Ordner `custom_components/gardena_sileno` in `/config/custom_components/` kopieren
2. Home Assistant neu starten
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Gardena SILENO**

### HACS

1. HACS öffnen → **Benutzerdefinierte Repositories**
2. URL eintragen: `https://github.com/112-christian-112/Gardena-Sileno`
3. Kategorie: **Integration**
4. Integration installieren und HA neu starten

---

## API-Zugangsdaten einrichten

1. Account anlegen auf [developer.husqvarnagroup.cloud](https://developer.husqvarnagroup.cloud)
2. Neue Application erstellen
3. Folgende APIs verbinden:
   - **Authentication API**
   - **GARDENA smart system API**
4. Application Key (Client ID) und Application Secret notieren

---

## Konfiguration

Die Integration wird vollständig über die Home Assistant Oberfläche konfiguriert – kein YAML erforderlich.

### Einrichtungs-Schritte

**Schritt 1 – API-Zugangsdaten**

| Feld | Beschreibung |
|------|-------------|
| Application Key | Client ID aus dem Developer Portal |
| Application Secret | Client Secret aus dem Developer Portal |

**Schritt 2 – Standort**

Automatische Erkennung aller verfügbaren Gardena-Standorte.

---

## Entitäten

### Sensoren

| Entität | Beschreibung |
|---------|-------------|
| `sensor.gardena_sileno_status` | Gerätestatus (OK / Warnung / Fehler) |
| `sensor.gardena_sileno_aktivitat` | Aktuelle Aktivität (Mähen, Laden, Geparkt...) |
| `sensor.gardena_sileno_letzter_fehler` | Letzter Fehlercode auf Deutsch |
| `sensor.gardena_sileno_akkustand` | Akkustand in % |
| `sensor.gardena_sileno_betriebsstunden` | Gesamtbetriebsstunden |
| `sensor.gardena_sileno_signalstarke` | WLAN-Signalstärke |
| `sensor.gardena_sileno_zeitplan_status` | Zeitplan-Status (nächste Mähzeit, Wartegrund...) |
| `sensor.gardena_sileno_geschatzte_ladezeit` | Geschätzte verbleibende Ladezeit |
| `sensor.gardena_sileno_geschatzte_mahdauer` | Geschätzte verbleibende Mähdauer |

### Binäre Sensoren

| Entität | Beschreibung |
|---------|-------------|
| `binary_sensor.gardena_sileno_online` | Gerät online/offline |

### Buttons

| Entität | Beschreibung |
|---------|-------------|
| `button.gardena_sileno_mahen_starten` | Mähvorgang für 1 Stunde starten |
| `button.gardena_sileno_parken_bis_nachster_timer` | Parken bis nächster Timer |
| `button.gardena_sileno_parken_dauerhaft` | Dauerhaft parken |
| `button.gardena_sileno_zeitplan_fortsetzen` | Zeitplan fortsetzen |

### Zeitplan-Steuerung

| Entität | Beschreibung | Standard |
|---------|-------------|---------|
| `switch.gardena_sileno_zeitplan_aktiv` | Zeitplan ein/aus | Aus |
| `switch.gardena_sileno_zeitfenster_1_aktiv` | Zeitfenster 1 ein/aus | Ein |
| `switch.gardena_sileno_zeitfenster_2_aktiv` | Zeitfenster 2 ein/aus | Aus |
| `time.gardena_sileno_zeitfenster_1_startzeit` | Startzeit Fenster 1 | 09:00 |
| `time.gardena_sileno_zeitfenster_1_endzeit` | Endzeit Fenster 1 | 12:00 |
| `time.gardena_sileno_zeitfenster_2_startzeit` | Startzeit Fenster 2 | 14:00 |
| `time.gardena_sileno_zeitfenster_2_endzeit` | Endzeit Fenster 2 | 17:00 |
| `select.gardena_sileno_mahtage` | Aktive Mähtage | Mo, Mi, Fr |

### Einstellungen

| Entität | Beschreibung | Standard |
|---------|-------------|---------|
| `number.gardena_sileno_mindest_akkustand_zum_starten` | Mindest-Akkustand für Start in % | 95% |
| `number.gardena_sileno_mindest_restzeit_im_zeitfenster` | Mindest-Restzeit im Fenster | 30 min |
| `select.gardena_sileno_rolltor` | Rolltor-Entität aus HA | Kein Rolltor |
| `number.gardena_sileno_rolltor_wartezeit_offnen` | Wartezeit nach Öffnen des Rolltors | 30 s |
| `number.gardena_sileno_rolltor_wartezeit_schliessen` | Wartezeit vor Schließen des Rolltors | 60 s |
| `select.gardena_sileno_regensensor` | Regensensor-Entität aus HA | Kein Sensor |
| `number.gardena_sileno_starkregen_schwellwert` | Starkregen-Schwellwert | 2.5 mm/h |

---

## Zeitplan-Logik

Der integrierte Scheduler ersetzt den Gardena App Zeitplan vollständig:

```
Zeitfenster startet (z.B. 09:00)
  │
  ├── Starkregen > Schwellwert? → Warten bis Regen aufhört
  ├── Akku < Mindestwert?       → Warten bis geladen
  └── Alles OK →
        Rolltor öffnen (falls konfiguriert)
        Mäher starten mit verbleibender Fensterzeit (max. 6h)
              │
              Mäher mäht...
              │
              └── Akku leer → heimfahren → laden
                    │
                    Akku >= Mindestwert?
                    ├── Ja + Zeitfenster noch aktiv →
                    │     Mäher wieder starten (Restzeit neu berechnet)
                    └── Zeitfenster abgelaufen →
                          Mäher dauerhaft parken
                          Rolltor schließen (nach konfigurierter Wartezeit)
```

Der Mäher startet mit dem Befehl `START_SECONDS_TO_OVERRIDE` und der verbleibenden Fensterzeit. Nach jedem Ladevorgang wird die verbleibende Zeit automatisch neu berechnet.

---

## Zeitplan-Status Sensor

Der Sensor `sensor.gardena_sileno_zeitplan_status` zeigt jederzeit den aktuellen Zustand:

| Anzeige | Bedeutung |
|---------|-----------|
| `Zeitfenster aktiv bis 12:00` | Mähvorgang läuft |
| `Warte auf Akku (89% von 95%)` | Lädt, wartet auf Mindestwert |
| `Pausiert wegen Regen (bis 12:00)` | Starkregen erkannt |
| `Nächste Mähzeit: Mo 09:00` | Kein aktives Fenster |
| `Zeitplan deaktiviert` | Zeitplan ausgeschaltet |
| `Keine Mähtage konfiguriert` | Konfiguration unvollständig |

---

## Push-Benachrichtigungen

Über HA-Automationen lassen sich Benachrichtigungen einrichten:

```yaml
alias: Gardena SILENO Benachrichtigungen
trigger:
  - platform: state
    entity_id: sensor.gardena_sileno_aktivitat
    not_to:
      - unavailable
      - unknown
  - platform: state
    entity_id: sensor.gardena_sileno_letzter_fehler
    not_to:
      - unavailable
      - unknown
      - Kein Fehler
action:
  - service: notify.mobile_app_DEIN_HANDY
    data:
      title: "🌿 Gardena SILENO"
      message: >
        {% if states('sensor.gardena_sileno_letzter_fehler') != 'Kein Fehler' %}
          ❌ Fehler: {{ states('sensor.gardena_sileno_letzter_fehler') }}
        {% else %}
          Aktivität: {{ states('sensor.gardena_sileno_aktivitat') }}
        {% endif %}
      data:
        click_action: homeassistant://navigate/gardena
```

---

## Rate-Limit

Die Gardena API erlaubt **10.000 Requests pro Monat** pro Application Key.

| Modus | Interval | Requests/Monat |
|-------|---------|----------------|
| Websocket aktiv | nur Heartbeat | ~720 |
| REST-Fallback | 30 Sekunden | ~86.400 ⚠️ |

**Empfehlung:** HA nicht zu häufig neu starten – jeder Start verbraucht einen Websocket-Request und mehrere REST-Calls.

---

## Bekannte Einschränkungen

- Websocket benötigt gültige API-Credentials mit entsprechenden Berechtigungen
- Statistik-Sensoren benötigen mindestens 3 vollständige Mähzyklen für eine erste Schätzung
- Bei intensivem REST-Polling (Websocket nicht verfügbar) kann das monatliche Rate-Limit erreicht werden

---

## Lizenz

MIT License – siehe [LICENSE](LICENSE)

---

## Danksagung

Inspiriert durch die originale [Gardena Smart System Integration](https://github.com/py-smart-gardena/hass-gardena-smart-system).
Basiert auf der offiziellen [Gardena Smart System API v2](https://developer.husqvarnagroup.cloud).
