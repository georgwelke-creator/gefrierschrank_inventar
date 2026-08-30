"""Mindestbestand-Warnsensor.

Phase 1 legt hier nur die einfache, aggregierte Variante an (ein Sensor,
der 'an' ist, sobald irgendeine Regel unterschritten ist, mit der Liste der
betroffenen Regeln als Attribut). Eine feinere Aufteilung mit eigener
Benachrichtigung pro Regel ist laut Umsetzungsplan Phase 7.
"""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_INVENTAR_AKTUALISIERT
from .sensor import _device_info
from .storage import GefrierschrankStorage


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    storage: GefrierschrankStorage = hass.data[DOMAIN][entry.entry_id]["storage"]
    async_add_entities([MindestbestandWarnSensor(entry, storage)])


class MindestbestandWarnSensor(BinarySensorEntity):
    """An, sobald mindestens eine Mindestbestand-Regel unterschritten ist."""

    _attr_should_poll = False
    _attr_icon = "mdi:alert-circle-outline"
    _attr_name = "Gefrierschrank Mindestbestand unterschritten"

    def __init__(self, entry: ConfigEntry, storage: GefrierschrankStorage) -> None:
        self._storage = storage
        self._attr_unique_id = f"{entry.entry_id}_mindestbestand_warnung"
        self._attr_device_info = _device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_INVENTAR_AKTUALISIERT, self._async_aktualisieren)
        )
        await self._async_aktualisieren()

    async def _async_aktualisieren(self) -> None:
        unterschritten = await self._storage.async_unterschrittene_regeln()
        self._attr_is_on = len(unterschritten) > 0
        self._attr_extra_state_attributes = {
            "betroffen": [
                f"{r.bezug_typ}={r.bezug_wert} ({r.aktueller_bestand}/{r.schwellenwert})"
                for r in unterschritten
            ]
        }
        self.async_write_ha_state()
