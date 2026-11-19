# Bundle 750 — vollständiger Analyzer-CLI-Rest

19. November 2026. Maßgebliches natives Fehler-Result:
SHA-256 `644b33b7ca04c17f82157fd79a68431ed5620b1efc74d71a46bba038ca5f5037`,
HEAD `83382391a0c1cac367d63840ce4b9f25e6b2b65b`.
ANALYZER-CLI-749 ist nach 7.381 erfolgreichen Tests committed. Danach scheiterte
19.g.W mit 640 Fehlern und 8.575 bestandenen Tests; W bleibt uncommitted,
R/C und 19.h.W/R/C wurden nicht ausgeführt. Bestätigt bleiben 819/918.
Der historische Vorbereitungsbericht 749 bleibt unverändert und ist kein
Erfolgsnachweis für die offenen Produktstufen.

Die gemeinsame Registry scheitert bereits beim Aufbau: Ein INPUT_READ-Vertrag
darf keine Projekt-Konfigurationsschemaprüfung anfordern. Request und explizite
Projektvarianten erhalten PROJECT_READ mit vollständiger Schemaprüfung;
projektlose Dateiaufrufe bleiben INPUT_READ. Varianten gehören stabil derselben
Registry, damit der unveränderte Identitätswächter echte Aufrufe akzeptiert.
Relative Dateien bleiben an das Aufrufverzeichnis gebunden. Die maschinenlesbare
Beschreibung nennt den tatsächlichen Projektmodus und beansprucht weder
AI-Transporteffekte noch eine Workfortsetzung.

Die allgemeinen Beispieldurchläufe verwenden für Analyzer echte Request- und
Reportdateien. Code 5 für nicht ausgeführte Worker beziehungsweise fehlende
unabhängige Aktualität wird präzise mit vollständigen unavailable-Daten geprüft;
alle bisherigen Erfolgsoracles bleiben bestehen. 18 zusätzliche Regressionen
prüfen öffentliche argv-/strukturierte Registryausführung, frühe vollständige
Konfigurationsprüfung, verschiedene Projekt-/Eingabeverzeichnisse, unbeabsichtigte
Projektentdeckung und die ausführbare Bindung der maschinenlesbaren Varianten.

Korrekturbindung: Plan-SHA-256 `4c84e2f2a717da52380c97ca79f85ad7d59e8e0cf80e0c81ff5ef63f33c32360`.
Der vollständige offene Präfix bleibt in ursprünglicher Reihenfolge erhalten:
19.g.W, 19.g.R, 19.g.C, 19.h.W, 19.h.R, 19.h.C; alle Rollen bleiben
implementation. Kein erfolgreicher Commit wird wiederholt. Die Spezifikation
0.2.99, ANALYZER-CLI-749 und der Entwicklungsvertrag bleiben bytegleich;
keine neue Klärung und keine Budgetänderung. Vollständige Vorherbytes binden
den tatsächlich ausgegebenen schmutzigen Snapshot einschließlich unverändert
übernommener, noch zu committender W-Dateien.

Dieser vorbereitete Stand **19.g.W** zählt erst nach seinem eigenen erfolgreichen
Apply-Gate/Commit **820/918**; danach folgt **19.g.R**. Die getrennten
W/R/C-Ziele und der ursprüngliche Umfang beider Gruppen bleiben vollständig.
C erhält die W/R-Testbytes und die extrahierten Funktionsdefinitionen unverändert.
Jede Stage installiert nur ihren eigenen Zustand und prüft die gefilterte
N=3-Gruppe plus ungefilterte Pflichtauswahl einschließlich sämtlicher vom
Fehler-Result betroffenen Testdateien vor ihrem Commit.

Dev führt keine Testkörper, Fixtures oder Test-Unterprozesse aus. Syntax,
statische Analyse, reine Collection, Katalog- und native Paketprüfung sind
keine Verhaltensabnahme. Spätere Work-/Worker-/Distributions- und Sprachpolicy-
Positionen, menschliche Freigaben sowie Vollsuite-/Plattformpflichten bleiben offen.
