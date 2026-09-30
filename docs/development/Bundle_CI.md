# Aktive Teststrategie ab Bundle 041

Nutzerentscheidung vom 30. September 2026. Diese Regel ersetzt die automatische
Bundle-CI und den Fünferzyklus vollständig. Produktplan weiterhin 225/885;
Testinfrastruktur ist OFF-PLAN, keine neue Produktfunktion.

## Normales Bundle: nur Pixel-Gates und Push

Pro Commit ausschließlich alle neuen Tests und direkt betroffene bestehende Tests.
Bei kleinen Änderungen werden genaue Node-IDs statt ganzer benachbarter Dateien
gewählt. Der Entrypoint nennt Dateien und Testauswahl vor jedem Gate. pytest-xdist,
maximal vier Worker, kein serieller Fallback, keine automatische Vollsuite,
kein lokaler Parallel-/Seriell-Vollvergleich und keine künstlichen Testtimeouts.
Fehlende, übersprungene oder fehlerhafte ausgewählte Tests verhindern den Commit.
Keine Tests auf Konsolentext, Farben, Layout, Dokumentation oder Markdown.

Nach jedem erfolgreichen Gate genau der zugehörige Commit. Nach dem letzten
Commit normaler Push der exakten Abschluss-SHA nach origin/dev. Keine automatische
Runnerabfrage, kein Start/Entdecken/Abwarten einer CI und keine automatische
CI-Evidence-Sammlung im normalen PatchHarbor-Entrypoint. Auch eine alte grüne CI
wird nicht als Nachweis des neuen Commits verwendet.

    LOCAL APPLY: SUCCESS / FAILED
    PUSH: SUCCESS / FAILED / UNAVAILABLE / NOT RUN
    FULL CI: NOT RUN (manual only)

Ein fehlgeschlagener späterer Push setzt erfolgreiche lokale Commits nicht zurück.
Bei abweichendem Remote-Stand: nicht forcen, zunächst den tatsächlichen Stand
prüfen. Kein Reset, Clean, Release-Tag, main-Update oder rekursiver PatchHarbor-Aufruf.
Bundle-Trailer sind nur Metadaten, keine Auslöser. Weder 040, 045 noch andere durch
fünf teilbare Nummern veranlassen automatisch irgendeinen Full-Test.

## Manueller Full-Test: immer parallel UND seriell

GitHub → Actions → **Full regression (manual)** → **Run workflow** → Branch **dev**.
Optional `commit_sha`: vollständige 40-stellige SHA aus der veröffentlichten
dev-Historie. Ohne Eingabe wird die unveränderliche Dispatch-SHA getestet,
nicht eine später weitergewanderte Branchspitze. Bei einer historischen Auswahl
werden Workflow-SHA und getestete SHA getrennt aufgezeichnet und geprüft.

Jeder manuelle Full-Run führt auf CPython 3.10, 3.11, 3.12, 3.13 und 3.14 die
komplette parallele Suite (vier Worker), die komplette serielle Suite und den
vorhandenen Nachweisvergleich aus. `mode` ist immer `both`. Kein paralleler-only
Button, keine täglichen/zeitgesteuerten Läufe, keine automatische Fehler-Wiederholung.
`fail-fast: false` erhält die vollständige Diagnose über alle Versionen. Ein bereits
fehlgeschlagener Parallelmodus wird nicht durch einen seriellen Erfolg überschrieben.
Die Fünferregel existiert nicht mehr. `auto` wird im Auswahlhelfer allein zur
Kompatibilität mit alten bereits registrierten Eingabemasken als `both` gelesen.

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
Run-ID, Attempt, Pythonversion, Runner, beide Testreports und Vergleich. Bestehende
CI-Wait-/Evidence-Helfer bleiben für ausdrücklich angeforderte Beobachtung erhalten;
sie starten keine Tests. Details: [CI-Nachweise](CI_Wait.md).

Ein lokaler Teilnachweis ist kein Full-Pass. Ein GitHub-Status ersetzt nicht den
gebundenen vollständigen Report. Die verbleibende Python-3.10-Venv-Korrektur muss
im nächsten bewusst gestarteten Full-Test bestätigt werden. Ein alter fehlgeschlagener
Run wird weder gelöscht noch nachträglich als grün dargestellt.

Primärquellen (geprüft am 30.09.2026):
- https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch
- https://docs.github.com/en/rest/actions/self-hosted-runners#list-self-hosted-runners-for-a-repository
