# SpecRoad: parallele Testentwicklung

## Einrichtung und Aufrufe

Die Gruppe `dev` in `pyproject.toml` fixiert pytest 9.0.2 und pytest-xdist 3.8.0.
Das sind bewusst gewählte Versionen, keine Behauptung der jeweils neuesten Version.
Der Core und seine portablen Distributionen enthalten diese Abhängigkeiten nicht.
Ein vollständiges transitive Lockfile wird damit noch nicht behauptet.

```sh
uv venv --python python3 --no-python-downloads .venv
uv pip install --python .venv/bin/python --link-mode copy --group dev
.venv/bin/python -I -B tools/run_tests.py
.venv/bin/python -I -B tools/run_tests.py --workers 4
.venv/bin/python -m pytest
.venv/bin/python -m pytest -n 4 tests/test_core.py
```

Eine vorhandene `.venv` nicht löschen oder blind neu erstellen; nur die Installation der
Entwicklungsgruppe wiederholen. `--link-mode copy` vermeidet Hardlink-Installation unter
PRoot. Der Runner nutzt niemals `-S`; isolierte Tests des abhängigkeitfreien Core weiterhin
schon. Die Testausführung selbst installiert nichts und braucht kein Netzwerk. Nur die
vorherige Abhängigkeitsinstallation benötigt verfügbare Pakete oder einen gefüllten Cache.

Lokal gilt seit dem 21. September 2026 der Standard von vier Workern.
Die vollständige serielle Referenz ist der CI vorbehalten, nicht jedem Clean-Commit.
Nur explizites `auto` lässt xdist die Workerzahl bestimmen. Explizite Zahlen und
`PYTEST_XDIST_AUTO_NUM_WORKERS` erlauben die Anpassung an vorhandene CPU-/Speicherressourcen.
Es gibt keinen stillen seriellen Fallback, keine automatische Wiederholung abgestürzter
Worker und keinen eigenen SpecRoad-Scheduler. Ein schnellerer Lauf ist nicht garantiert;
Prozessstart und parallele Unterprozesse verursachen ebenfalls Aufwand.

## Katalog und Nachweise

Der vollständige Runner erhebt die tatsächlich gesammelte Testmenge und bindet sie an
alle 730 Manifeste, Spezifikationsbytes, Quellstand, Laufzeit und Ausführungskonfiguration.
Alte unittest-Kennungen bleiben erhalten. Native pytest-Funktionen verwenden ihre nodeid.
Die Manifeste wechseln zu `specroad-dev-pytest-v1`; historische unittest-Nachweise werden
nicht umgeschrieben und sind durch die geänderte Manifestbindung nicht mehr aktuell.

Ein Auftrag schreibt optional mit `--evidence build/<eindeutiger-name>.json` genau einen
gebundenen Bericht. Nur der Controller veröffentlicht; Worker schreiben keine gemeinsame
Datei. Bestehende Ziele werden nicht überschrieben. Tests auf Teilmengen, leere oder
abweichende Worker-Sammlungen, fehlende Tests, Collection-Fehler, Setup-/Teardown-Fehler,
Untertestfehler und Worker-Abbrüche ergeben keinen bestandenen vollständigen Nachweis.
Auch Skip/XFail/Unexpected Success sind im vollständigen Gate kein Erfolg.
`--observations` liefert zusätzlich die maschinenlesbare Sammlung und Worker-Zuordnung.

Ein grüner Entwicklungsbericht ist keine Releasefreigabe. Der Status der Requirements
wird durch die Testmigration nicht künstlich erhöht.

## Audit des Ausgangsstands

Basis: Result `specroad_Result_083543_0915_2e6e8b.zip`, sauberer HEAD
`1a187870ffd987225057d506f828e438951e8bd9`, 292 vorhandene Tests.
Die Prüfung fand pro Test private temporäre Projekt-/Buildverzeichnisse, kontrollierte
Core-Unterprozesse und kontextgebundene Mocks statt gemeinsamer fester Arbeitsdateien.
Die unittest-Syntax bleibt nutzbar. Threads werden für die Suite nicht eingeführt.

Ein konkreter Isolationsfehler wurde behoben: Der dynamisch geladene Build-Helfer ließ
`sys.path`-Einträge im Testprozess zurück. Sein Import stellt nun den vorherigen Zustand
wieder her. Eine automatische, pro Test laufende Wächter-Fixture erkennt und restauriert
liegengebliebene Änderungen an Arbeitsverzeichnis, Umgebung, Suchpfad und globalem Zufall.
Sie macht eine unerlaubte Änderung sichtbar, statt sie still zu entschuldigen. Eine
verschwundene aktuelle Arbeitsdirectory wird ebenfalls sicher verlassen.

Die vorhandenen PRoot-sicheren Kopier- und Symlinkregressionen bleiben erhalten.
Tests dürfen ausschließlich eigene Verzeichnisse aufräumen. Neue Tests dürfen keine
festen gemeinsam verwendeten Dateinamen, Ports oder sonstigen externen Ressourcen
beanspruchen. Session-/Modul-Fixtures wären pro Worker zu beurteilen und wären keine
prozessübergreifenden Singletons.

