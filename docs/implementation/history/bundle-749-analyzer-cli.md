# Bundle 749 — Analyzer-CLI und externe Dateien

19. November 2026. Vollständig geprüftes erfolgreiches Result 748:
SHA-256 `90214003b53dbf372be22749e8fd4bf917c29d8e177db6ef9e6f1c90ba69c6a9`, sauberer HEAD
`26898f20dab7c7fc50139bd72769c276e6b2f51a`. Alle sieben Stages sind committed,
zuletzt 19.f.C mit 9.355 erfolgreichen Tests; bestätigt 819/918 Positionen.
Kein offener Korrekturrest und keine Wiederholung erfolgreicher Commits.

[ANALYZER-CLI-749](../decisions/analyzer-cli-749.md) präzisiert vorab in genau
einem optionalen Klärungspräfix T.5.2 und die zugehörigen Planabnahmen.
Danach folgen die vollständigen Gruppen 19.g.W/R/C und 19.h.W/R/C.
Dieser vorbereitete Stand **19.g.C** zählt erst nach seinem eigenen
Apply-Gate/Commit **822/918**; danach folgt **19.h.W**.

19.g.W installiert list/describe/request/run/import/show/evaluate mit echten
Registryverträgen, nativer Requestbildung, passiven Reportlesern und atomarer
Ausgabe außerhalb des kanonischen Modells. Ein noch nicht implementierter
Worker liefert für alle angeforderten Analyzer ehrliche unavailable-Coverage
und Code 5. Variadische Positionsdateien verwenden denselben Registrybinder
wie strukturierte Aufrufe; bisherige skalare Parameter bleiben kompatibel.
R ergänzt bytegleiche No-op-Publikation ohne Schreibversuch, native Grenz-
und Quellenfehler, alle gewählten unlesbaren Inputs sowie frühe Kennungsprüfung.
C isoliert die bereits registrierten Optionen/Handler in einem CLI-Modul;
Definitionen und Testbytes bleiben unverändert.

19.h.W integriert ausdrücklich übergebene fremde Descriptor-/Settingsdateien
in vollständige Requests, Listen, Beschreibungen und vorhandene Import-/
Auswertungspfade. Ausführbarkeit bleibt distributionseigen und false.
R validiert die gesamte passive Eingabedatei auch ohne Projekt-/Workerstart
und bindet adversariale Abnahmen: keine Prozesse, Netzwerk-/Modellimporte
oder impliziten Analyzer durch strict, validate und dessen Lintpipeline.
C trennt die distributionseigene Ausführungsgrenze vom passiven Dateiadapter,
ohne Verhaltensänderung und bei unveränderten W/R-Testbytes.

Jede Stage installiert nur ihren eigenen Zustand, prüft die fällige gefilterte
N=3-Gruppe plus ungefilterte Pflichtauswahl und committet erst bei Erfolg.
Dev führt keine Testkörper, Fixtures oder Test-Unterprozesse aus. Syntax,
Statische Analyse, reine Collection und native Paketprüfung sind keine
Verhaltensabnahme. Tests verwenden echte kleine Projekte/Dateien, bestehende
passive Reportfixtures mit ausdrücklich unbekannten Enginefakten und eine
verifizierte Partialintegration. Keine Tests menschlicher Darstellung.

Sprachpolicy, tatsächlicher Worker, Distribution und dauerhafte Workadapter
behalten ihre nachfolgenden eigenen Planpositionen. Ein erfolgreicher
aktueller Dateicheck erteilt keine Evidence-/Review-/Produktfreigabe.
Vollsuite und separate CPython-/Plattformmatrix bleiben Releasepflichten.
