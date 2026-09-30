# Bundle 039: gebundene CI-Diagnose nach Beobachtungsabbruch

## Anlass und Grenze

Quelle ist `specroad_Result_105336_0930_3ce5ab.zip`, nicht ein vermuteter aktueller GitHub-Stand.
Das Result bestätigt Bundle 038 lokal mit sauberem Arbeitsbaum und Produktstand 225/885.
Der Abschlusscommit `ee64af35118fbf3b039ac06e45ac9dd6975e20df` wurde nach `origin/dev` gepusht.
Im eingebetteten CI-Nachweis ist Run `36718142755`, Attempt `1`, exakt daran gebunden.
Der Matrixjob `109896248057` (`CPython 3.12 / parallel`) scheiterte im Schritt
`Full parallel regression`; andere Matrixjobs waren noch nicht abgeschlossen.
Danach brach die Beobachtung mit `gh_api_exit_1` ab. Logs und Testreport-Artefakte
fehlen im Result. Der konkrete fehlgeschlagene Test und die Ursache des API-Fehlers
sind damit **nicht festgestellt**. Ein 404 beim Abruf über den Chat-Connector
liefert keine zusätzliche Fehlerursache des Tests.

Bundle 039 ist ein einzelner OFF-PLAN-Infrastruktur-/Diagnosecommit
`ci: gebundene CI-Evidence nach Beobachtungsabbruch sichern`.
Die Produktimplementierung, die Spezifikation und der Zähler 225/885 bleiben
unverändert; `5.p.W` bleibt der nächste Produktcommit. Nur die abgeschlossene
Bundle-Nummer steigt nach erfolgreichem lokalen Gate/Commit auf 039.
Ein erfolgreicher Diagnosepatch ist keine Erklärung oder Reparatur des unbekannten
CI-Testfehlers. Vor weiterer Produktentwicklung sind die nachgeholten Nachweise auszuwerten.

## Verhalten des vorhandenen Beobachters

`tools/watch_bundle_ci.py` und `tools/ci_support/` bleiben der einzige CI-Beobachter.
Normale Beobachtung bindet nach der SHA-genauen Suche Run-ID und Attempt. Ein
späterer Attempt-Wechsel wird weiterhin als unzuverlässige Beobachtung abgelehnt.
Die neue explizite historische Abfrage verwendet dagegen durchgehend
`actions/runs/{run_id}/attempts/{attempt}` und die daran gebundenen Jobs, Logs und
Artefaktnamen. Sie liest nur; kein Rerun, Cancel, Workflow-Dispatch oder Git-Schreibzugriff.

Jeder geprüfte Run-Snapshot wird schon vor dem folgenden Jobabruf gesichert. Bei
Transportabbruch nach bestätigter Bindung versucht der Beobachter, vollständige
Attempt-Logs und verfügbare Reports zu erhalten. Fehlt das vollständige Logarchiv,
werden Logs bereits bestätigter abgeschlossener Job-IDs einzeln versucht. Noch
laufende oder ungeprüfte Jobs werden dafür nicht erfunden. Ein Bindungsfehler
berechtigt nicht zu dieser Ersatzsicherung. Drei GET-Versuche bleiben die Grenze
pro Abruf; ein Testfehler wird nicht als wiederholbarer API-Fehler behandelt.

Fehlgeschlagene Report-ZIPs werden vor der bestehenden Pass-Prüfung bytegetreu
aufbewahrt. Sie gelten nicht als bestandene Tests. `capture_complete` beschreibt
nur die vorhandenen Roharchive (gesamtes Logarchiv plus fünf Matrixreport-ZIPs),
nicht ihren Erfolg. Die strengere bisherige `evidence_complete`-/
`test_evidence_verified`-Prüfung wird nicht gelockert. Eine abgebrochene Beobachtung
kann weiterhin kein finales CI-SUCCESS nachweisen. Verifizierte Run-/Jobdaten,
beobachtete Fehler, Aufnahmezeitpunkte, erwartete Python-Matrix, Modus und SHA-256
aller enthaltenen Dateien stehen im JSON-Nachweis. Testzahlen und Vergleiche werden
nur aus überprüfbaren Reports abgeleitet, niemals bei fehlenden Reports geschätzt.

