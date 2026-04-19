"""Gardena Sileno Integration für Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import GardenaCoordinator
from .mow_scheduler import GardenaScheduler

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button", "binary_sensor", "number", "switch", "select", "time"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration einrichten."""
    coordinator = GardenaCoordinator(hass, entry.data)
    await coordinator.async_config_entry_first_refresh()

    scheduler = GardenaScheduler(hass, coordinator, entry.entry_id)
    await scheduler.async_start()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "scheduler": scheduler,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Websocket erst nach Setup starten – nicht blockierend
    hass.async_create_task(coordinator.async_start_websocket())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration entladen."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator: GardenaCoordinator = data["coordinator"]
        scheduler: GardenaScheduler = data["scheduler"]

        if coordinator._ws_task and not coordinator._ws_task.done():
            coordinator._ws_task.cancel()

        await scheduler.async_stop()

    return unload_ok
