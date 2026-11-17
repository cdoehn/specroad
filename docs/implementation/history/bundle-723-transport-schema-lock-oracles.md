# Bundle 723 — Transportschemas und gemischte Lock-Regressionen

17. November 2026. Das native Fehler-Result von Bundle 722 mit SHA-256
`79445e4d1d3d3ec0d1a4e3808c2e74fdbbdb066e95ebbcd74d8830261d002b7c`
belegt **76 fehlgeschlagene und 12.227 bestandene Tests** im Gate 18.w.R.
Es entstand kein neuer Commit. 18.w.W bleibt mit Commit
`142e5f57fb85c547147afa271200a12b28be77c3` bestätigt; Produktfortschritt
775/918. Der erhaltene Arbeitsstand entspricht exakt dem ausgebrachten R.

Beim Entfernen des veralteten Restore-Ergebnisschemas wurde versehentlich
auch der benachbarte Zweig für `ai-runtime-verify-v1` und
`ai-runtime-extract-v1` entfernt. Ihre Registrykennungen und Produzenten
blieben richtig erhalten, der Schemakatalog und die öffentlichen
Transportbefehle scheiterten aber am fehlenden Schema. Die Korrektur stellt
genau diesen weiterhin gültigen Zweig bytegleich aus dem bestätigten W
wieder her. Geschlossene Feldmengen, Original-/Runtimebindungen und
Autoritätsgrenzen bleiben erhalten; alte Recovery-/Restore-Verträge werden
nicht wieder eingeführt. Vorhandene vollständige Katalog-, Modul-/PYZ- und
Transport-Negativtests prüfen die tatsächlichen Ergebnisse.

Eine gemischte Snapshot-Regression erzeugte außerdem noch einen neuen
Recovery-Lock. Ihre stabile Identität und Varianten bleiben erhalten:
Der alte Aufruf muss ohne Schreibversuch mit `product_recovery_removed`
abgewiesen werden. Ein ausdrücklich als historisch aufgebauter Ownerrecord
unter dem echten nativen Mutex blockiert weiterhin die Erfassung vor dem
ersten Quellbyte; seine Bytes bleiben erhalten. Der verwandte echte
Kindprozess-Test prüft die unveränderte Sperre/Freigabe von Writer und
Operational sowie die dauerhafte Abweisung von Recovery vor und nach dem
Snapshotabschluss. Keine erfolgreiche Sperre oder Produktfreigabe wird
dabei simuliert.

Beide Korrekturen gelten in sämtlichen fünf offenen Stages
**18.w.R, 18.w.C, 18.x.W, 18.x.R, 18.x.C**. Kennungen, Rollen
`implementation`, ursprüngliche Commitnachrichten und Löschabsichten samt
vollständigen Vorherbytes bleiben erhalten. `correction_of` bindet den
vollständigen Rest des originalen Plans von Bundle 722. Kein erfolgreicher
Commit wird wiederholt; Spezifikation, aktive Katalogbindungen und stabile
Testnummern bleiben unverändert. Keine Klärung und kein Budgetwechsel.

Jede Stage behält die ursprüngliche Pflichtauswahl; alle fehlgeschlagenen
Testdateien, die gesamte geänderte Snapshot-Regression und ihre betroffenen
Verbraucher sind zusätzlich ungefiltert Pflicht. Echte W/R/C-Zustände werden
erst nach ihrem jeweiligen erfolgreichen Apply-Gate committed, bevor der
Folgezustand ausgebracht wird. C behält jeweils die Testbytes seines R.
Dev prüft statisch, per reiner Collection und nativer Paketvalidierung;
keine Testkörper, Fixtures oder Test-Unterprozesse und kein vorweggenommener
Apply-, Vollsuite- oder Releaseerfolg.

Commitzielstand dieser Stage: **18.w.C**, **777/918**, danach **18.x.W**.
