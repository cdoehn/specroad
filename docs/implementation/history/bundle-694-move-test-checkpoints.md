# Bundle 694 — Verlässliche MOVE-Testvorbereitung

Quelle: natives Fehler-Result mit SHA-256
`f73d11460f1a904a42739ad95144244c59e599622ab79f642e4c2aa107f85095`,
HEAD `aa351f477b65163471f52170dcc262d200123b38`.
Bundle 693 hat MOVE.W mit 8.811 bestandenen Tests committed. MOVE.R endete
mit 8.909 bestandenen und zwei fehlgeschlagenen Tests; R wurde nicht committed,
C nicht begonnen. Der bestätigte W-Commit wird nicht wiederholt.

## Befund und Korrektur

Fehler: `test_missing_cancel_ack_never_restarts_or_passes_gate[True]`
erwartete einen fehlerhaften Gateausgang, erhielt aber sechs bestandene Tests.
`test_completion_during_cancel_request_keeps_real_result_without_repeat`
erreichte sein Prozessende nicht innerhalb der unveränderten Wartefrist.

Beide Tests warten bisher nur auf `target.running == 0`. Der Controller
veröffentlicht diesen Wert auch zwischen zwei Testberechtigungen, während der
Zielworker noch weitere kurze Tests besitzt. Eine spätere MOVE-Anfrage kann
dann regulär wegen belegtem Ziel abgewiesen werden, bevor die injizierte
Abbruchfunktion überhaupt läuft. Der erste Test akzeptierte jede Ablehnung;
beim zweiten lag die Freigabe des Originals ausschließlich in dieser Funktion.
Die ursprünglichen Receipts stehen im Result nicht als Einzelartefakte zur
Verfügung; der konkrete frühe Ablehnungsgrund ist daher eine aus Code und
Fehlerbild abgeleitete Diagnose, kein zusätzlich beobachteter Laufbeleg.

Der gemeinsame native Testhelfer wartet jetzt auf den tatsächlichen normalen
Abschluss des ursprünglichen Zielworkers über den xdist-Controllerhook.
Dies ersetzt die flüchtige Nullanzeige in den positiven MOVE- und Abbruchfällen.
Die beiden Fehlerfalltests belegen zusätzlich, dass ihre injizierte Funktion
erreicht wurde; beim gleichzeitigen Abschluss auch das Ende genau des
ursprünglichen Versuchs. Die Erfolgs-/Fehlererwartungen, echte lokale und
Proxy-Ausführung, Gateprüfung, Phasenhistorie, Kapazitätsgrenzen, Fristen und
vorhandenen Testidentitäten bleiben erhalten. Kein Produktverhalten geändert,
keine Testwiederholung, keine Abschwächung des belegten Fehlerfalls.

## Vollständiger Rest und Prüfung

`correction_of` bindet den alten Plan
`8770a59862ab8f33d8f5625b170705bbbe133fba22e051837aa8b03d6d013c0c` exakt an MOVE.R, MOVE.C;
beide behalten ID, Rolle und Nachricht. Alle erhaltenen R-Dateien werden mit
vollständigen aktuellen Vorherbytes übernommen. Die Korrektur gilt in R und C.
Zielstand dieser Stage: **MOVE.R**; danach **MOVE.C**, jeweils erst nach
eigenem erfolgreichem Apply-Gate und Commit. C enthält weiterhin seine echte
Strukturbereinigung. Der separate Produkt-Recovery-Rückbau wird nicht vorgezogen;
der Produktstand bleibt 762/918. Keine neue Klärung oder Budgetänderung.

Dev prüft Syntax, reine Collection, unveränderte Testnummern und Testidentitäten,
vollständige Vorherbytes sowie das native Paketformat. Keine Verhaltenstests
in Dev. Beide geänderten nativen Testdateien und alle übrigen bisherigen
START/CONFIG/LIVE/MOVE-, Host-, Scheduler-, History-, Gate- und Monitorabnahmen
bleiben je Stage Pflicht; Apply ergänzt die fällige gefilterte N=3-Gruppe.
Keine zusätzliche Schluss-Suite und kein vorweggenommener Apply-Erfolg.
