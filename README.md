# Gefrierschrank Inventar

Home-Assistant-Integration für ein KI-gestütztes, vollständig lokales Gefrierschrank-Inventar. Alle Daten bleiben im lokalen Netzwerk, keine Cloud.

Dies ist **Phase 1** eines mehrstufigen Projekts (Datenmodell und manuelle Erfassung). Die spätere automatische Erfassung per Kamera und Sprache baut auf genau diesem Datenmodell auf.

## Status

Frühe Entwicklungsphase, noch nicht für den produktiven Einsatz gedacht. Datenmodell und Services können sich noch ändern.

## Was die Integration aktuell kann

- Fächer (offene Ablagen oder Schubladen) bei der Einrichtung anlegen, später über die Optionen weitere hinzufügen
- Artikel einlagern und entnehmen über Home-Assistant-Services (`gefrierschrank_inventar.einlagern`, `gefrierschrank_inventar.entnehmen`) – diese Services erzeugen unter *Entwicklerwerkzeuge → Aktionen* automatisch ein Formular und dienen in dieser Phase als manuelles Test-Interface, ganz ohne Kamera oder Sprache
- Ein Sensor pro Fach mit der Anzahl aktuell vorhandener Artikel (Artikelliste als Attribut)
- Ein Gesamtbestand-Sensor
- Mindestbestand-Regeln je Kategorie, Artikel oder Fach (`gefrierschrank_inventar.mindestbestand_setzen` / `_entfernen`) mit einem aggregierten Warn-Binary-Sensor

## Installation

### Über HACS (als Custom Repository, solange die Integration noch nicht im Standard-Store gelistet ist)

1. HACS → Integrationen → Menü (drei Punkte) → Benutzerdefinierte Repositories
2. Dieses Repository als Typ "Integration" hinzufügen
3. "Gefrierschrank Inventar" installieren und Home Assistant neu starten

### Manuell

Den Ordner `custom_components/gefrierschrank_inventar` in das `custom_components`-Verzeichnis deiner Home-Assistant-Konfiguration kopieren und Home Assistant neu starten.

## Einrichtung

Einstellungen → Geräte & Dienste → Integration hinzufügen → "Gefrierschrank Inventar". Zuerst die Gesamtanzahl der Fächer angeben, danach jedem Fach einen Namen geben. Der Fach-Typ (offen/Schublade) lässt sich aktuell nur direkt in der Datenbank ändern, eine passende Einstellmöglichkeit folgt in einer späteren Phase.

## Beispiel: Artikel manuell einlagern

```yaml
service: gefrierschrank_inventar.einlagern
data:
  fach_id: 1
  name: Fischstäbchen
  kategorie: Fisch
  menge: 1
  quelle: manuell
```

## Projekt-Hintergrund

Teil eines größeren Projekts für eine KI-basierte Lebensmittelerkennung im Gefrierschrank per Kamera, lokal über Home Assistant, ohne Cloud-Anbindung. Der volle Architektur- und Umsetzungsplan (Kamera-Anbindung, Fach-Kalibrierung, lokale Bild-KI, Sprachsteuerung) liegt außerhalb dieses Repositories in der Projektdokumentation.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
