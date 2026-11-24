# Ressourcen des Analyzer-Adapters messen und prüfen

Die Ressourcenabnahme nach Spezifikation 14.1/T.10 ist getrennt von Corestart,
Sprachgenauigkeit und dauerhafter CLI-/Work-Integration. Eine aktuelle grüne
Verhaltenstest-Suite erzeugt keine neue Performancebeobachtung.

## Versionierter Referenznachweis

`verification/fixtures/analyzer-resources-20261121/receipt.json` bindet die
Originalbytes und die exportierten Dateien. Alle Nutzdaten sind unabhängig
gzip-komprimiert; `.gz.gz` bezeichnet eine unverändert erhaltene bereits
komprimierte originale RSS-Zeitreihe. Keine Fremdlibrary ist zum Lesen nötig.
Das ist eine nachvollziehbare Datenbindung, keine digitale Signatur.

Der Referenzhost hat Intel Core i7-8700, Stepping 10, Microcode 0xfa,
6 physische/12 logische Kerne, etwa 32 GiB RAM und DDR4 mit 2667 MT/s.
Linux 7.0.0-43-generic, Ubuntu 26.04.1, lokales NVMe-SSD-Dateisystem ext4,
Governor performance, Swap aus. Die öffentliche Plattformprojektion enthält
die exakten technischen Werte und originalen Plattform-SHA. Hostname,
Boot-/Maschinenkennung, lokale Konfiguration und unbefüllte Vorabfelder
werden nicht veröffentlicht. GNU time verliert allein den Kommandozeilen-
präfix mit lokalen Pfaden; sämtliche numerischen Zeilen bleiben bytegleich.

Das unveränderte Originalsummary entstand am 21. November 2026 um 08:43 UTC;
es bindet die Rohresultate aller sechs Läufe. Fixture und Reportbytes enthalten
keine Kundendaten: 1000 eigens synthetisierte vollständige Texte mit 166–440
Codepoints. Sie sind kein sprachlich geprüftes Abnahmekorpus.

## Messmethode

Die vier unveränderten Skripte unter `tools/analyzer_benchmark/measured_v1/`
sind als `.py.gz` bytegleich komprimiert archiviert. Vor Verwendung mit
`gzip.decompress` nach `measurement/<name>.py` entpacken; nie die Originalbytes
formatieren. Es sind exakt die gemessenen Skripte. Ihr SHA-256 steht im Summary und in der
Plattformprojektion. `prepare.py` erzeugt die vollständigen nativen Artefakte
und den Request aus dem verifizierten Offlinepaket für CPython 3.14.
`parent.py` verwendet den nativen Transport und vollständige Reportvalidierung.
`worker.py` ruft den vorhandenen echten Adapter auf; die Instrumentierung zählt
Modellladungen und Volltexthashes und delegiert unverändert an Modell und Scorer.
Der langlebige produktive Work-Dispatcher wird nicht als fertig ausgewiesen.

`benchmark.py` beobachtet separat genau Parent und Worker über deren gesamte
Lebenszeit. GNU time liefert User+System für den ganzen Prozessbaum sowie
separat den Worker. `/proc/<pid>/smaps_rollup` liefert die zeitnah summierten
RSS-Bytes; Startticks erkennen PID-Wiederverwendung. Messintervalle und
Lesezeitspannen bleiben im Rohbeleg. Kurze zwischen Samples verborgene Spitzen
werden nicht ausgeschlossen: Die Summe beider GNU-time-Lebenszeitmaxima ist
eine konservative Obergrenze (der äußere Wert kann den Worker bereits
enthalten). Nur eine Obergrenze innerhalb 512 MiB erlaubt einen Pass; liegt
nur die Stichprobenspitze darunter, ist das Ergebnis unbestimmt. CPU erhält
0,02 s Rundungsreserve für beide GNU-time-Zeitfelder. Keine Textkürzung.

