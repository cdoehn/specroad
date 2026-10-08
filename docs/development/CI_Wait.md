# Aktive Teststrategie ab 7. Oktober 2026

In `specroad-codex` läuft die vollständige Testsuite ausschließlich parallel.
In `specroad-apply` führt `tools/run_apply_tests.py` den parallelen Volltest aus.
Auch beim letzten Bundle-Zustand läuft ausschließlich der parallele Volltest.
`--final-bundle-state` bleibt kompatibel und startet denselben einzelnen Lauf.
Nur dessen Erfolg erlaubt den W/R/C-Commit.
Die technischen Aufrufe stehen in [Testing.md](Testing.md). Die zentrale lokale
Arbeitsanweisung ist `AGENTS.md`.

GitHub-CI startet niemals automatisch. Full Regression wird ausschließlich
vom Nutzer manuell per `workflow_dispatch` gestartet und führt die vollständige
Testsuite parallel auf Python 3.10–3.14 aus. Codex startet keine CI-Workflows.
In GitHub gibt es keinen seriellen Volltest.
Die frühere 5er-Bundle-Regel bleibt entfernt.

## Exakte, rein lesende Beobachtung

`tools/watch_bundle_ci.py` startet oder wiederholt keine CI und verändert weder
Commits noch Branches. Es kann nach einem ausdrücklich manuellen Start zusätzlich
aufgerufen werden. Der Default ist `event=workflow_dispatch`, `mode=parallel`.
`--bundle` ist optionale Metadaten, kein Modusschalter. Der Workflow-Dateiname
bleibt `behavior.yml`, damit bestehende Registrierung und historische Links gelten.

Für einen Full-Run des gegenwärtig ausgecheckten unveränderten Commits:

```sh
python3 -I -B tools/watch_bundle_ci.py \
  --commit FULL_TEST_COMMIT_SHA \
  --run-id EXACT_RUN_ID --attempt EXACT_ATTEMPT \
  --output-dir /tmp/specroad-ci-UNIQUE
```

Die Großbuchstaben sind zu ersetzende Werte, keine ausführbaren Beispiel-SHAs.
Das frische Ausgabeziel darf noch nicht existieren. Tests werden nicht gestartet.
Bei unterschiedlichen Test- und Workflowrevisionen zusätzlich die vollständige
`--workflow-commit`-SHA angeben. Der Observer bindet den Run an die Dispatch-SHA,
den Report dagegen an die tatsächlich getestete SHA. `run-context.json` bestätigt
beide Revisionen, Ereignis, Branch, Repository, Run-ID, Attempt, Python und Ausführungsmodus.
Ein grüner Run ohne diese Bindung darf keinen erfolgreichen manuellen Full-Nachweis
für eine andere ausgewählte SHA liefern.

Ohne `--source-sha256` muss HEAD exakt der Test-SHA entsprechen; nur dann wird
`source_identity` des aktuellen Baums verwendet. Für ältere Testrevisionen den
bereits verifizierten Quellhash aus dem zugehörigen Result ausdrücklich übergeben.
Bei mehreren passenden manuellen Runs ist eine Run-ID-/Attempt-Bindung nötig;
der Observer nimmt nicht willkürlich den neuesten grünen Run. Halb angegebene
Pins, wechselnde Attempts, andere Repositories/Branches und fremde Artefakte
werden zurückgewiesen.

Ein selbständig gestarteter Observer kennt keinen Pixel-Apply. Er meldet
`local_apply: not_observed`, nicht fälschlich LOCAL APPLY SUCCESS. Sein Exitcode 0
bedeutet abgeschlossene Beobachtung; `ci_status` und Evidence-Felder enthalten
das tatsächliche Ergebnis. CI- oder Netzwerkfehler lösen niemals Rollbacks aus.

## Alte Push-Läufe rein lesend nachholen

Historische Push-Nachweise bleiben lesbar, aber nur mit ausdrücklich aus dem
alten Result übernommenem `--event push --mode parallel|both` und dessen Bundle,
SHA und Quellenhash. Der Modus wird **nicht mehr aus der Bundle-Nummer berechnet**.
`--recover-prior` akzeptiert genau diese Felder:

```json
{
  "repository": "cdoehn/specroad",
  "branch": "dev",
  "workflow_path": ".github/workflows/behavior.yml",
  "commit_sha": "FULL_TEST_COMMIT_SHA",
  "bundle_number": 40,
  "source_sha256": "FULL_SOURCE_SHA256",
  "run_id": 36742807853,
  "run_attempt": 1,
  "trigger_event": "push",
  "expected_mode": "both",
  "workflow_commit_sha": "FULL_TEST_COMMIT_SHA"
}
```

Dieses Schema ist eine Vorlage, keine gebundene Diagnose; die Platzhalter müssen
mit Werten des betreffenden Result ersetzt werden. Historische Archive werden
nicht umgeschrieben. Ohne konkrete Beauftragung findet auch diese Nachholung
nicht im normalen Bundle statt.

## Evidence und Result-Transport

Gesichert werden run.json, jobs.json, vollständige verfügbare Attempt-Logs,
Artefaktindex, paralleler Report pro Version (bei historischen dualen Läufen beide Reports/Comparison) sowie Größen und SHA-256 aller
gesicherten Dateien. Fehlgeschlagene Reports bleiben erhalten, auch wenn sie den
strengen Passing-Vergleich nicht bestehen. Capture-Vollständigkeit, bestätigter
Testnachweis und tatsächliche GitHub-Conclusion sind getrennte Felder.
Bei Transportfehlern werden bereits bestätigte abgeschlossene Joblogs nach Möglichkeit
gesichert; fehlende Dateien werden nicht erfunden. GitHub-Artefakte werden nicht als
unvertrauenswürdige Pfade ins Repository extrahiert.

Der vorhandene `SPECRoad-CI-EVIDENCE-V1`-Transport kann das komprimierte, geprüfte
Archiv in erfasstem stdout transportieren. Wird ein expliziter Observer innerhalb
einer PatchHarbor-Ausführung aufgerufen, kann deren Result es im execution.log
enthalten. **Ein normaler Bundle-041-Apply ruft keinen Observer auf und sammelt
keine manuelle CI automatisch ein.** Eine separat aufgerufene Beobachtung speichert
ci-evidence.zip und ci-summary.json im angegebenen frischen Verzeichnis; diese
Dateien müssen zur weiteren Analyse gesondert bereitgestellt werden.
Kein rekursives `patchharbor bundle`, keine Änderung einer erzeugten Result-ZIP.

Historie: Die CI-WAIT.a.W/R/C-Implementierung ab Bundle 019 begründete die exakte
Bindung und den Archivtransport. Deren automatische Aufrufe und Fünferregel sind
seit Bundle 041 abgelöst; die ursprünglichen Fehler-/Testnachweise bleiben gültige
historische Aussagen, keine aktuellen automatischen Ausführungsanweisungen.
