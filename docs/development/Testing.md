# APPLY-ONLY-535: Testauswahl in Dev, Ausführung im Apply

Verbindliche Nutzeranweisung vom 1. November 2026; Spezifikation 2.5.2.
Dev schreibt Code und Tests und bereitet echte aufeinanderfolgende
Commitzustände vor. Es führt keine Tests aus. Statische Prüfung, Syntax,
reine Collection und native Paketvalidierung sind erlaubt, aber kein
Verhaltenstest-Erfolg. Die nachfolgenden historischen Abschnitte erklären
ältere Werkzeuge und Nachweise und erteilen keine Dev-Testfreigabe.

## Testplan für jeden Commit

Jeder Zustand erhält eine eigene eindeutige Commit-ID und einen Plan:

```json
{
  "format_version": 1,
  "commit_id": "15.n.R",
  "test_ids": [],
  "test_files": ["tests/test_transport_outbound.py"],
  "reason": "Geänderte Exportverträge und ihre Fehlerfälle vollständig prüfen"
}
```

`test_ids` bezeichnet exakte native Testidentitäten aus der Collection;
alte unittest-Identitäten bleiben erhalten. `test_files` wählt vollständige
Testdateien einschließlich aller gesammelten Varianten. Unbekannte IDs,
fehlende Dateien und leere Pflichtauswahlen werden abgelehnt. Neue oder
geänderte Testdateien müssen vollständig enthalten sein; der Stage-Builder
ergänzt sie automatisch. Für Änderungen an Helfern und Produktcode ergänzt
Dev eine begründete Auswahl aller notwendigen betroffenen Prüfungen.

Die tatsächliche Testanzahl wird im Apply aus der vollständigen Collection
ermittelt. Kein im Dev geschätzter Zähler ersetzt den exakten Mengennachweis.

## Apply-Gate

```sh
.venv/bin/python -I -B tools/run_apply_tests.py \
  --test-plan "$specroad_commit_test_plan" \
  --commit-id "$specroad_commit_id" \
  --outdir "$specroad_fresh_gate_directory"
```

`verification/apply_commit_policy.json` verlangt bei neuen Ständen einen
Testplan. Alte Fixtures/Results ohne diese Policy behalten ihren alten
Vertrag; bereits veröffentlichte Bundles werden nicht umgeschrieben.

Die Menge lautet: **gefilterte fällige N=3-Gruppe vereinigt mit Pflichtauswahl**.
Nummern und Rotationsanker in `verification/apply_test_numbers.json` bleiben
append-only. Nur echte erfolgreiche Commits schalten die First-Parent-
Rotation weiter. Der globale aktuelle Laufzeitfilter entfernt die langsamsten
`floor(gültig gemessene aktuelle Tests / 5)` aus der Rotationsgruppe;
unbekannte/ungültige Messungen bleiben zugelassen. Pflichtauswahl überstimmt
Filter und Gruppe. Überlappungen laufen einmal pro Commit. Jeder andere
Commitzustand erhält sein eigenes Gate. Kein zusätzlicher Schlusslauf.

Alle ausgewählten Tests laufen mit vier xdist-Workern und `--dist worksteal`.
Die vorhandene automatische SQLite-Messung speichert Setup/Call/Teardown
sofort dauerhaft, auch für zusätzlich aufgenommene langsame Pflichttests.
Historie, Seeds und bestehende Messwerte werden nicht gelöscht. Der neueste
Versuch bleibt maßgeblich; ein ungültiger neuer Versuch fällt nicht auf alte
Erfolge zurück. Eine neue Messung ändert nicht die bereits gebundene Auswahl.

`selection.json` Format 3, Auswahlbindung v4 und
`stable_modulo_partition_with_latest_runtime_filter_and_required_tests`
weisen den genauen Quellstand, HEAD, Commit-ID, Pflichtplan, Snapshot,
Testnummern, Vereinigungsmenge, zusätzlich aufgenommene und wieder zugelassene
langsame Tests nach. `full_suite_passed` bleibt `null`.
`tools/verify_apply_commit.py` prüft diesen Nachweis unabhängig erneut,
ohne Tests auszuführen. Fehler, Skips, fehlende Tests, veränderte Daten oder
fehlende Messphasen erlauben keinen Commit.

## Bundles und Korrekturen

Siehe [Apply-Commitpläne](Apply_Commit_Plans.md). Ein gemeinsamer Entrypoint
stellt jeden Zustand erst nach dem vorherigen erfolgreichen Commit her.
Bei Fehlern endet das Bundle. Erfolgreiche Commits, Index und aktuelle
Dateien bleiben erhalten. Der vollständige Rest steht maschinenlesbar im
PatchHarbor-Ausführungslog und damit im Result. Kein Modell ist beim
Ausführen, Messen oder Committen beteiligt. Das Korrekturbundle bindet das
neue Fehler-Result und führt die offenen Commit-IDs fort.

