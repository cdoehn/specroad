# Testlaufzeiten: automatische Historie und aktuelle Apply-Auswahl

Seit RUNTIME-AUTO-521 speichert jeder normale pytest-Lauf die nativen Phasen
sofort dauerhaft. Kein zusätzlicher Messaufruf und keine Vollsuite sind nötig.
Die Projektpolicy `verification/test_runtime_policy.json` verbindet Dev und
Apply mit `../exchange/specroad-test-runtime-history.sqlite3`. Diese SQLite-
Datei wird nicht als Produktpayload verteilt. Ohne Projektpolicy liegt der
Speicher im lokalen `build/test-runtime-history.sqlite3`.

Ein Teststart invalidiert den bisherigen aktuellen Wert. Nur drei erfolgreiche
Phasen desselben Versuchs liefern wieder eine gültige Dauer. Fehler und Abbruch
bleiben wiederholungspflichtig; kein Rückgriff auf ältere erfolgreiche Werte.
Alle Versuche und ihre Phasen bleiben erhalten. Parallel gestartete Versuche
werden atomar geordnet, unabhängig von ihrer Abschlussreihenfolge.

Nur Apply ermittelt aus den aktuellen gültigen Werten der vorhandenen Tests
vor jedem Lauf das langsamste Fünftel und zieht es von der fälligen N=3-Gruppe
ab. Neue oder ungültige Werte werden nicht ausgeschlossen. Dev und manuelle
Volltests laufen ungefiltert. `runtime-snapshot.json` bindet die Auswahl dieses
Laufs; neue Messungen verändern erst die nächste Auswahl. `selection.json`
verwendet dafür Auswahlbindung v3 und
`stable_modulo_partition_with_latest_runtime_filter`.

Bestehende Messjournale und die Baseline bleiben historische Quellen. Ihr
Import erzeugt keine neue Testevidenz. Datenbankfehler lassen das Gate scheitern;
Tests werden deshalb weder gelöscht noch als bestanden gewertet. Control,
Watcher, Testnummern und der Commitrotationsanker bleiben unverändert.

## Historische Bedienung der ausdrücklich beauftragten Einmessung

Die folgende Anleitung dokumentiert den bisherigen expliziten Messweg. Seine
unveränderlichen Journale und Exporte bleiben lesbar; die feste Liste steuert
bei vorhandener aktueller Projektpolicy nicht mehr den automatischen Apply-Lauf.

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

## Ausdrücklich beauftragte Aktualisierung am 30. Oktober 2026

RUNTIME-REFRESH-520 ersetzt nach Nutzerfreigabe einmalig die feste Liste durch
die Rangfolge aus 22.263 erhaltenen historischen Messungen und 215 ergänzend
gemessenen neuen Tests. 4.495 der 22.478 Identitäten sind ausgeschlossen.
Quellstände und historische Übernahmen bleiben in den vorhandenen
Provenienzfeldern erhalten; dies ist kein neuer Vollsuite-Erfolgsnachweis.
Die Originaljournale werden weder umgeschrieben noch zu einem vermeintlich
einheitlichen Quellstand erklärt. Messzeiten enthalten setup, call und teardown.

Der normale Freeze-Befehl verweigert weiterhin das Überschreiben. Die
ausdrücklich beauftragte Datenänderung erfolgt state-gebunden über PatchHarbor.
Weitere Updates brauchen erneut einen Auftrag; Nachholmessungen ändern die
Ausschlussliste nicht selbst. N=3, gezielte Dev-Tests und manuelle Volltests
behalten ihr bisheriges Verhalten. Einzelheiten und Hashbindungen stehen im
Implementierungsplan unter RUNTIME-REFRESH-520.
