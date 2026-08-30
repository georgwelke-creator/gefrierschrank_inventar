"""Async SQLite-Datenschicht für das Gefrierschrank-Inventar.

Bewusst ohne ORM gehalten (reines aiosqlite), damit die Integration schlank
bleibt und keine zusätzlichen schweren Abhängigkeiten braucht. Alle Methoden
sind async und blockieren den Event-Loop von Home Assistant nicht.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from .const import (
    BEZUG_TYPEN,
    FACH_TYPEN,
    STATUS_ENTNOMMEN,
    STATUS_VORHANDEN,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS fach (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    typ TEXT NOT NULL CHECK (typ IN ('offen', 'lade')),
    position INTEGER NOT NULL DEFAULT 0,
    kalibrierung_x1 REAL,
    kalibrierung_y1 REAL,
    kalibrierung_x2 REAL,
    kalibrierung_y2 REAL,
    aktiv INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS inventar_eintrag (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fach_id INTEGER NOT NULL REFERENCES fach(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    kategorie TEXT,
    menge REAL NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'vorhanden' CHECK (status IN ('vorhanden', 'entnommen', 'unklar')),
    eingelagert_am TEXT NOT NULL,
    entnommen_am TEXT,
    quelle TEXT NOT NULL DEFAULT 'manuell' CHECK (quelle IN ('manuell', 'sprache', 'bild')),
    referenzbild_pfad TEXT,
    confidence REAL,
    notiz TEXT
);

CREATE TABLE IF NOT EXISTS mindestbestand (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bezug_typ TEXT NOT NULL CHECK (bezug_typ IN ('kategorie', 'artikel_name', 'fach')),
    bezug_wert TEXT NOT NULL,
    schwellenwert REAL NOT NULL,
    aktiv INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_inventar_fach ON inventar_eintrag(fach_id);
CREATE INDEX IF NOT EXISTS idx_inventar_status ON inventar_eintrag(status);
CREATE INDEX IF NOT EXISTS idx_inventar_kategorie ON inventar_eintrag(kategorie);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Fach:
    id: int
    name: str
    typ: str
    position: int
    aktiv: bool = True


@dataclass
class InventarEintrag:
    id: int
    fach_id: int
    name: str
    kategorie: str | None
    menge: float
    status: str
    eingelagert_am: str
    entnommen_am: str | None
    quelle: str
    notiz: str | None = None


@dataclass
class MindestbestandRegel:
    id: int
    bezug_typ: str
    bezug_wert: str
    schwellenwert: float
    aktiv: bool = True
    aktueller_bestand: float = field(default=0)


class GefrierschrankStorage:
    """Kapselt sämtliche Datenbankzugriffe."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def async_init(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA foreign_keys = ON")
        await self._db.executescript(SCHEMA)
        await self._db.commit()

    async def async_close(self) -> None:
        if self._db is not None:
            await self._db.close()

    # ------------------------------------------------------------------
    # Fächer
    # ------------------------------------------------------------------
    async def async_add_fach(self, name: str, typ: str, position: int) -> int:
        if typ not in FACH_TYPEN:
            raise ValueError(f"Unbekannter Fach-Typ: {typ}")
        cursor = await self._db.execute(
            "INSERT INTO fach (name, typ, position) VALUES (?, ?, ?)",
            (name, typ, position),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def async_list_faecher(self) -> list[Fach]:
        cursor = await self._db.execute(
            "SELECT id, name, typ, position, aktiv FROM fach WHERE aktiv = 1 ORDER BY position"
        )
        rows = await cursor.fetchall()
        return [
            Fach(id=r["id"], name=r["name"], typ=r["typ"], position=r["position"], aktiv=bool(r["aktiv"]))
            for r in rows
        ]

    async def async_get_fach(self, fach_id: int) -> Fach | None:
        cursor = await self._db.execute(
            "SELECT id, name, typ, position, aktiv FROM fach WHERE id = ?", (fach_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return Fach(id=row["id"], name=row["name"], typ=row["typ"], position=row["position"], aktiv=bool(row["aktiv"]))

    async def async_set_fach_typ(self, fach_id: int, typ: str) -> None:
        if typ not in FACH_TYPEN:
            raise ValueError(f"Unbekannter Fach-Typ: {typ}")
        await self._db.execute("UPDATE fach SET typ = ? WHERE id = ?", (typ, fach_id))
        await self._db.commit()

    # ------------------------------------------------------------------
    # Inventar
    # ------------------------------------------------------------------
    async def async_einlagern(
        self,
        fach_id: int,
        name: str,
        kategorie: str | None,
        menge: float,
        quelle: str,
        notiz: str | None = None,
        referenzbild_pfad: str | None = None,
        confidence: float | None = None,
    ) -> int:
        cursor = await self._db.execute(
            """
            INSERT INTO inventar_eintrag
                (fach_id, name, kategorie, menge, status, eingelagert_am, quelle, notiz, referenzbild_pfad, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (fach_id, name, kategorie, menge, STATUS_VORHANDEN, _now_iso(), quelle, notiz, referenzbild_pfad, confidence),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def async_entnehmen(self, eintrag_id: int) -> bool:
        """Markiert einen konkreten Eintrag als entnommen."""
        cursor = await self._db.execute(
            "UPDATE inventar_eintrag SET status = ?, entnommen_am = ? WHERE id = ? AND status = ?",
            (STATUS_ENTNOMMEN, _now_iso(), eintrag_id, STATUS_VORHANDEN),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def async_entnehmen_by_name(self, fach_id: int, name: str) -> int | None:
        """Entnimmt den ältesten vorhandenen Eintrag mit diesem Namen im Fach (FIFO).

        Praktisch für die Entnahme-Erkennung ohne Sprachangabe: es muss nur
        Fach und (vom Bildabgleich vermuteter) Name übergeben werden.
        Gibt die id des entnommenen Eintrags zurück, oder None falls kein
        passender vorhandener Eintrag gefunden wurde.
        """
        cursor = await self._db.execute(
            """
            SELECT id FROM inventar_eintrag
            WHERE fach_id = ? AND name = ? AND status = ?
            ORDER BY eingelagert_am ASC
            LIMIT 1
            """,
            (fach_id, name, STATUS_VORHANDEN),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        eintrag_id = row["id"]
        await self._db.execute(
            "UPDATE inventar_eintrag SET status = ?, entnommen_am = ? WHERE id = ?",
            (STATUS_ENTNOMMEN, _now_iso(), eintrag_id),
        )
        await self._db.commit()
        return eintrag_id

    async def async_list_inventar(
        self,
        fach_id: int | None = None,
        kategorie: str | None = None,
        status: str = STATUS_VORHANDEN,
        suche: str | None = None,
    ) -> list[InventarEintrag]:
        query = "SELECT * FROM inventar_eintrag WHERE status = ?"
        params: list = [status]
        if fach_id is not None:
            query += " AND fach_id = ?"
            params.append(fach_id)
        if kategorie is not None:
            query += " AND kategorie = ?"
            params.append(kategorie)
        if suche:
            query += " AND name LIKE ?"
            params.append(f"%{suche}%")
        query += " ORDER BY eingelagert_am DESC"
        cursor = await self._db.execute(query, params)
        rows = await cursor.fetchall()
        return [
            InventarEintrag(
                id=r["id"],
                fach_id=r["fach_id"],
                name=r["name"],
                kategorie=r["kategorie"],
                menge=r["menge"],
                status=r["status"],
                eingelagert_am=r["eingelagert_am"],
                entnommen_am=r["entnommen_am"],
                quelle=r["quelle"],
                notiz=r["notiz"],
            )
            for r in rows
        ]

    async def async_fach_bestand(self, fach_id: int) -> list[InventarEintrag]:
        return await self.async_list_inventar(fach_id=fach_id, status=STATUS_VORHANDEN)

    async def async_gesamt_anzahl(self) -> int:
        cursor = await self._db.execute(
            "SELECT COUNT(*) AS n FROM inventar_eintrag WHERE status = ?", (STATUS_VORHANDEN,)
        )
        row = await cursor.fetchone()
        return int(row["n"])

    # ------------------------------------------------------------------
    # Mindestbestand
    # ------------------------------------------------------------------
    async def async_mindestbestand_setzen(
        self, bezug_typ: str, bezug_wert: str, schwellenwert: float
    ) -> int:
        if bezug_typ not in BEZUG_TYPEN:
            raise ValueError(f"Unbekannter Bezugstyp: {bezug_typ}")
        # Vorhandene Regel mit gleichem Bezug aktualisieren statt duplizieren
        cursor = await self._db.execute(
            "SELECT id FROM mindestbestand WHERE bezug_typ = ? AND bezug_wert = ?",
            (bezug_typ, bezug_wert),
        )
        row = await cursor.fetchone()
        if row is not None:
            await self._db.execute(
                "UPDATE mindestbestand SET schwellenwert = ?, aktiv = 1 WHERE id = ?",
                (schwellenwert, row["id"]),
            )
            await self._db.commit()
            return row["id"]
        cursor = await self._db.execute(
            "INSERT INTO mindestbestand (bezug_typ, bezug_wert, schwellenwert) VALUES (?, ?, ?)",
            (bezug_typ, bezug_wert, schwellenwert),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def async_mindestbestand_entfernen(self, bezug_typ: str, bezug_wert: str) -> bool:
        cursor = await self._db.execute(
            "DELETE FROM mindestbestand WHERE bezug_typ = ? AND bezug_wert = ?",
            (bezug_typ, bezug_wert),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def async_list_mindestbestand(self) -> list[MindestbestandRegel]:
        cursor = await self._db.execute(
            "SELECT id, bezug_typ, bezug_wert, schwellenwert, aktiv FROM mindestbestand WHERE aktiv = 1"
        )
        regeln = []
        for row in await cursor.fetchall():
            bestand = await self._async_aktueller_bestand(row["bezug_typ"], row["bezug_wert"])
            regeln.append(
                MindestbestandRegel(
                    id=row["id"],
                    bezug_typ=row["bezug_typ"],
                    bezug_wert=row["bezug_wert"],
                    schwellenwert=row["schwellenwert"],
                    aktiv=bool(row["aktiv"]),
                    aktueller_bestand=bestand,
                )
            )
        return regeln

    async def _async_aktueller_bestand(self, bezug_typ: str, bezug_wert: str) -> float:
        if bezug_typ == "kategorie":
            cursor = await self._db.execute(
                "SELECT COALESCE(SUM(menge), 0) AS n FROM inventar_eintrag WHERE status = ? AND kategorie = ?",
                (STATUS_VORHANDEN, bezug_wert),
            )
        elif bezug_typ == "artikel_name":
            cursor = await self._db.execute(
                "SELECT COALESCE(SUM(menge), 0) AS n FROM inventar_eintrag WHERE status = ? AND name = ?",
                (STATUS_VORHANDEN, bezug_wert),
            )
        else:  # fach
            cursor = await self._db.execute(
                "SELECT COALESCE(SUM(menge), 0) AS n FROM inventar_eintrag WHERE status = ? AND fach_id = ?",
                (STATUS_VORHANDEN, int(bezug_wert)),
            )
        row = await cursor.fetchone()
        return float(row["n"])

    async def async_unterschrittene_regeln(self) -> list[MindestbestandRegel]:
        regeln = await self.async_list_mindestbestand()
        return [r for r in regeln if r.aktueller_bestand < r.schwellenwert]