Transportfehler speichern einen erkannten numerischen HTTP-Status und Exitcode,
aber keine rohen `gh`-Diagnosen, Tokens, Header oder Zugangsdaten. Das ändert keine
Authentifizierung oder Berechtigung. Größenlimits und nicht ausführende Behandlung
externer Archive bleiben bestehen; unvollständige Übertragung wird kenntlich gemacht.

## Automatischer Ablauf beim Apply

Nach dem einen lokalen Commit wird dessen volle SHA normal nach `origin/dev`
gepusht. Die bestehende Hetzner-Auswahl mit explizitem Ubuntu-24.04-Fallback bleibt
unverändert. Bundle 039 verlangt die komplette parallele Suite auf CPython
3.10–3.14; Bundle 040 verlangt wieder parallel plus seriell plus Vergleich.

Zuerst beobachtet das Werkzeug den neuen Abschlusscommit. Anschließend liest es
mit `--recover-prior` genau den historischen Attempt aus Bundle 038 nach. Das
JSON hierfür stammt aus der Result-Bindung, nicht aus den neuen Quellen:

```json
{
  "repository": "cdoehn/specroad",
  "branch": "dev",
  "workflow_path": ".github/workflows/behavior.yml",
  "commit_sha": "ee64af35118fbf3b039ac06e45ac9dd6975e20df",
  "bundle_number": 38,
  "run_id": 36718142755,
  "run_attempt": 1,
  "source_sha256": "6c2b1012d634c879d7a5feea4841f26728e8559b9465413bcc58c13233d12b02"
}
```

Der Source-Hash wurde mit der vorhandenen Source-Identity-Funktion über den
vollständig gegen das Manifest geprüften Base-Snapshot bestimmt. Er ist bewusst
nicht der Source-Hash von Bundle 039. Alle acht JSON-Felder sind vorgeschrieben;
fremde Repositorys, Halbbindungen und unbekannte Felder werden abgelehnt.
Bei fehlgeschlagenem Push wird kein neuer Lauf gesucht, der alte Attempt kann
weiterhin nachgelesen werden. Nach einem Benutzerabbruch startet keine zweite
Beobachtung. Netzwerk-/CI-Fehler ändern oder verwerfen keine lokalen Commits.

## Result-Transport und getrennte Aussagen

Der bestehende `SPECRoad-CI-EVIDENCE-V1`-Transport erhält weiterhin genau **einen**
prüfsummengesicherten Frame-Verbund. Das aktuelle Evidence-Archiv enthält die
alten Nachweise als `prior-ci-evidence.zip` mit eigenem `summary.json` und eigenen
Dateihashes. Das äußere `summary.json` enthält `prior_ci`, ohne den aktuellen
CI-Status durch den alten zu ersetzen. Auch das verschachtelte ZIP besitzt einen
SHA-256 im äußeren Dateiinventar. Kein zweiter konkurrierender Frame wird ausgegeben.

Der Entrypoint weist LOCAL APPLY, aktuelle CI und historische CI getrennt aus.
Ein unbekannter oder alter roter Status wird nie auf grün umgeschrieben. Fehlende
Berechtigungen, verschwundene Artefakte und Größenlimits bleiben als unvollständige
Evidence erkennbar. `capture_limit` erhält den beobachteten CI-Ausgang, aber entfernt
positive Übertragungsbehauptungen für nicht mitgelieferte Dateien.

## Gezieltes lokales Gate

Nur diese neuen bzw. unmittelbar durch Beobachter/Transport betroffenen Testdateien
werden auf dem Pixel ausgeführt, mit vier pytest-xdist-Workern:

- `tests/test_ci_observation_recovery.py` (44 neue Verhaltens-/Datenvertragstests)
- `tests/test_ci_wait.py`
- `tests/test_ci_wait_right.py`
- `tests/test_ci_evidence_retry.py`

Erwartete Gesamtauswahl: 120 Tests. Die vorgelagerte Katalogprüfung sammelt nur
Tests ein und führt keine Testkörper aus. Kein lokaler Vollsuitevergleich, kein
Dokumentations-, Konsolentext- oder Layouttest. Ergänzende serielle Vorabtests in
der Chat-Arbeitsumgebung sind weder Pixel-Apply noch GitHub-CI-Nachweis.
