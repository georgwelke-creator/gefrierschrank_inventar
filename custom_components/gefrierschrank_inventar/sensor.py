"""Sensoren der Gefrierschrank-Inventar-Integration.

Ein Sensor pro Fach (Anzahl aktuell vorhandener Artikel, mit der Artikelliste
als Attribut fürs Dashboard) sowie ein Gesamt-Sensor. Aktualisierung erfolgt
per Dispatcher-Signal direkt nach jeder Änderung (kein Polling), das passt
zum iot_class "local_push" aus dem Manifest.
"""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_INVENTAR_AKTUALISIERT
from .storage import GefrierschrankStorage


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    storage: GefrierschrankStorage = hass.data[DOMAIN][entry.entry_id]["storage"]
    faecher = await storage.async_list_faecher()

    entities: list[SensorEntity] = [
        FachBestandSensor(entry, storage, fach.id, fach.name) for fach in faecher
    ]
    entities.append(GesamtBestandSensor(entry, storage))
    async_add_entities(entities)


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Gefrierschrank Inventar",
        manufacturer="Eigenbau",
        model="Gefrierschrank Inventar",
    )


class FachBestandSensor(SensorEntity):
    """Anzahl der aktuell vorhandenen Artikel in einem Fach."""

    _attr_should_poll = False
    _attr_native_unit_of_measurement = "Artikel"
    _attr_icon = "mdi:fridge-outline"

    def __init__(self, entry: ConfigEntry, storage: GefrierschrankStorage, fach_id: int, fach_name: str) -> None:
        self._storage = storage
        self._fach_id = fach_id
        self._attr_name = f"{fach_name} Bestand"
        self._attr_unique_id = f"{entry.entry_id}_fach_{fach_id}_bestand"
        self._attr_device_info = _device_info(entry)
        self._attr_extra_state_attributes: dict = {"fach_id": fach_id}

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_INVENTAR_AKTUALISIERT, self._async_aktualisieren)
        )
        await self._async_aktualisieren()

    async def _async_aktualisieren(self) -> None:
        eintraege = await self._storage.async_fach_bestand(self._fach_id)
        self._attr_native_value = len(eintraege)
        self._attr_extra_state_attributes = {
            "fach_id": self._fach_id,
            "artikel": [e.name for e in eintraege],
        }
        self.async_write_ha_state()


class GesamtBestandSensor(SensorEntity):
    """Gesamtanzahl aller aktuell vorhandenen Artikel im Gefrierschrank."""

    _attr_should_poll = False
    _attr_native_unit_of_measurement = "Artikel"
    _attr_icon = "mdi:snowflake"
    _attr_name = "Gefrierschrank Gesamtbestand"

    def __init__(self, entry: ConfigEntry, storage: GefrierschrankStorage) -> None:
        self._storage = storage
        self._attr_unique_id = f"{entry.entry_id}_gesamtbestand"
        self._attr_device_info = _device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_INVENTAR_AKTUALISIERT, self._async_aktualisieren)
        )
        await self._async_aktualisieren()

    async def _async_aktualisieren(self) -> None:
        self._attr_native_value = await self._storage.async_gesamt_anzahl()
        self.async_write_ha_state()
