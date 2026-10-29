# Dauerhafte Testlaufzeitmessung

Alle Befehle aus der Dev-Arbeitskopie ausführen. Keine Dienste erforderlich.
Die SQLite-Datei liegt im vorhandenen ignorierten build-Bereich. Jeder vom
Controller empfangene setup/call/teardown-Report wird sofort mit FULL-Synchronisierung
committed. Fertige erfolgreiche Tests bleiben nach einem Prozessabbruch erhalten.
Nicht empfangene oder nicht committede Phasen bleiben offen. Daten verschiedener
Testversuche werden niemals zu einem Test zusammengesetzt.

## Erstmalige Messung

```bash
.venv/bin/python -I -B tools/measure_test_runtimes.py --journal build/test-runtime-measurements.sqlite3 --workers 4 --all
```

## Lesender Status

```bash
.venv/bin/python -I -B tools/measure_test_runtimes.py --journal build/test-runtime-measurements.sqlite3 --status
```

Der JSON-Bericht nennt vollständige Messungen, gespeicherte Phasen und fehlende
Testidentitäten. Nach einem Abbruch genau während eines SQLite-Commits kann ein
lesender Status zunächst eine notwendige Transaktionswiederherstellung melden.
Der ausdrückliche folgende Messaufruf übernimmt diese native SQLite-Recovery.

## Nur fehlende Tests nachholen

```bash
.venv/bin/python -I -B tools/measure_test_runtimes.py --journal build/test-runtime-measurements.sqlite3 --workers 4 --remaining
```

## Frei zusammengestellte Gruppen

`--test-file tests/datei.py` und `--test-id <stabile-ID-oder-Node-ID>` sind
beliebig oft kombinierbar. Auch mehrere `--selection-file build/gruppe.json`
sind möglich. Beispiel einer selbst geschriebenen Auswahl (Platzhalter ersetzen):

```json
{"test_files":["tests/datei_a.py","tests/datei_b.py"],"test_ids":["tests/datei_c.py::test_einzelfall"]}
```

```bash
.venv/bin/python -I -B tools/measure_test_runtimes.py --journal build/test-runtime-measurements.sqlite3 --workers 4 --selection-file build/gruppe.json
```

Die Auswahl ist eine Vereinigung. Schon vollständig gemessene Tests werden
ausgelassen, nichts wird automatisch überschrieben. Unbekannte Auswahlen
werden abgewiesen. Quelle, komplette Collection, Plattform und Workerzahl
müssen zur Messbasis passen. Bei Änderungen eine neue Journaldatei verwenden;
alte Daten nicht löschen oder als passenden Nachweis ausgeben.

## Vollständige Messabdeckung exportieren und einmalig einfrieren

```bash
.venv/bin/python -I -B tools/measure_test_runtimes.py --journal build/test-runtime-measurements.sqlite3 --export build/test-runtime-coverage.json
.venv/bin/python -I -B tools/freeze_test_runtime_baseline.py --measurement build/test-runtime-coverage.json
```

Export und feste Ausschlussliste verlangen erfolgreiche, vollständige Laufzeiten
aller gebundenen Tests. Zusammengeführte Teilmessungen sind ausdrücklich kein
einzelner erfolgreicher Vollsuitelauf. Die feste Liste bleibt unveränderlich.
N=3-Apply-Filter, ungefilterte gezielte Dev-Tests und manuelle Vollsuite bleiben
wie in Spezifikation 2.5 geregelt. Ein bereits gestarteter alter Lauf ohne
dauerhafte Phasenspeicherung erhält dadurch keine rückwirkenden Laufzeitdaten.