Ein Warm-up und fünf frische Prozesspaare werden ausgeführt; die Wallzeit ist
der Median dieser fünf Läufe. Governor, Swap, erkannte konkurrierende Last und
Throttlingzähler werden während des gesamten Laufs beobachtet. Projektdateien
werden vor/nach jedem Lauf vollständig gehasht. Fehler bleiben Fehler; es gibt
keine automatische Wiederholung. Der Messbeobachter liegt außerhalb des
bewerteten Parent-/Workerbaums und weist seine eigene CPU separat aus.

## Erneuter expliziter Messauftrag

Messungen nur auf einer separat freigegebenen lastfreien Referenzplattform;
keine automatische Messung auf normalen Apply-Testhosts. Für die archivierte
v1-Anordnung einen privaten Laufordner `<host>/work/<lauf>/` anlegen:
`measurement/` enthält die vier Skripte, `addon.zip` das nativ verifizierte
Offlinepaket, `packaging/language_packaging/` die vorhandenen Packagingmodule,
`fixtures-support/support/` die vorhandenen reinen Helfer `domain.py`,
`artifacts.py`, `model.py`, `relations.py` desselben gebundenen Quellstands.
`operator-inputs.json` enthält Interpreterversion/-SHA, Paket-/Corebuild und
Quellcommit/-Result-SHA. `<host>/platform.preflight.json` enthält die tatsächlich
erhobenen Daten nach 14.1 und die aktuelle Bootkennung zur lokalen Bindung.
Keine unbekannten Werte als bestandene Bedingungen ergänzen. Verwendete
Vorbereitungsdaten und Module ebenfalls lokal hashen und sichern.

Mit dem explizit gebundenen CPython 3.14 zuerst
`measurement/benchmark.py --prepare-only`, dann einmal `--run` aufrufen;
neue Zielordner verwenden. Die Skripte ändern weder Swap, Governor, Hostpool
noch Dienste. Solche nötigen Betreiberaktionen erfolgen separat. Das Ergebnis
bleibt ohne passende Plattform/Originaldaten blockiert. Nach der Messung
Originaldaten samt Hashkette sichern, private Angaben nur über eine dokumentierte
Projektion entfernen und den Messhost wiederherstellen.

## Prüfung in Apply

`analyzer_benchmark.verify.load` prüft die komplette Export-/Originalhashkette;
`assess(..., expected_build=...)` validiert Originalrequests und sämtliche
Reports mit den nativen Parsern und wertet Ressourcen aus. `check` meldet
fehlende oder unbekannte Daten als `blocked`. `passed` bedeutet nur diese
historische Referenzmessung, niemals Release oder menschliche Abnahme.

Der Apply-Test baut die aktuellen unveränderten Corequellen mit dem nativen
Builder und vergleicht deren Identität mit dem gemessenen Build. Eine Änderung
dieses Builds braucht einen neu gebundenen realen Ressourcenbeleg; alte Zahlen
werden nicht automatisch auf neue Implementierungen übertragen. Gegenbeispiele
verändern ausschließlich Messbelege und prüfen Ablehnung, ohne einen Detektor
oder Erfolg zu simulieren. Alle Messwerkzeuge bleiben unter `tools/`, außerhalb
der produktiven Abhängigkeiten. Die Corebudgets aus 14.6 bleiben unberührt.


## Beobachter v2: eigene neue Kindprozesse

[Bundle 805](../implementation/history/bundle-805-force-contract-correction.md)
korrigiert ein beobachtetes Rennen zwischen RSS-Baumaufnahme und Umfeldprüfung.
Für neue Messungen ersetzt `tools/analyzer_benchmark/measured_v2/benchmark.py.gz`
den Beobachter; die drei anderen v1-Skripte bleiben bytegleich. Die Zugehörigkeit
wird anhand der aktuellen Elternkette bis zur ursprünglichen Wrapperidentität
und erneut geprüfter PID, Eltern-PID und Startticks festgestellt. Fehlende,
umgehängte, wiederverwendete oder unaufklärbare Prozesse bleiben Fremdlast.
Der Vorabcheck hat keine Ausnahme für einen Messwrapper.

