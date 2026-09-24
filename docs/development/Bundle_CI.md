# Bundle-CI ab Bundle 009

Entwicklung auf `dev`; `main` wird vom Patch nicht verändert. Die neuere
Result-Bindung ist maßgeblich, nicht ein älterer noch sauberer Main-Snapshot.

## Pixel

`tools/run_selected_tests.py --test-file tests/test_example.py --expected-tests N
--outdir build/UNIQUE --workers 4` startet genau die angegebenen vollständigen
Testdateien parallel. Nur neue Tests und direkt von der Änderung betroffene bestehende Tests werden je
Commit ausdrücklich benannt. Kein `--sr-gate`, keine lokale Produktsuite und
keine angeblich vollständige Evidence aus einer Auswahl. Vollständigkeit bezieht
sich hier nur auf die Auswahl. Auch übersprungene Tests oder fehlende Reports
lassen dieses Gate scheitern. Dateimengen, Testkennungen, Anzahl und unveränderte
Quellen werden geprüft. Berichte sind neue Dateien außerhalb der Quellen.

## GitHub

`behavior.yml` reagiert auf Pushes zu `dev` und manuelle Workflow-Aufrufe.
Der kleine Select-Job führt keine Tests aus. Nur ein Abschlusscommit mit genau
folgenden Git-Message-Trailern schaltet beim Push die Vollsuite frei:

    SpecRoad-Bundle: 009
    SpecRoad-Bundle-Final: true

Zwischencommits tragen `false`. Betreff und W/R/C-Identität bleiben unverändert.
Alle fünf Bundles, also 020, 025 usw., laufen parallel plus seriell mit Vergleich.
Andere Abschlusscommits laufen nur parallel. CI belegt die ausgecheckte exakte
SHA; fünf Python-Versionen 3.10–3.14 bleiben vorgesehen.

Actions → Behavior tests → Run workflow: Workflow-Branch `dev` wählen; optional
`commit_sha` (40 Hexzeichen) für einen veröffentlichten Zwischencommit angeben.
Ohne SHA wird der gewählte Dev-Stand geprüft. `mode=both` fordert zusätzlich
seriell an und kann den verbindlichen Fünferzyklus nicht abschwächen. Der Commit
muss in der veröffentlichten `dev`-Historie liegen. Eingaben werden nie als Shell
Code interpoliert. Kein `pull_request_target`, keine Schreibrechte oder Secrets.

GitHub zeigt den Run-workflow-Button nur, wenn dieselbe Workflowdatei auf dem
Defaultbranch existiert. Die bisherige Vorlage enthielt bereits
`workflow_dispatch`. Falls die Oberfläche auf `main` noch die alte Eingabemaske
zeigt, muss die neue Workflow-Schnittstelle dort separat bewusst übernommen
werden; dieses Bundle ändert oder merged `main` NICHT. Der Dispatch gegen `dev`
mit den genannten Inputs ist auch über GitHub CLI/API möglich, sobald der
Workflow registriert ist. Änderungen am Defaultbranch und Berechtigungen sind
keine stillschweigenden Patch-Nebenwirkungen.

Ein Push veröffentlicht lokale Commits, ist aber noch kein grüner CI-Nachweis.
Nach einem erfolgreichen Apply ist einmal `git push origin dev` erforderlich,
falls die Abschlussmeldung keinen erfolgreichen Push bestätigt. Kein Force-Push,
keine Änderung von Remote-URLs, Credentials, Tags oder Branch-Protection.

Primärquellen: GitHub Docs, Events that trigger workflows (push/workflow_dispatch)
und Workflow syntax, geprüft am 22.09.2026. Die Workflowdatei ist kein Beweis,
dass GitHub den Lauf tatsächlich angenommen oder bestanden hat.

Ab Bundle 019: siehe CI_Wait.md; CI-Beobachtung und Fünferzyklus.
