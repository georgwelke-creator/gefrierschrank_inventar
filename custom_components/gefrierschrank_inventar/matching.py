"""Ähnlichkeitsabgleich für Artikelnamen.

Wird beim Einlagern per Sprache genutzt: statt bei einem Verhörer
("Fischsebchen" statt "Fischstäbchen") einen neuen, ähnlich klingenden
Artikel anzulegen, wird automatisch der bereits bekannte Name verwendet.
Bewusst mit dem Python-eigenen `difflib` gelöst, ganz ohne Zusatzabhängigkeit
und ohne Cloud-Aufruf.
"""
from __future__ import annotations

import difflib

from .const import AEHNLICHKEITS_SCHWELLE


def finde_aehnlichen_artikelnamen(
    name: str, bekannte_namen: list[str], schwelle: float = AEHNLICHKEITS_SCHWELLE
) -> str | None:
    """Sucht unter den bekannten Artikelnamen den ähnlichsten Treffer.

    Vergleicht case-insensitiv. Gibt den bekannten Namen in seiner
    ursprünglichen Schreibweise zurück, wenn ein ausreichend ähnlicher
    (aber nicht bereits exakt identischer) Treffer existiert. Gibt None
    zurück, wenn der Name schon exakt bekannt ist (keine Korrektur nötig)
    oder wenn nichts nah genug dran ist (dann ist es vermutlich ein
    tatsächlich neuer Artikel).
    """
    name_normalisiert = name.strip().lower()
    if not name_normalisiert:
        return None

    namen_map: dict[str, str] = {}
    for bekannt in bekannte_namen:
        namen_map.setdefault(bekannt.strip().lower(), bekannt)

    if name_normalisiert in namen_map:
        return None  # exakt bekannt, keine Korrektur nötig

    treffer = difflib.get_close_matches(
        name_normalisiert, namen_map.keys(), n=1, cutoff=schwelle
    )
    if not treffer:
        return None
    return namen_map[treffer[0]]