Das Summary bindet weiterhin den vollständigen konkreten Skriptsatz. Die
Quellenprüfung akzeptiert genau den archivierten v1- oder v2-Satz. Workload,
Grenzwerte, Messformate und native CPU-/RSS-Auswertung bleiben unverändert.
Alle alten Quellen und Belege bleiben erhalten. Zurückgewiesene Serien werden
nicht nachträglich umgedeutet; v2-Belege stammen aus neuen vollständigen Serien.


## Historische v1-Prozessrollen

Die v1-Beobachtung überschreibt die letzte Prozesszeile auch dann, wenn keine
RSS-Probe mehr lesbar ist. Ihr aus der zuletzt gelesenen Kommandozeile
abgeleitetes Rollenlabel kann deshalb vom beobachteten Parent abweichen.
In den Originaldaten von run-3 und run-4 trägt dessen letzte Inventarzeile
`worker`; seine eigenen PID-/PPID-Belege und sämtliche RSS-Proben weisen
weiterhin denselben Parent nach.

Die Auswertung bindet beide eigenen Prozessbelege an genau zwei getrennte
PID-/Startidentitäten, die beiden GNU-time-Hüllen und deren Abstammung.
Nur das finale Parent-Label darf in dieser v1-Anordnung `worker` lauten.
Alle tatsächlichen RSS-Proben müssen weiterhin Rolle, PID, Startticks und
PPID bestätigen; beide Prozesse müssen beobachtet worden sein. Fremde,
doppelte oder wiederverwendete PIDs, vertauschte Probenrollen und eine
abweichende Prozesskette werden abgewiesen. Die Messdateien, Originalskripte,
Hashketten, CPU-/Speicherwerte und Grenzwerte bleiben unverändert.


## Buildgebundene Folgemessungen für Bundle 775

Nach ausdrücklichem erneutem Messauftrag am 21. November 2026 wurde jeder
geänderte 19.w-Corebuild mit derselben unveränderten v1-Messanordnung gemessen.
Die neue Ablage `verification/fixtures/analyzer-resources-builds/<build_sha256>/`
enthält je gemessenem Build die vollständige komprimierte Exporthashkette.
Das Apply-Gate baut die aktuellen Corequellen und wählt ausschließlich deren
exakten Hash; fehlende oder abweichende Daten bleiben ein Fehler.
Der ursprüngliche Nachweis und seine festen Regressionen bleiben erhalten.

| Stufe | Corebuild-SHA-256 | CPU maximal | Laufzeit Median | RSS-Obergrenze |
| --- | --- | ---: | ---: | ---: |
| 19.w.W | `1393923b615fa15db89295f7f690b15ee527287b1d6e7086102477464991b2e2` | 6.79 s | 6.80 s | 363.16 MiB |
| 19.w.R | `6e1e9eb8f528ed065ca7472418714cea5e47fd245e22ec65859fae9b38876daa` | 6.85 s | 6.82 s | 363.25 MiB |
| 19.w.C | `51f32744745365840d4fd7b5a028ccbcb05dbf6859f203ca31f3b20857181a8f` | 6.82 s | 6.79 s | 363.17 MiB |

Jede Serie umfasst einen Warm-up und fünf neue Prozesspaare mit jeweils
1.000 ungekürzten Texten von 166–440 Codepoints. Die CPU-Prüfung addiert
0,02 Sekunden Rundungsreserve; die RSS-Obergrenze bleibt konservativ.
Die tatsächlichen Messwerte sind Referenzbelege, keine Apply-, Sprachkorpus-
oder Releasefreigabe. Ein später erneut geänderter Build braucht neue Messdaten.