## Verifikationsgrenzen

Der Patch prüft Zwischenstände einzeln. Tatsächliche serielle und parallele Ergebnisse
sind dem Apply-Protokoll und den zugehörigen aktuellen Berichten zu entnehmen, nicht aus
dieser Anleitung abzuleiten. Ein lokaler CPython-Lauf ist kein Nachweis für Pixel/PRoot
oder die ganze CI-Matrix. Keine pauschale Behauptung über alle zukünftigen Tests.

Automatisiert werden ausschließlich Verhalten und maschinenlesbare Datenverträge geprüft.
Keine Tests auf Konsolentexte, Farben, Layout oder Dokumentation; Doctests und fremde
Plugin-Autoloads sind deaktiviert. Die farbige Produktdarstellung bleibt unverändert.
Es werden keine künstlichen Test- oder Suite-Timeouts eingeführt.

## Primärquellen

- https://docs.pytest.org/en/stable/how-to/unittest.html
- https://pytest-xdist.readthedocs.io/en/stable/distribution.html
- https://pytest-xdist.readthedocs.io/en/stable/how-it-works.html
- https://docs.astral.sh/uv/pip/packages/

## CI-Referenz und Abbruchregressionen

`tools/compare_test_runs.py` vergleicht bereits entstandene Berichte. Es verteilt selbst
keine Tests. Die Berichte müssen unabhängige Run-IDs, identische Eingangsbindungen,
identische Testmengen und Identitäten sowie ausschließlich bestandene Ergebnisse haben.
Unterschiedliche Worker-Zuordnung ist erlaubt; fehlende oder doppelte Tests sind es nicht.

Der Workflow `.github/workflows/behavior.yml` ruft in GitHub Actions
`tools/run_ci_tests.py --outdir <frisches-Verzeichnis>` auf. Er führt je Python-
Version erst die vollständige Suite parallel, danach seriell und den Nachweisvergleich
aus. Lokal wird dieser Starter nicht verwendet. Sein GitHub-Umgebungscheck ist nur
ein Schutz vor versehentlichem Start, keine Ausführungs-Sandbox. Ein serielles
Scheitern darf einen vorherigen parallelen Fehler niemals als Erfolg überschreiben.

Die Python-Matrix 3.10–3.14 bleibt vorbereitet; ein GitHub-Repository und ein Push
werden erst in einem späteren separaten Auftrag eingerichtet. Erst ein dortiger
Workflowlauf kann den CI-Erfolg bestätigen. Ein lokaler paralleler Testlauf genügt
nicht als Nachweis der seriellen oder plattformübergreifenden Abnahme.

Historisch verglich die Migrations-Abnahme seriell/2/4/auto mit verschiedenen
Hash-Seeds. Künftige vollständige Vergleiche gehören ausschließlich in die CI.

Regressionsfälle starten absichtlich eigene pytest-Prozesse mit lokalen Mini-Fixtures:
ein absichtlicher Worker-Absturz, unterschiedliche Worker-Sammlungen, Collection-Fehler,
Setup-/Teardown-Fehler, Skip/XFail/Unexpected Success sowie fehlgeschlagene/übersprungene
unittest-Untertests. Die Prüfung wertet ausschließlich strukturierte Ergebnisse und
Exitcodes aus. Diese kleinen Framework-Regressionsfälle benötigen auch beim äußeren
seriellen Referenzlauf xdist. Fehlende Abhängigkeiten führen zu Fehlern, niemals zu Skips.

## OFF-PLAN-Commitfolge dieses Umbaus

| Kennung | Zweck |
|---|---|
| TEST-PARALLEL.a.W | Entwicklungsabhängigkeiten und serielle pytest-Sammlung |
| TEST-PARALLEL.a.R | Prozessisolation einschließlich tatsächlichem Build-Import-Leak |
| TEST-PARALLEL.a.C | Gemeinsamer isolierter Builder-Import |
| TEST-PARALLEL.b.W | pytest-Runner und controllergebundene Evidence |
| TEST-PARALLEL.b.R | Strenge Fehler-/Vollständigkeitsprüfung mit realen pytest-Prozessen |
| TEST-PARALLEL.b.C | Reine Ergebnisbuchhaltung von Framework-Hooks trennen |
| TEST-PARALLEL.c.W | Paralleler Standard, serieller CI-Referenzlauf, TD-002 |
| TEST-PARALLEL.c.R | Parallel-/Abbruchregressionen und fachlicher Laufvergleich |
| TEST-PARALLEL.c.C | Gemeinsame Prozessstart-Policy und konsolidierte Anleitung |

Alle 292 ursprünglichen Verhaltenstests bleiben vorhanden. Hinzu kommen 55 Tests zur
Isolation, Framework-Integration und Nachweisprüfung, insgesamt 347 gesammelte Tests.
Untertests werden ihren übergeordneten Testfällen zugeordnet und nicht als zusätzliche
Plan- oder Requirement-Abdeckung hochgezählt. Keine neuen Produkt-Planpositionen.
