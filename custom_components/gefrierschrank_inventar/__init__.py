"""Die Gefrierschrank-Inventar-Integration.

Phase 1 des Projekts: Datenmodell, lokale Speicherung und ein manuelles
Test-Interface über Home-Assistant-Services, ganz ohne Kamera oder
Spracheingabe. Die spätere Bild- und Sprach-Pipeline baut auf genau diesem
Datenmodell auf (siehe Projektdokumentation).
"""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
import voluptuous as vol

from .const import (
    ATTR_BEZUG_TYP,
    ATTR_BEZUG_WERT,
    ATTR_EINTRAG_ID,
    ATTR_FACH_ID,
    ATTR_KATEGORIE,
    ATTR_MENGE,
    ATTR_NAME,
    ATTR_NOTIZ,
    ATTR_QUELLE,
    ATTR_SCHWELLENWERT,
    BEZUG_TYPEN,
    CONF_ANZAHL_FAECHER,
    CONF_FACH_NAMEN,
    DB_DATEINAME,
    DOMAIN,
    QUELLE_MANUELL,
    SERVICE_EINLAGERN,
    SERVICE_ENTNEHMEN,
    SERVICE_MINDESTBESTAND_ENTFERNEN,
    SERVICE_MINDESTBESTAND_SETZEN,
    SIGNAL_INVENTAR_AKTUALISIERT,
)
from .storage import GefrierschrankStorage

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor"]

EINLAGERN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_FACH_ID): vol.Coerce(int),
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(ATTR_KATEGORIE): cv.string,
        vol.Optional(ATTR_MENGE, default=1): vol.Coerce(float),
        vol.Optional(ATTR_QUELLE, default=QUELLE_MANUELL): cv.string,
        vol.Optional(ATTR_NOTIZ): cv.string,
    }
)

ENTNEHMEN_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Optional(ATTR_EINTRAG_ID): vol.Coerce(int),
            vol.Optional(ATTR_FACH_ID): vol.Coerce(int),
            vol.Optional(ATTR_NAME): cv.string,
        },
        cv.has_at_least_one_key(ATTR_EINTRAG_ID, ATTR_FACH_ID),
    )
)

MINDESTBESTAND_SETZEN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_BEZUG_TYP): vol.In(BEZUG_TYPEN),
        vol.Required(ATTR_BEZUG_WERT): cv.string,
        vol.Required(ATTR_SCHWELLENWERT): vol.Coerce(float),
    }
)

MINDESTBESTAND_ENTFERNEN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_BEZUG_TYP): vol.In(BEZUG_TYPEN),
        vol.Required(ATTR_BEZUG_WERT): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Richtet die Integration für einen Config-Entry ein."""
    db_path = Path(hass.config.path(".storage")) / DB_DATEINAME
    storage = GefrierschrankStorage(db_path)
    await storage.async_init()

    # Fächer beim allerersten Start aus den Einrichtungsdaten anlegen.
    # Idempotent: bei einem Neustart/Reload sind schon Fächer vorhanden.
    vorhandene_faecher = await storage.async_list_faecher()
    if not vorhandene_faecher:
        fach_namen = entry.data.get(CONF_FACH_NAMEN, [])
        for position, name in enumerate(fach_namen, start=1):
            await storage.async_add_fach(name=name, typ="offen", position=position)
        _LOGGER.info(
            "Gefrierschrank Inventar: %d Fächer angelegt (%s)",
            len(fach_namen),
            ", ".join(fach_namen),
        )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"storage": storage}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_register_services(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entlädt einen Config-Entry wieder."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["storage"].async_close()
    return unload_ok


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Fügt ein über den Options-Flow nachträglich angelegtes Fach hinzu."""
    storage: GefrierschrankStorage = hass.data[DOMAIN][entry.entry_id]["storage"]
    neuer_name = entry.options.get("weiteres_fach_name")
    if not neuer_name:
        return
    vorhandene = await storage.async_list_faecher()
    if any(f.name == neuer_name for f in vorhandene):
        return  # schon angelegt, z. B. nach einem Neustart
    naechste_position = max((f.position for f in vorhandene), default=0) + 1
    await storage.async_add_fach(name=neuer_name, typ="offen", position=naechste_position)
    async_dispatcher_send(hass, SIGNAL_INVENTAR_AKTUALISIERT)
    _LOGGER.info("Gefrierschrank Inventar: zusätzliches Fach '%s' angelegt", neuer_name)


def _async_register_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    storage: GefrierschrankStorage = hass.data[DOMAIN][entry.entry_id]["storage"]

    async def async_einlagern(call: ServiceCall) -> None:
        await storage.async_einlagern(
            fach_id=call.data[ATTR_FACH_ID],
            name=call.data[ATTR_NAME],
            kategorie=call.data.get(ATTR_KATEGORIE),
            menge=call.data.get(ATTR_MENGE, 1),
            quelle=call.data.get(ATTR_QUELLE, QUELLE_MANUELL),
            notiz=call.data.get(ATTR_NOTIZ),
        )
        async_dispatcher_send(hass, SIGNAL_INVENTAR_AKTUALISIERT)

    async def async_entnehmen(call: ServiceCall) -> None:
        if ATTR_EINTRAG_ID in call.data:
            erfolgreich = await storage.async_entnehmen(call.data[ATTR_EINTRAG_ID])
        else:
            eintrag_id = await storage.async_entnehmen_by_name(
                fach_id=call.data[ATTR_FACH_ID], name=call.data.get(ATTR_NAME, "")
            )
            erfolgreich = eintrag_id is not None
        if not erfolgreich:
            _LOGGER.warning(
                "Gefrierschrank Inventar: kein passender vorhandener Artikel zum Entnehmen gefunden (%s)",
                dict(call.data),
            )
        async_dispatcher_send(hass, SIGNAL_INVENTAR_AKTUALISIERT)

    async def async_mindestbestand_setzen(call: ServiceCall) -> None:
        await storage.async_mindestbestand_setzen(
            bezug_typ=call.data[ATTR_BEZUG_TYP],
            bezug_wert=call.data[ATTR_BEZUG_WERT],
            schwellenwert=call.data[ATTR_SCHWELLENWERT],
        )
        async_dispatcher_send(hass, SIGNAL_INVENTAR_AKTUALISIERT)

    async def async_mindestbestand_entfernen(call: ServiceCall) -> None:
        await storage.async_mindestbestand_entfernen(
            bezug_typ=call.data[ATTR_BEZUG_TYP], bezug_wert=call.data[ATTR_BEZUG_WERT]
        )
        async_dispatcher_send(hass, SIGNAL_INVENTAR_AKTUALISIERT)

    hass.services.async_register(DOMAIN, SERVICE_EINLAGERN, async_einlagern, schema=EINLAGERN_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_ENTNEHMEN, async_entnehmen, schema=ENTNEHMEN_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_MINDESTBESTAND_SETZEN, async_mindestbestand_setzen, schema=MINDESTBESTAND_SETZEN_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MINDESTBESTAND_ENTFERNEN,
        async_mindestbestand_entfernen,
        schema=MINDESTBESTAND_ENTFERNEN_SCHEMA,
    )
