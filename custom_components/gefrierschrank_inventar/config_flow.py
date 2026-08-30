"""Config-Flow für die Gefrierschrank-Inventar-Integration.

Zweistufig: zuerst die Anzahl der Fächer, danach ein Name pro Fach
(vorbelegt mit "Fach 1", "Fach 2", ...). Der Typ (offene Ablage oder
Schublade) ist hier bewusst nicht Teil der Einrichtung, sondern lässt
sich danach jederzeit per Service `fach_typ_setzen` anpassen, sonst wird
der Einrichtungsdialog bei vielen Fächern unübersichtlich.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import CONF_ANZAHL_FAECHER, CONF_FACH_NAMEN, DOMAIN

MIN_FAECHER = 1
MAX_FAECHER = 20
STANDARD_ANZAHL_FAECHER = 7


class GefrierschrankInventarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handhabt die Einrichtung über die Home-Assistant-UI."""

    VERSION = 1

    def __init__(self) -> None:
        self._anzahl_faecher: int = STANDARD_ANZAHL_FAECHER

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._anzahl_faecher = user_input[CONF_ANZAHL_FAECHER]
            return await self.async_step_faecher()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ANZAHL_FAECHER, default=STANDARD_ANZAHL_FAECHER
                ): vol.All(int, vol.Range(min=MIN_FAECHER, max=MAX_FAECHER))
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_faecher(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            fach_namen = [
                user_input[f"fach_{i}_name"] for i in range(1, self._anzahl_faecher + 1)
            ]
            return self.async_create_entry(
                title="Gefrierschrank Inventar",
                data={
                    CONF_ANZAHL_FAECHER: self._anzahl_faecher,
                    CONF_FACH_NAMEN: fach_namen,
                },
            )

        schema_dict: dict[Any, Any] = {}
        for i in range(1, self._anzahl_faecher + 1):
            schema_dict[vol.Required(f"fach_{i}_name", default=f"Fach {i}")] = str
        schema = vol.Schema(schema_dict)
        return self.async_show_form(step_id="faecher", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        # config_entry wird von Home Assistant automatisch als self.config_entry
        # bereitgestellt, sobald der Flow gestartet wird - nicht mehr selbst im
        # Konstruktor speichern (seit HA 2025.12 deprecated).
        return GefrierschrankInventarOptionsFlow()


class GefrierschrankInventarOptionsFlow(config_entries.OptionsFlow):
    """Erlaubt es später, weitere Fächer hinzuzufügen, ohne neu einzurichten."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        aktuelle_anzahl = self.config_entry.data.get(CONF_ANZAHL_FAECHER, STANDARD_ANZAHL_FAECHER)
        schema = vol.Schema(
            {
                vol.Required(
                    "weiteres_fach_name", default=f"Fach {aktuelle_anzahl + 1}"
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
