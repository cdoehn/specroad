# OFF-PLAN RUNTIME-AUTO-521: aktuelle Messhistorie und Korrektur von Result 520

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN RUNTIME-AUTO-521: aktuelle Messhistorie und Korrektur von Result 520

**Ausdrücklicher gemeinsamer Nutzerauftrag vom 30. Oktober 2026.** Die neue
Messpolicy aus Spezifikation 2.5 wird zusammen mit den beiden Inventarkorrekturen
in genau einer state-gebundenen ZIP umgesetzt. Produktstand bleibt 650/900;
15.l.R ist abgeschlossen, 15.l.C bleibt offen und wird nicht bearbeitet.

Quelle: Result 520, SHA-256
`5fc5fb898397ab15796afce0984f8d02ed732277e2c4e5efe7bc4cfaa2479dc8`,
Base-Commit `5b851562a0a882c1fde085c7306854cf30188ca9`, Zustand
`33041b321d28c074`. Das Apply blieb ohne Commit: 6004 bestanden, 2 fehlgeschlagen.
Die drei uncommitteten Dateien aus 520 werden erhalten. Historische Werte und
Originaljournale werden weder ersetzt noch als aktuelle Erfolgsevidenz benutzt.

Pflichtabnahmen:
- Automatische dauerhafte Phasenmessung schon beim ersten gewöhnlichen Dev-
  und Apply-Lauf; Historie und Originalherkunft erhalten; reine Collection ohne
  Messversuch. Gemeinsame aktuelle Werte sind sofort für Apply verfügbar.
- Neuester gestarteter Versuch pro Test; sofortige Invalidierung bei Start,
  kein Rückgriff auf ältere Erfolge; Fehler/Subtests/Abbruch und fehlende Phasen
  bleiben ungültig. Erfolgreicher Wiederholungslauf macht den Wert gültig.
- N=3 minus dynamischem langsamstem Fünftel der aktuellen gültigen Messwerte;
  deterministische Gleichstände, neue/ungültige Tests zugelassen, entfernte
  Identitäten nicht mitzählen. Dev und manuelle Volltests bleiben ungefiltert.
- Auswahl-Snapshot und tatsächliche Identitäten mit v3-Bindung prüfen;
  Messänderungen während des Laufs gelten erst für die nächste Auswahl.
- Parallelität, Datenbankfehler und unvollständige Phasen sicher behandeln;
  keine Vermischung von Versuchen, keine verlorenen alten Datensätze.
- Registry-Test ergänzt die bereits vorhandenen recover.restore- und work.*-
  Commands; Schemakatalog-Test ergänzt restore-command-v1 und work-command-v1.
  Die exakten Inventarprüfungen und negativen Verträge bleiben erhalten.
- Gezielte parallele Dev-Abnahmen und vollständige Collection/Katalogprüfung;
  pro echtem Zwischenstand genau die fällige parallele Apply-Gruppe vor Commit.
  Kein zusätzlicher Volltest, keine Dokumentationstests, keine Dienstbedienung.

- [x] **RUNTIME-AUTO-521.W:** Vollständige automatische Messung, aktuelle
  Apply-Auswahl und beide Inventarkorrekturen funktionsfähig integrieren.
- [x] **RUNTIME-AUTO-521.R:** Fehler-, Abbruch-, Parallelitäts- und I/O-Grenzen
  vervollständigen und mit Verhaltensabnahmen absichern.

W-Dev-Abnahme: **215 gezielte Verhaltenstests**, vier parallele Worker, Exit 0.
Beide Tests aus dem fehlgeschlagenen Result sind enthalten und erfolgreich.
Vollständige Collection/Katalogprüfung: **22.489** Identitäten; keine Vollsuite.
Der W-Apply-Nachweis und sein Commit stehen bis zur externen Ausführung aus.

R-Dev-Abnahme: **330 gezielte Verhaltenstests**, vier parallele Worker,
Exit 0; ergänzend **57** Tests der betroffenen Auswahl-Runner, ebenfalls
vier Worker und Exit 0. Vollständige Collection/Katalogprüfung: **22.514**
Identitäten. Echte Worker-Abbrüche, erfolgreiche Wiederholung, konkurrierende
Schreiber, defekte/ausgetauschte Datenbanken und verweigerte Schreibvorgänge
wurden in isolierten Testprojekten geprüft. Diese negativen Fixture-Läufe sind
keine fehlgeschlagenen Produktgates. Historische Journale bleiben unverändert.

Lieferfolge innerhalb Bundle 521: erst W-Zustand installieren, fällige N=3-Gruppe
2 mit aktueller Auswahl prüfen und committen; anschließend R-Zustand herstellen,
Gruppe 0 mit neuem Messsnapshot prüfen und committen. Keine Vorinstallation des
R-Endstands. Die aktuellen Messdaten bestimmen die Gruppengröße unmittelbar
vor dem jeweiligen Lauf, keine veraltete feste Sollzahl. Bei Fehler bleiben
bereits erzeugte Commits und der tatsächliche Restzustand erhalten.
Commit-Messages:
1. `test(workflow): Laufzeiten automatisch erfassen und Apply-Auswahl aktualisieren`
2. `test(workflow): Messhistorie gegen Abbruch und Speicherfehler absichern`

Die frühere Ausnahme RUNTIME-REFRESH-520 bleibt historisch dokumentiert; ihr
fehlgeschlagener Einzelcommit wird nicht als erfolgreich abgeschlossen erklärt.
Die erhaltene Baseline wird mit der neuen Policy gemeinsam übernommen.