## Manuelle Tests und CI

Nur ein gesonderter ausdrücklicher Nutzerauftrag erlaubt einen manuellen
Testlauf in Dev, etwa eine volle Suite oder eine Nachholmessung. Die
vorhandenen Starter bleiben dafür verfügbar. `run_selected_tests.py` ist
kein normaler Entwicklungsschritt mehr. Manuelle Auswahlen sind ungefiltert
und messen ebenfalls. Collection allein startet keine Testkörper.

GitHub-CI bleibt ausschließlich vom Nutzer manuell über workflow_dispatch
gestartet. Alle Tests laufen über die bestehende zeitgewichtete Paketmatrix
auf CPython 3.10–3.14. Keine automatische CI, keine automatische Vollsuite
zur Messung. Die Anleitungen in [CI_Packages.md](CI_Packages.md) gelten weiter.

## Historische Infrastruktur und Nachweise

Die folgenden älteren Beschreibungen dokumentieren frühere Teststrategien.
Bei Aussagen zu Dev-/Apply-Umfang gilt ausschließlich die obige Regel.

# SpecRoad: parallele Testentwicklung

## Einrichtung und Aufrufe

Die Gruppe `dev` in `pyproject.toml` fixiert pytest 9.0.2 und pytest-xdist 3.8.0.
Das sind bewusst gewählte Versionen, keine Behauptung der jeweils neuesten Version.
Der Core und seine portablen Distributionen enthalten diese Abhängigkeiten nicht.
Ein vollständiges transitive Lockfile wird damit noch nicht behauptet.

```sh
uv venv --python python3 --no-python-downloads .venv
uv pip install --python .venv/bin/python --link-mode copy --group dev
.venv/bin/python -m pytest -n 4 tests/test_core.py
```

Eine vorhandene `.venv` nicht löschen oder blind neu erstellen; nur die Installation der
Entwicklungsgruppe wiederholen. `--link-mode copy` vermeidet Hardlink-Installation unter
PRoot. Der Runner nutzt niemals `-S`; isolierte Tests des abhängigkeitfreien Core weiterhin
schon. Die Testausführung selbst installiert nichts und braucht kein Netzwerk. Nur die
vorherige Abhängigkeitsinstallation benötigt verfügbare Pakete oder einen gefüllten Cache.

Lokal gilt seit dem 21. September 2026 der Standard von vier Workern.
Sowohl in der Codex-Entwicklung als auch im PatchHarbor-Apply laufen alle
Zwischenstände ausschließlich parallel, einschließlich des letzten Zustands.
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

Der Patch prüft Zwischenstände einzeln. Die Entwicklungsumgebung liefert nur
gezielte parallele Ergebnisse; das spätere Apply-Protokoll belegt die dortige
vollständige parallele Suite vor jedem Commit.
Maßgeblich sind diese Protokolle
und die zugehörigen aktuellen Berichte; diese Anleitung ist kein Ausführungsnachweis.
Ein lokaler CPython-Lauf ist kein Nachweis für Pixel/PRoot
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
Version ausschließlich die vollständige Suite parallel aus. Der lokale Apply
führt ebenfalls genau einen vollständigen parallelen Lauf je Zwischenstand aus.
Der jeweilige Lauf muss vor dem Commit erfolgreich sein.

Die Python-Matrix 3.10–3.14 läuft im ausschließlich manuell gestarteten Workflow.
Erst der exakt gebundene tatsächliche Workflowlauf kann den CI-Erfolg bestätigen. Ein lokaler paralleler Testlauf genügt
nicht als Nachweis der plattformübergreifenden Abnahme.

Historisch verglich die Migrations-Abnahme seriell/2/4/auto mit verschiedenen
Hash-Seeds. Diese historischen Vergleiche sind keine aktuelle Ausführungsregel.

Regressionsfälle starten absichtlich eigene pytest-Prozesse mit lokalen Mini-Fixtures:
ein absichtlicher Worker-Absturz, unterschiedliche Worker-Sammlungen, Collection-Fehler,
Setup-/Teardown-Fehler, Skip/XFail/Unexpected Success sowie fehlgeschlagene/übersprungene
unittest-Untertests. Die Prüfung wertet ausschließlich strukturierte Ergebnisse und
Exitcodes aus. Diese kleinen Framework-Regressionsfälle benötigen ebenfalls xdist.
Fehlende Abhängigkeiten führen zu Fehlern, niemals zu Skips.

## Historische OFF-PLAN-Commitfolge der pytest-Migration

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


## Historische Testauswahl

Die frühere fachbezogene Apply-Auswahl und die am 15. Oktober 2026 eingeführte
Gerade/Ungerade-Rotation sind historische Verfahren. Ab Bundle 295 gilt die
oben beschriebene Drittelrotation.
`run_selected_tests.py` bleibt das Hilfsmittel für gezielte Entwicklungstests.
