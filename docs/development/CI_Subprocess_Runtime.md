# CI-Reparatur: Laufzeitpfad isolierter Python-Unterprozesse

## Anlass und Bindung

OFF-PLAN `CI-SUBPROCESS-RUNTIME`, Bundle **040**. Der Produktstand bleibt
**225/885**, letzter Produktcommit **5.o.C**, nächster **5.p.W**.

Maßgebliche Ausgangsbasis ist `specroad_Result_144731_0930_5c8967.zip`:
Commit `e1133e191b82dea9ef327d87f0f4c2582d919647`, sauberer Arbeitsbaum,
Bundle 039 lokal erfolgreich. Der fehlgeschlagene CI-Run ist **36732090139**,
Attempt **1**. Die über `tools/extract_ci_evidence.py` zurückgewonnenen Archive
enthalten die vollständigen fünf Matrixreports und die zugehörigen Logs.
Die im Evidence-Summary gespeicherten Dateiprüfsummen wurden überprüft.

Die Reports weisen für CPython 3.10–3.13 jeweils dieselben **84 fehlgeschlagenen
Testidentitäten** aus, neben 4.874 erfolgreichen. CPython 3.14 meldet alle
4.958 Tests erfolgreich. Die Unterprozesse enden vor ihrem Python-Programm
mit Exitcode 127: Die jeweils benötigte `libpython`-Bibliothek wird nicht
gefunden. Im Elternprozess ist `LD_LIBRARY_PATH` gesetzt, der gemeinsame
Starter `tests/support/processes.py` verwirft diese Variable jedoch.

Die gesicherte CI von Bundle 038 zeigt dasselbe Fehlermuster. Das ist ein
Test-Infrastrukturfehler; aus diesen Befunden folgt kein nachgewiesener
fachlicher Fehler der normativen Idempotenz.

## Eng begrenzte Korrektur

`run_python` übernimmt zusätzlich exakt die benannte Variable
`LD_LIBRARY_PATH`, sofern sie im Elternprozess vorhanden ist. Der Wert wird
weder ergänzt noch normalisiert oder aus einem angenommenen Installationsort
rekonstruiert. Fehlende Werte bleiben fehlend, vorhandene Werte werden erhalten.
Damit bleibt die vom vertrauenswürdigen Test-/Runner-Setup konfigurierte
Laufzeitumgebung auch für einen ausdrücklich ausgewählten Interpreter nutzbar.

Die übrige Isolation bleibt bestehen: `PATH` ist leer; unter anderem
`GH_TOKEN`, `GITHUB_TOKEN`, beliebige Geheimnisvariablen, `PYTHONPATH`,
`PYTHONHOME`, `VIRTUAL_ENV`, `LD_PRELOAD`, `LD_AUDIT` und `BASH_ENV` werden
nicht weitergegeben. Die bereits erlaubten Windows-/Temporärvariablen bleiben
unverändert. stdin bleibt geschlossen, es gibt weder Shell noch Testtimeout
noch automatische Wiederholung. Die Elternumgebung wird nicht verändert.

Dies ist keine Sandbox und keine neue Vertrauensprüfung von Bibliothekspfaden:
Der bereits gestartete Testprozess und sein Runner-Setup sind vertrauenswürdig.
Es werden keine allgemeinen Loader-Variablen freigeschaltet und keine
Produkt-Laufzeitabhängigkeiten eingeführt.

## Regression und lokale Auswahl

Die neue Datei `tests/test_process_environment.py` enthält **13** Verhaltenstests.
Sie prüfen die exakte Prozessumgebung, fehlende/leere/mehrteilige Pfade,
Geheimnis- und Loader-Injektionsvariablen, unveränderte Prozessverträge und
wirklich gestartete isolierte Python-Prozesse einschließlich Standardbibliotheks-
Erweiterungsmodulen. Keine Oracles für menschliche Ausgabe oder Dokumentation.

Die negative Vorabkontrolle mit dem alten Starter ergab sechs fehlgeschlagene
und sieben erfolgreiche Tests; dieselben 13 Tests bestanden nach der Korrektur
in der externen Arbeitsumgebung. Das ist kein Pixel-Apply- oder CI-Erfolgsnachweis.

Das Pixel-Gate wählt exakt die **84** im gebundenen CI-Report fehlgeschlagenen
Testidentitäten aus den **44** direkten Aufruferdateien sowie alle **13** neuen
Tests aus: **97 Tests**. Die Übersetzung der alten Reportidentitäten in pytest-
Node-IDs stammt aus dem Katalogreport desselben Attempts. Die aktuelle
Katalogprüfung bestätigt ihre Existenz; sie führt keine Testkörper aus.

Der Entrypoint nennt die 45 betroffenen Dateien vor dem Gate und protokolliert
die exakte Node-ID-Auswahl. Er verwendet `tools/pytest_entry.py`, die bestehenden
Beobachtungs-/Validierungsfunktionen und pytest-xdist mit vier Workern.
`selected_test_ids_only` ist ausdrücklich ein Teilnachweis mit
`full_suite_passed: null`, nicht die Behauptung einer vollständigen Dateiauswahl.
Keine lokale Vollsuite und kein lokaler Parallel-/Seriell-Vollvergleich.

## CI-Abnahme und Ergebnisgrenzen

Bundle **040** ist durch fünf teilbar. Der unveränderte Workflow
`.github/workflows/behavior.yml` wählt deshalb für die CPython-Matrix
**3.10, 3.11, 3.12, 3.13, 3.14** den Modus **both**:
komplette parallele Suite, komplette serielle Suite und Nachweisvergleich.
Die bestehenden Tests werden nicht deaktiviert, übersprungen oder abgeschwächt.

Vor dem einzigen Abschlusscommit erfolgt die bestehende Hetzner-Probe mit
explizitem Ubuntu-24.04-Fallback. Nach dem normalen Push bindet
`tools/watch_bundle_ci.py` ausschließlich den neuen Abschlusscommit, Run und
Attempt. Kein erneutes historisches Nachladen ist zur bekannten Diagnose nötig.
Logs, Matrixreports, Vergleich und Dateiprüfsummen werden mit dem vorhandenen
Evidence-Transport im nächsten PatchHarbor-Result gesichert.

`LOCAL APPLY` und `CI` werden getrennt gemeldet. Fehlgeschlagene oder nicht
verfügbare CI ist kein Erfolg und führt nicht zum Zurücksetzen lokaler Commits.
Erst das nächste Pixel-Result bestätigt Apply und den tatsächlichen neuen CI-Stand.
