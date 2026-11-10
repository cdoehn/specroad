# Control: Paketprüfung, Instanzen und Monitor

Nutzerauftrag vom 10. November 2026, OFF-PLAN in Linie Dev2/Apply2.
Die Produktposition 18.h.W und alle vorhandenen Freigaben bleiben unverändert.
Diese Vorbereitung ist kein Apply-Erfolgsnachweis und startet keine Automatik.

## Geordnete Abnahmen

| Folge | W | R | C |
| --- | --- | --- | --- |
| RUNTIME-LANES | Eigene Exchange-Historie vor dem ersten Control-Gate | Unsichere oder wechselnde Ziele zurückweisen | Gemeinsame Pfadauflösung |
| CONTROL-X | Exakte Paketbindung vor nativer Prüfung; sichtbare Prüfphase | Große Historien, geänderte Dateien, Archivierung und konkurrierende Ergebnisse | Suche, Cache und Nachweis getrennt |
| CONTROL-INSTANCES | Benannte Instanzen, vollständige Bedienzuordnung und gemeinsame Besitzsperren | Parallelstart, Recovery, Konfigurationswechsel und Legacy-Erhaltung | Gemeinsame Sperrschlüssel für Worker und Handover |
| CONTROL-MONITOR | Lesende TUI für alle Instanzen und JSON-Momentaufnahme | Veraltung, Teilfehler und begrenzte unabhängige Abfragen | Darstellung, Quellen und Aktualisierung getrennt |

Die Runtime-Voraussetzung und alle neun Control-Zustände (zwölf Commits) werden einzeln über Apply2 geprüft und committed. Jeder Zustand
enthält Pflichtauswahl und stabile Testnummern. Die eigentlichen Verhaltenstests
laufen ausschließlich im Apply. Ein rotes Gate erhält den erfolgreichen Präfix.

## Paketprüfung

Das erwartete Vorher-Binding grenzt Patch-Kandidaten vor der nativen Vollprüfung
ein. Identität und Gültigkeit bleiben Entscheidungen des nativen Core. Auswahl
nach Hash, unmittelbarem Vorher-Result und eindeutiger Folge bleibt verbindlich.
Die Fortschrittsdaten unterscheiden discovery/validation und abgeschlossene oder
unterbrochene Prüfungen; aktuelle Repository- und Dispatchprüfungen bleiben frisch.

Der Apply-Treiber akzeptiert ausschließlich die ausdrücklich gebundenen Branches
dev und dev2 und verweigert bekannte Entwicklungskopien. Repositorypfad, native
Repository-ID, vollständiger Zustand und tatsächlich ausgecheckter Branch werden
weiter vor der Ausbringung sowie vor jedem Commit geprüft.
