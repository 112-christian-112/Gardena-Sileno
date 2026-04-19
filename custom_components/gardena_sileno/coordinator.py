"""Coordinator für Gardena Sileno Integration."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    AUTH_URL,
    API_BASE_URL,
    WEBSOCKET_URL,
    UPDATE_INTERVAL,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_LOCATION_ID,
    MOWER_ERROR_CODES,
    MOWER_ACTIVITY_TEXTS,
    MOWER_STATE_TEXTS,
)

_LOGGER = logging.getLogger(__name__)


class GardenaCoordinator(DataUpdateCoordinator):
    """Koordinator für Gardena API – Websocket + REST Fallback."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialisierung."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self._client_id = config[CONF_CLIENT_ID]
        self._client_secret = config[CONF_CLIENT_SECRET]
        self._location_id = config[CONF_LOCATION_ID]
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ws_task: asyncio.Task | None = None
        self._mower_data: dict = {}
        self._common_data: dict = {}

    # ── Token Management ──────────────────────────────────────────────────────

    async def async_get_token(self) -> bool:
        """Neuen Token per client_credentials holen."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                AUTH_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error("Token-Request fehlgeschlagen: %s", resp.status)
                    return False
                data = await resp.json()
                if "access_token" not in data:
                    return False
                self._access_token = data["access_token"]
                _LOGGER.debug("Token erfolgreich geholt")
                return True
        except Exception as e:
            _LOGGER.error("Token-Request Exception: %s", e)
            return False

    async def async_refresh_token(self) -> bool:
        """Token erneuern."""
        if not self._refresh_token:
            return await self.async_get_token()

        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                AUTH_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": self._refresh_token,
                },
            ) as resp:
                if resp.status != 200:
                    return await self.async_get_token()
                data = await resp.json()
                if "access_token" not in data:
                    return await self.async_get_token()
                self._access_token = data["access_token"]
                if "refresh_token" in data:
                    self._refresh_token = data["refresh_token"]
                return True
        except Exception:
            return await self.async_get_token()

    # ── REST API ──────────────────────────────────────────────────────────────

    async def async_fetch_data(self) -> dict:
        """Daten per REST API holen."""
        if not self._access_token:
            if not await self.async_get_token():
                raise UpdateFailed("Token konnte nicht geholt werden")

        session = async_get_clientsession(self.hass)

        try:
            async with session.get(
                f"{API_BASE_URL}/locations/{self._location_id}",
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "X-Api-Key": self._client_id,
                },
            ) as resp:
                if resp.status == 401:
                    _LOGGER.debug("Token abgelaufen, erneuere...")
                    if not await self.async_refresh_token():
                        raise UpdateFailed("Token-Erneuerung fehlgeschlagen")
                    async with session.get(
                        f"{API_BASE_URL}/locations/{self._location_id}",
                        headers={
                            "Authorization": f"Bearer {self._access_token}",
                            "X-Api-Key": self._client_id,
                        },
                    ) as resp2:
                        data = await resp2.json()
                else:
                    data = await resp.json()

            return self._parse_data(data)

        except UpdateFailed:
            raise
        except Exception as e:
            raise UpdateFailed(f"API-Fehler: {e}") from e

    def _parse_data(self, raw: dict) -> dict:
        """Rohdaten in lesbare Werte umwandeln."""
        mower = {}
        common = {}

        for item in raw.get("included", []):
            if item.get("type") == "MOWER":
                mower = item.get("attributes", {})
            elif item.get("type") == "COMMON":
                common = item.get("attributes", {})

        self._mower_data = mower
        self._common_data = common

        state = mower.get("state", {}).get("value", "UNAVAILABLE")
        activity = mower.get("activity", {}).get("value", "NONE")
        error_code = mower.get("lastErrorCode", {}).get("value", "NO_MESSAGE")

        return {
            "state": MOWER_STATE_TEXTS.get(state, state),
            "state_raw": state,
            "activity": MOWER_ACTIVITY_TEXTS.get(activity, activity),
            "activity_raw": activity,
            "error": MOWER_ERROR_CODES.get(error_code, error_code),
            "error_code": error_code,
            "error_timestamp": mower.get("lastErrorCode", {}).get("timestamp", ""),
            "operating_hours": mower.get("operatingHours", {}).get("value", 0),
            "battery_level": common.get("batteryLevel", {}).get("value", 0),
            "battery_state": common.get("batteryState", {}).get("value", "UNKNOWN"),
            "rf_link_level": common.get("rfLinkLevel", {}).get("value", 0),
            "online": common.get("rfLinkState", {}).get("value", "UNKNOWN") == "ONLINE",
            "name": common.get("name", {}).get("value", "SILENO"),
            "serial": common.get("serial", {}).get("value", None),
            "model_type": common.get("modelType", {}).get("value", "GARDENA smart Mower"),
        }

    # ── Websocket ─────────────────────────────────────────────────────────────

    async def async_start_websocket(self) -> None:
        """Websocket-Verbindung starten."""
        if self._ws_task and not self._ws_task.done():
            return
        self._ws_task = self.hass.async_create_task(self._ws_listen())

    async def _get_websocket_url(self) -> str | None:
        """Websocket-URL von der API holen."""
        if not self._access_token:
            if not await self.async_get_token():
                return None

        session = async_get_clientsession(self.hass)
        try:
            payload = {
                "data": {
                    "type": "WEBSOCKET",
                    "attributes": {
                        "locationId": self._location_id
                    }
                }
            }
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Authorization-Provider": "husqvarna",
                "X-Api-Key": self._client_id,
                "Content-Type": "application/vnd.api+json",
            }
            async with session.post(
                f"{API_BASE_URL}/websocket",
                headers=headers,
                json=payload,
            ) as resp:
                if resp.status == 401:
                    await self.async_refresh_token()
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    async with session.post(
                        f"{API_BASE_URL}/websocket",
                        headers=headers,
                        json=payload,
                    ) as resp2:
                        data = await resp2.json()
                        resp = resp2
                else:
                    data = await resp.json()

                if resp.status == 201:
                    url = data.get("data", {}).get("attributes", {}).get("url")
                    _LOGGER.debug("Websocket URL erhalten: %s", url)
                    return url
                else:
                    _LOGGER.debug("Websocket Response %s: %s", resp.status, data)
                    return None
        except Exception as e:
            _LOGGER.error("Websocket-URL Fehler: %s", e)
            return None

    async def _ws_listen(self) -> None:
        """Websocket-Verbindung aufrechterhalten und Nachrichten verarbeiten."""
        while True:
            try:
                ws_url = await self._get_websocket_url()
                if not ws_url:
                    _LOGGER.debug("Keine Websocket-URL verfügbar – REST polling aktiv")
                    await asyncio.sleep(300)
                    continue

                session = async_get_clientsession(self.hass)
                _LOGGER.info("Verbinde mit Gardena Websocket...")

                async with session.ws_connect(ws_url) as ws:
                    self._ws = ws
                    _LOGGER.info("Gardena Websocket verbunden")

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_ws_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            _LOGGER.error("Websocket Fehler: %s", ws.exception())
                            break
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            _LOGGER.warning("Websocket geschlossen")
                            break

            except asyncio.CancelledError:
                _LOGGER.debug("Websocket Task abgebrochen")
                return
            except Exception as e:
                _LOGGER.error("Websocket Exception: %s", e)

            _LOGGER.info("Websocket getrennt, reconnect in 30s...")
            await asyncio.sleep(30)

    async def _handle_ws_message(self, raw: str) -> None:
        """Websocket-Nachricht verarbeiten."""
        try:
            data = json.loads(raw)

            # Ping/Pong Handler (Original-Integration Protokoll)
            if "data" in data:
                inner = data["data"]
                if isinstance(inner, dict) and inner.get("type") == "WEBSOCKET_PING":
                    if self._ws:
                        pong = {"data": {"type": "WEBSOCKET_PONG", "attributes": {}}}
                        await self._ws.send_str(json.dumps(pong))
                        _LOGGER.debug("Pong gesendet")
                    return

            msg_type = data.get("type")

            if msg_type == "MOWER":
                attrs = data.get("attributes", {})
                for key, value in attrs.items():
                    self._mower_data[key] = value
                _LOGGER.debug("Mäher-Update via Websocket: %s", attrs)
                self.async_set_updated_data(self._build_state())

            elif msg_type == "COMMON":
                attrs = data.get("attributes", {})
                for key, value in attrs.items():
                    self._common_data[key] = value
                self.async_set_updated_data(self._build_state())

            else:
                _LOGGER.debug("Unbekannte Websocket-Nachricht: %s", msg_type)

        except json.JSONDecodeError:
            _LOGGER.warning("Ungültige Websocket-Nachricht: %s", raw)
        except Exception as e:
            _LOGGER.error("Fehler beim Verarbeiten der Websocket-Nachricht: %s", e)

    def _build_state(self) -> dict:
        """Aktuellen State aus gecachten Daten bauen."""
        mower = self._mower_data
        common = self._common_data

        state = mower.get("state", {}).get("value", "UNAVAILABLE")
        activity = mower.get("activity", {}).get("value", "NONE")
        error_code = mower.get("lastErrorCode", {}).get("value", "NO_MESSAGE")

        return {
            "state": MOWER_STATE_TEXTS.get(state, state),
            "state_raw": state,
            "activity": MOWER_ACTIVITY_TEXTS.get(activity, activity),
            "activity_raw": activity,
            "error": MOWER_ERROR_CODES.get(error_code, error_code),
            "error_code": error_code,
            "error_timestamp": mower.get("lastErrorCode", {}).get("timestamp", ""),
            "operating_hours": mower.get("operatingHours", {}).get("value", 0),
            "battery_level": common.get("batteryLevel", {}).get("value", 0),
            "battery_state": common.get("batteryState", {}).get("value", "UNKNOWN"),
            "rf_link_level": common.get("rfLinkLevel", {}).get("value", 0),
            "online": common.get("rfLinkState", {}).get("value", "UNKNOWN") == "ONLINE",
            "name": common.get("name", {}).get("value", "SILENO"),
        }

    # ── Steuerung ─────────────────────────────────────────────────────────────

    async def async_send_command(self, command: str, duration: int = 0) -> bool:
        """Befehl an Mähroboter senden."""
        if not self._access_token:
            if not await self.async_get_token():
                return False

        # Geräte-ID aus Location-Daten holen
        import json as json_lib
        device_id = "59a1f729-9978-42ad-843a-b33a19e8d80b"

        payload: dict[str, Any] = {
            "data": {
                "id": "request-1",
                "type": "MOWER_CONTROL",
                "attributes": {
                    "command": command,
                },
            }
        }

        if duration > 0:
            payload["data"]["attributes"]["seconds"] = duration

        session = async_get_clientsession(self.hass)
        try:
            async with session.put(
                f"{API_BASE_URL}/command/{device_id}",
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Authorization-Provider": "husqvarna",
                    "X-Api-Key": self._client_id,
                    "Content-Type": "application/vnd.api+json",
                },
                data=json_lib.dumps(payload),
            ) as resp:
                if resp.status == 401:
                    await self.async_refresh_token()
                    # Nochmal versuchen
                    return await self.async_send_command(command, duration)

                if resp.status in (200, 201, 202, 204):
                    _LOGGER.info("Befehl '%s' erfolgreich gesendet", command)
                    return True

                error_text = await resp.text()
                _LOGGER.error("Befehl fehlgeschlagen: %s – %s", resp.status, error_text)
                return False

        except Exception as e:
            _LOGGER.error("Fehler beim Senden des Befehls: %s", e)
            return False

    # ── DataUpdateCoordinator ─────────────────────────────────────────────────

    async def _async_update_data(self) -> dict:
        """Daten aktualisieren – wird vom Coordinator aufgerufen."""
        return await self.async_fetch_data()
