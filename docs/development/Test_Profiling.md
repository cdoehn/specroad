# Test-Profiling

`tools/profile_tests.py` bereitet explizite Diagnoseausführungen mit cProfile,
strace und Linux-Prozesszählern vor und speichert deren Daten dauerhaft.
Das Werkzeug gehört zur Entwicklungsinfrastruktur. Es ersetzt kein Apply-Gate
und startet weder Control noch Dienste, CI oder automatische Wiederholungen.
Es gelten die [Freigaberegeln für manuelle Tests](Testing.md#manuelle-tests-und-ci).

## Auswahl

Mit dem vorhandenen Entwicklungsinterpreter auf einem Linux-Host aufrufen.
pytest und pytest-xdist müssen installiert sein; `strace` muss im `PATH`
stehen und eigene Kindprozesse verfolgen können. Das Werkzeug installiert nichts.
Die folgenden `run`-Befehle führen Tests aus und benötigen die entsprechende
ausdrückliche Beauftragung:

```sh
.venv/bin/python tools/profile_tests.py run --all
.venv/bin/python tools/profile_tests.py run --slowest 10
.venv/bin/python tools/profile_tests.py run --test tests/test_core.py
.venv/bin/python tools/profile_tests.py run --test 'tests/test_example.py::test_value[one]'
.venv/bin/python tools/profile_tests.py run --test tests -k 'publication or prepare'
.venv/bin/python tools/profile_tests.py run -k 'merge and not recovery' -m 'not slow'
.venv/bin/python tools/profile_tests.py run --selection build/profile-selection.json
```

Die Beispielnamen durch tatsächlich vorhandene Testpfade/-IDs ersetzen.
`--test` ist wiederholbar und nimmt Dateien, Verzeichnisse oder vollständige
pytest-IDs einschließlich Parametern an. Eine Auswahl-JSON enthält ein nichtleeres
Array solcher Zeichenketten; sie kann mit `--test` kombiniert werden:

```json
[
  "tests/test_example.py::test_value[one]",
  "tests/merge_tests/test_example.py"
]
```

Überlappende Auswahlen bilden eine Vereinigung; jeder Test wird einmal ausgeführt.
Pfade beziehen sich auf die Repository-Kopie des aufgerufenen Skripts. Alle
Auswahlen müssen unter deren `tests/` liegen. `-k` und `-m` wirken wie in pytest;
ohne expliziten Pfad filtern sie die gesamte Testsammlung. Die Filter sind auch
mit `--all` oder `--slowest N` kombinierbar; bei `--slowest` wird zuerst gefiltert
und dann innerhalb der verbleibenden Tests gerankt. Leere, unbekannte oder
mehrdeutige Auswahlen führen zu einem Fehler vor der Testausführung.

`--slowest 10` verwendet ausschließlich die neuesten tatsächlich begonnenen,
vollständigen, gültigen Versuche mit bestandenen Setup-/Call-/Teardown-Phasen.
Die Summe dieser drei Phasen entscheidet; Gleichstand wird nach Testidentität
aufgelöst. Neue, entfernte, zuletzt fehlgeschlagene oder unvollständige Tests
sowie bloße Baseline-Schätzwerte gehen nicht ins Ranking ein. Es werden bis zu
zehn passende Tests gewählt; bei weniger vorhandenen Messungen entsprechend
weniger. `--slowest N` erlaubt auch eine andere positive Anzahl.

Standardquelle ist die normale Laufzeithistorie der zur aufgerufenen Kopie
gehörenden Entwicklungslinie. `--history DATEI` überschreibt diese ausschließlich
lesende Rankingquelle. Es gibt keinen stillen Rückgriff auf die andere Linie
oder einen älteren Erfolg.

## Ausführung und Messgrenzen

Jeder Lauf erhält eine UUID und einen privaten Quellsnapshot. Der native
Snapshot-Helfer kopiert öffentliche Projektdateien einschließlich uncommitteter
Änderungen, jedoch keine Git-Verwaltung, lokale PatchHarbor-Konfiguration oder
Zugangsdaten. Quellhash und Dateiinventar werden gespeichert; die kopierten
Quelldateien und Unterverzeichnisse werden schreibgeschützt. Die Repository-Wurzel
der Kopie bleibt für deren private `build/`-Dateien beschreibbar.

Eine frische Collection im Snapshot löst die Auswahl auf und speichert ihre
pytest-IDs und stabilen Testidentitäten. Danach startet genau eine native
pytest-xdist-Sitzung mit worksteal. Konfiguration, Root und Conftest-Grenze
werden ausdrücklich auf den Snapshot gesetzt; die importierte Produkt- und
Verifikationskopie wird geprüft. Ein Worker-Abbruch wird nicht automatisch
wiederholt. Die ursprüngliche Arbeitskopie kann danach weiterbearbeitet werden.

`--worker-limit` begrenzt die parallelen Worker, standardmäßig auf zehn.
Verfügbare CPUs, Affinität, cgroup-Quoten, Auswahlgröße und die bestehende
Begrenzung verschachtelter Testläufe zählen mit. Jeder Worker wird auf eine
zugelassene logische CPU gebunden, zunächst auf unterschiedliche physische Kerne.
Testprozesse haben mindestens Nice +10. Es gibt keine zusätzlichen Test- oder
Suite-Timeouts. Das Werkzeug läuft im Vordergrund; Strg+C beendet ausschließlich
seine eigenen gestarteten Prozessgruppen und erhält vorhandene Daten.

Erfasst werden:

- cProfile getrennt für Setup, Testkörper und Teardown: Aufrufzahlen, Eigenzeit,
  kumulierte Zeit und Aufruferbeziehungen sowie native `.pstats`-Dateien.
- strace mit Zeitstempel, Syscall-Dauer, aufgelösten Dateideskriptoren und
  Kindprozessen (`-ff -ttt -T -yy -s 64`), als getrennte Rohdateien je PID/TID.
- Phasengrenzen mit PID, nativer Thread-ID, Epoch- und monotoner Zeit sowie
  CPU-Zeit, I/O-Zählern, Seitenfehlern und Kontextwechseln.
- Sekündliche `/proc`-Momentaufnahmen des gestarteten Prozessbaums einschließlich
  RSS-, Scheduler- und I/O-Daten. Kurzlebige Prozesse können zwischen diesen
  Stichproben liegen; ihre Syscalls bleiben in strace erhalten.
- Auf Python ab 3.12 optionale Zeilen-/Rückkehrereignisse der eigentlichen
  Testfunktion über `sys.monitoring`. Fehlt die API oder ein freier Werkzeugplatz,
  wird dies explizit gespeichert. Fixtures und tiefe Aufrufketten deckt cProfile ab.

cProfile erfasst den ausführenden Testthread; zusätzliche Threads und Python-
Unterprozesse erhalten kein eigenes cProfile. strace erfasst auch deren Syscalls.
Die Phasengrenzen und Prozessbeziehungen erlauben eine spätere zeitliche Zuordnung;
gemeinsame Session-Fixtures und weiterlebende Hintergrundprozesse müssen dabei
gesondert berücksichtigt werden. Instrumentierung verändert Laufzeiten deutlich.
Diese Werte sind Diagnosewerte und keine unbeeinflussten Benchmarkzeiten.

Die native Laufzeithistorie des nicht registrierten Snapshots bleibt in dessen
privatem `build/`. Eine veraltete Policy, die aus diesem Bereich heraus schreiben
würde, wird vor Collection und Testausführung abgewiesen. Somit ersetzen die
instrumentierten Zeiten keine normalen Messwerte der Apply-Linien.

## Datenbank, Status und Rohdaten

Standarddatenbank: `build/profiling/profiles.sqlite3`; mit `--database DATEI`
änderbar. Laufverzeichnisse liegen daneben unter `runs/<UUID>/`. Die Datenbank
wird erst beim ausdrücklich gestarteten `run` angelegt. Schema und Formatmarker
unterscheiden sie von Laufzeithistorien; fremde Datenbanken werden nicht
umgewidmet. Messdaten gehören in `build/` oder außerhalb der Quellinputs.

| Tabelle | Inhalt |
| --- | --- |
| `runs` | Herkunft, Quell-/Auswahlhash, Einstellungen, Befehl, Status, Fehler |
| `tests` | Exakte Auswahl, Rankingherkunft, Worker/CPU/PID/TID und Ergebnis |
| `phases` | Setup-/Call-/Teardown-Grenzen und Ressourcenstände |
| `python_functions` | Funktionsidentität, Aufrufzahlen und Zeiten je Phase |
| `python_callers` | Aufruferbeziehungen und deren Messwerte |
| `artifacts` | Rohdateiart, Zuordnung, Größe, SHA-256 und Importstatus |
| `artifact_chunks` | Verlustfrei komprimierte Rohdateien in begrenzten Blöcken |

Worker schreiben Phasen und Python-Aufrufdaten mit kurzen SQLite-Transaktionen.
Nach dem Prozessende werden Rohprofile, Traces, Ressourcenstichproben,
Auswahlbelege und Logs in die Datenbank übernommen. Rohdateien und Snapshot
bleiben zusätzlich erhalten. Die Datenbank enthält somit die Messdaten selbst
und nicht nur Dateiverweise. Während `indexing` sind noch nicht alle Rohdateien
übernommen. Bei einem Abbruch bleiben unvollständige Importe als solche markiert;
die erhaltenen Rohdateien ermöglichen spätere Reparatur/Auswertung. Ein hart
getöteter Koordinator kann einen offenen Status hinterlassen; dieser ist kein
Nachweis, dass der Prozess noch lebt.

Ein erfolgreicher Lauf verlangt passende native Beobachtungen, vollständige
Profilphasen, Worker-Traces, unveränderte Snapshot-Quellen und abgeschlossenen
Rohdatenimport. Exitcode 0 allein genügt nicht. `passed` bezieht sich auf die
gespeicherte Diagnoseauswahl, niemals auf einen Apply-Commit oder eine Freigabe.
Teilfehler und übersprungene Tests bleiben sichtbar.

Die folgenden Befehle starten keine Tests und führen keine Collection aus:

```sh
.venv/bin/python tools/profile_tests.py status
.venv/bin/python tools/profile_tests.py status --run UUID
.venv/bin/python tools/profile_tests.py export --artifact 123 --output build/exported.pstats
```

`status` liefert JSON, mit `--run` einschließlich Testzuständen und Artefakt-IDs.
`export` rekonstruiert ein vollständiges Artefakt aus der Datenbank, prüft Größe
und SHA-256 und veröffentlicht es erst danach. Bestehende Zieldateien werden
nicht überschrieben. Alle Unterbefehle unterstützen `--database`.
Für die Sicherung einer laufenden SQLite-Datenbank die SQLite-Backupfunktion
verwenden; eine isolierte Kopie der Hauptdatei ohne WAL kann unvollständig sein.
Rohtraces enthalten Dateipfade und gekürzte Syscall-Argumente und bleiben lokale
Diagnosedaten, kein Bestandteil eines Produkt-Payloads.
