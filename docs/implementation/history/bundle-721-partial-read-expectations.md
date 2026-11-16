# Bundle 721 — veraltete Recovery-CLI-Erwartungen korrigieren

16. November 2026. Das native Fehler-Result mit SHA-256
`006ef3e98444fd5da8eadbf91561f818e9c2706b3793f41567b969b54e70d531`
belegt **11.802 bestandene Tests, zwei Fehler und keinen Commit** im ersten
Gate von Bundle 720. Der bestätigte Produktstand bleibt vor der Korrektur
774/918, zuletzt 18.v.C. Der vollständig offene Rest lautet
18.w.W, 18.w.R, 18.w.C, 18.x.W, 18.x.R, 18.x.C; alle Rollen bleiben
`implementation`, die ursprünglichen Commitnachrichten bleiben erhalten.

Beide Fehler liegen in der gemischten Regression
`tests/test_partial_read_consumers.py`. Sie erwartete noch einen verfügbaren
öffentlichen Befehl `recover status`, obwohl RECOVERY-REMOVAL-006 und 18.w.W
ihn entfernen. Die vorhandenen parametrisierten Testidentitäten bleiben
erhalten: Der alte Recovery-Aufruf muss mit Usage-Fehler 2, ohne Ergebnis,
ohne Schreibversuch und bei bytegleichem Projektinventar abgewiesen werden.
Die zweite Prüfung beweist außerdem, dass der ehemalige Backendadapter
nicht aufgerufen wird. Für `lock status` bleibt die Abweisung einer während
des Lesens geänderten Projektidentität mit Fehler 6 verbindlich; die erreichte
Fehlerinjektion wird nun ausdrücklich geprüft. Die Environment-Diagnose und
sämtliche übrigen gemischten Sicherheitsprüfungen bleiben erhalten.

Die Korrektur gilt bytegleich in allen sechs Stages. Ihre ursprüngliche
Pflichtauswahl sowie die vollständige gemischte Testdatei bleiben Pflicht.
Produktcode, Spezifikation, aktive Katalogbindungen und stabile Testnummern
werden durch diese Korrektur nicht geändert. Alle ursprünglichen Löschziele
und vollständigen Vorherbytes bleiben gebunden, auch bereits im Fehlerstand
fehlende Dateien. Keine neue Klärung, kein Budgetwechsel, keine Wiederholung
erfolgreicher Commits und keine zusätzliche Produktposition.

Jede Stage wird erst nach ihrem eigenen Apply-Gate committed. Die folgenden
Zielangaben gelten ausschließlich für diese einzelne Stage nach erfolgreichem
Gate; spätere Stages bleiben bis zu ihrem eigenen Gate offen. Dev führt nur
statische Prüfungen, reine Collection und native Paketvalidierung aus, keine
Testkörper oder Fixtures. Eine vollständige Verhaltens- oder Releaseabnahme
wird damit nicht behauptet.

Commitzielstand dieser Stage: **18.w.W**, **775/918**, danach **18.w.R**.
