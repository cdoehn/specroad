# Aktive Teststrategie ab 3. Oktober 2026

In `specroad-codex` läuft die vollständige Testsuite ausschließlich parallel.
In `specroad-apply` führt `tools/run_apply_tests.py` den parallelen Volltest aus.
Beim letzten Bundle-Zustand fügt `--final-bundle-state` anschließend einen seriellen
Volltest hinzu. Nur der Erfolg aller vorgesehenen Läufe erlaubt den W/R/C-Commit.
Die technischen Aufrufe stehen in [Testing.md](Testing.md). Die zentrale lokale
Arbeitsanweisung ist `AGENTS.md`.

GitHub-CI startet niemals automatisch. Full Regression wird ausschließlich
manuell per `workflow_dispatch` gestartet und führt die vollständige Testsuite
parallel auf Python 3.10–3.14 aus. In GitHub gibt es keinen seriellen Volltest.
Die frühere 5er-Bundle-Regel bleibt entfernt.

## Manueller Full-Test: ausschließlich parallel

GitHub → Actions → **Full regression (manual)** → **Run workflow** → Branch **dev**.
Optional `commit_sha`: vollständige 40-stellige SHA aus der veröffentlichten
dev-Historie. Ohne Eingabe wird die unveränderliche Dispatch-SHA getestet,
nicht eine später weitergewanderte Branchspitze. Bei einer historischen Auswahl
werden Workflow-SHA und getestete SHA getrennt aufgezeichnet und geprüft.

Jeder manuelle Full-Run führt auf CPython 3.10–3.14 ausschließlich die komplette
parallele Suite mit vier Workern aus. `mode` ist `parallel`; kein serieller
GitHub-Volltest und kein Parallel-/Seriell-Vergleich. Keine automatische
Auslösung und keine Fünferregel. Alte Auswahlwerte `auto` und `both` werden vom
Selektor nur zur Kompatibilität als `parallel` gelesen.

Expliziter Start per CLI, ebenfalls manuell:

```sh
gh workflow run behavior.yml --repo cdoehn/specroad --ref dev
```

Der Button benötigt die Workflowdatei mit `workflow_dispatch` auch im Defaultbranch.
Dieses Bundle verändert weder `main` noch den Defaultbranch. Ist der Workflow dort
nicht registriert oder die alte Eingabemaske noch vorhanden, ist eine bewusste
separate Übernahme/Registrierung nötig. Ohne diese Voraussetzung ist auch ein
CLI-Dispatch kein Umgehungsweg. Der vorhandene private Defaultbranch ist in der
Chat-Arbeitsumgebung nicht live verifiziert; ein Workflow im dev-Snapshot beweist
noch keine verfügbare Schaltfläche.

## Hetzner und expliziter Fallback

Ein kleiner **Ubuntu-24.04-Select-Job** prüft vor den Volltests den Runner
`Hetzner-specroad`: online, frei, eindeutiger Name und alle Labels
`self-hosted, Linux, X64, specroad, hetzner`. Erst dann wird genau diese
Label-Schnittmenge gewählt. Andernfalls werden die Jobs ausdrücklich an
`ubuntu-24.04` gegeben. Keine Blade-15-Auswahl und kein vermischtes Label-Fallback.
Ein API-Befund ist eine Momentaufnahme, keine Reservierung und keine Migration
bereits wartender Jobs.

Der frühere externe Probe-Schritt entfällt aus normalen Bundles. Die manuelle
Verfügbarkeitsprüfung braucht deshalb Zugriff auf die Repository-Runner-API.
Dafür kann ein separat eingerichtetes Actions-Secret **SPECROAD_RUNNER_READ_TOKEN**
verwendet werden (auf dieses Repository beschränkt, Administration: read).
Das normale GITHUB_TOKEN stellt diese Administrationsberechtigung nicht bereit.
Ohne nutzbares Leserecht oder bei API-Ausfall erfolgt ausdrücklich der Hosted-Fallback.
Die Probe gibt keine Tokenwerte aus; der optionale Token wird nur dem Select-Schritt
übergeben, nicht den Testjobs. Dieses Bundle legt selbst keine Secrets an.

`runner=auto` bevorzugt geprüftes Hetzner. Auch `runner=hetzner` überspringt die
Verfügbarkeitsprüfung nicht. `runner=github-hosted` wählt bewusst Ubuntu 24.04.
Der kleine Select-Job benötigt immer GitHub-hosted-Kapazität. Sind dafür keine
Minuten/Kapazitäten vorhanden, ist der Lauf nicht verfügbar bzw. fehlgeschlagen,
nicht erfolgreich. Diese Einschränkung ist kein Anlass, einen ungeprüften offline
Self-hosted-Runner zu wählen.

Die Verlagerung auf manuelle Starts beschleunigt normale Entwicklungszyklen,
verkürzt jedoch nicht automatisch die Laufzeit eines vollständigen Matrixlaufs.
Mit einem Self-hosted-Runner werden die fünf Jobs weiterhin nacheinander ausgeführt.

## Nachweise und Grenzen

Jeder Testjob sichert Test-/Workflow-SHA, Repository, Branch, Ereignistyp,
Run-ID, Attempt, Pythonversion, Runner, parallelen Testreport. Bestehende
CI-Wait-/Evidence-Helfer bleiben für ausdrücklich angeforderte Beobachtung erhalten;
sie starten keine Tests. Details: [CI-Nachweise](CI_Wait.md).

Ein lokaler Volltest bestätigt nicht die GitHub-Matrix. Ein GitHub-Status ersetzt nicht den
gebundenen vollständigen Report. Die verbleibende Python-3.10-Venv-Korrektur muss
im nächsten bewusst gestarteten Full-Test bestätigt werden. Ein alter fehlgeschlagener
Run wird weder gelöscht noch nachträglich als grün dargestellt.

Primärquellen (geprüft am 30.09.2026):
- https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch
- https://docs.github.com/en/rest/actions/self-hosted-runners#list-self-hosted-runners-for-a-repository
