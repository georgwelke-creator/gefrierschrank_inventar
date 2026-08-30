"""Konstanten für die Gefrierschrank-Inventar-Integration."""
from __future__ import annotations

DOMAIN = "gefrierschrank_inventar"

# Config-Entry / Options Keys
CONF_ANZAHL_FAECHER = "anzahl_faecher"
CONF_FACH_NAMEN = "fach_namen"

# Fach-Typen
FACH_TYP_OFFEN = "offen"
FACH_TYP_LADE = "lade"
FACH_TYPEN = [FACH_TYP_OFFEN, FACH_TYP_LADE]

# Eintrags-Status
STATUS_VORHANDEN = "vorhanden"
STATUS_ENTNOMMEN = "entnommen"
STATUS_UNKLAR = "unklar"

# Quelle eines Eintrags (woher stammt die Erkennung)
QUELLE_MANUELL = "manuell"
QUELLE_SPRACHE = "sprache"
QUELLE_BILD = "bild"

# Bezugstyp für Mindestbestand-Regeln
BEZUG_KATEGORIE = "kategorie"
BEZUG_ARTIKEL_NAME = "artikel_name"
BEZUG_FACH = "fach"
BEZUG_TYPEN = [BEZUG_KATEGORIE, BEZUG_ARTIKEL_NAME, BEZUG_FACH]

# Signal, das bei jeder Änderung am Inventar gesendet wird,
# damit Sensoren sich ohne Polling aktualisieren.
SIGNAL_INVENTAR_AKTUALISIERT = f"{DOMAIN}_inventar_aktualisiert"

# Datenbankdatei, wird im HA-Konfigverzeichnis unter .storage abgelegt
DB_DATEINAME = "gefrierschrank_inventar.db"

# Service-Namen
SERVICE_EINLAGERN = "einlagern"
SERVICE_ENTNEHMEN = "entnehmen"
SERVICE_MINDESTBESTAND_SETZEN = "mindestbestand_setzen"
SERVICE_MINDESTBESTAND_ENTFERNEN = "mindestbestand_entfernen"

ATTR_FACH_ID = "fach_id"
ATTR_NAME = "name"
ATTR_KATEGORIE = "kategorie"
ATTR_MENGE = "menge"
ATTR_QUELLE = "quelle"
ATTR_NOTIZ = "notiz"
ATTR_EINTRAG_ID = "eintrag_id"
ATTR_BEZUG_TYP = "bezug_typ"
ATTR_BEZUG_WERT = "bezug_wert"
ATTR_SCHWELLENWERT = "schwellenwert"
