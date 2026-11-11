# Control: Paketprüfung, Instanzen und Monitor

Nutzerauftrag vom 10. November 2026, OFF-PLAN in Linie Dev2/Apply2.
Produktfortschritt und vorhandene Betriebsfreigaben bleiben unverändert.
Stand 11. November 2026: Die zwölf Commits sind über Bundles 001–004 vollständig
in Apply2 abgenommen. Der [Ausführungsnachweis](../implementation/history/dev2-control-profiling-001-005.md)
belegt den Abschluss. Installation und Betriebsprüfung der neuen Control-Version
samt Monitor stehen noch aus; eine Automatik wurde dadurch nicht gestartet.

## Geordnete Abnahmen

| Folge | W | R | C |
| --- | --- | --- | --- |
| RUNTIME-LANES | Eigene Exchange-Historie vor dem ersten Control-Gate | Unsichere oder wechselnde Ziele zurückweisen | Gemeinsame Pfadauflösung |
| CONTROL-X | Exakte Paketbindung vor nativer Prüfung; sichtbare Prüfphase | Große Historien, geänderte Dateien, Archivierung und konkurrierende Ergebnisse | Suche, Cache und Nachweis getrennt |
| CONTROL-INSTANCES | Benannte Instanzen, vollständige Bedienzuordnung und gemeinsame Besitzsperren | Parallelstart, Recovery, Konfigurationswechsel und Legacy-Erhaltung | Gemeinsame Sperrschlüssel für Worker und Handover |
| CONTROL-MONITOR | Lesende TUI für alle Instanzen und JSON-Momentaufnahme | Veraltung, Teilfehler und begrenzte unabhängige Abfragen | Darstellung, Quellen und Aktualisierung getrennt |

Die Runtime-Voraussetzung und alle neun Control-Zustände (zwölf Commits) wurden
einzeln über Apply2 geprüft und committed. Jeder Zustand enthielt Pflichtauswahl
und stabile Testnummern. Die Verhaltenstests liefen im Apply; erfolgreiche
Commitpräfixe blieben während der Korrekturen erhalten.

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

## Instanzen

Ohne Auswahl bleibt `default` mit bestehenden Pfaden, Historie und
`specroad-control.service` erhalten. `control --instance NAME ...` wählt genau
eine benannte Instanz. Namen bestehen aus kleinen ASCII-Buchstaben, Ziffern,
Unterstrich oder Bindestrich, beginnen mit einem Buchstaben und sind höchstens
32 Zeichen lang. Konfiguration, State, Jobs, Budgets, Socket, Logs und Releases
liegen unter `$SPECROAD_CONTROL_HOME/instances/NAME/`. Die Unit heißt
`specroad-control@NAME.service`; Installation oder Deployment startet sie nicht.

Die ausdrückliche Ersteinrichtung erlaubt `configure --repository DEV
--apply-repository APPLY --exchange EXCHANGE --thread-id UUID --result RESULT`.
Die Bindung einer bestehenden Historie kann dadurch nicht überschrieben werden.
Gemeinsame Sperren schützen Dev-Pfad, Codex-Home/Thread und native Apply-ID;
getrennte Ziele dürfen parallel laufen. Bestehende Sperren der Standardinstanz
werden zusätzlich gehalten. Die Legacy-Migration bleibt bei `default`.
Dev2 wird weiterhin manuell bedient; dieses Bundle richtet keinen Dienst ein.

## Control-Monitor

`python3 tools/control-monitor --all` öffnet die lesende TUI. Mit `--instance
NAME` wird eine einzelne Instanz ausgewählt. `--once --json` liefert dieselben
Beobachtungen ohne Terminal. Ohne Auswahl gilt die Standardinstanz bzw.
`SPECROAD_CONTROL_INSTANCE`. Die installierte Python-Paketkopie enthält dieselbe
Monitorimplementierung (`python -m specroad_control.monitor`).

Die Übersicht zeigt Frische, Lifecycle, Sollzustand und Automatikphase. Vier
Detailansichten enthalten Betrieb, Bindung/Release/Unit, Paketprüfung/Budget
sowie Fehler/Quellen. Links/rechts wählt eine Instanz, Tab oder 1–4 eine Ansicht,
hoch/runter scrollt, r liest neu, ? zeigt Hilfe, q beendet.

Live-Daten stammen aus dem Status-Socket. Bei Ausfall bleiben gespeicherte
Zustände ausdrücklich VERALTET; eine alte PID beweist keinen laufenden Prozess.
Release-Receipts werden als solche angezeigt, nicht als neue Codeprüfung.
Abfragen laufen pro Instanz unabhängig mit einem Zeitbudget und höchstens einer
offenen Abfrage je Instanz. Der Monitor startet keine Dienste, fragt kein Modell
und öffnet keine schreibende SQLite-Verbindung.

Budget, aktueller Job und die letzten Statuswerte von Acceptance-, Reconcile-
und Freigabereceipts werden zusätzlich aus einer begrenzten Speicherkopie der
Historie gelesen. Offene SQLite-Journale, geänderte Bytes oder ein überschrittenes
Lesebudget ergeben einen Quellenfehler. Die Anzeige erteilt daraus keine neue
Freigabe und verbindet SQLite niemals mit der Originaldatei.
