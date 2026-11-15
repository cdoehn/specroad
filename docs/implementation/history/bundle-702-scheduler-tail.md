# Bundle 702 — ungestartete Scheduler-Folgetests

Datum: 15. November 2026. Ausdrücklich beauftragte Übernahme der privaten
SCHEDULER-TAIL-Reparatur nach erfolgreichem Bundle 701. Nativ geprüfte Quelle:
`specroad-apply_Result_085003_1115_5aeeed.zip`, SHA-256
`f850165ad145ba0fb12fad142a4aad19730af07d3bdd3477a37abfab7fb792bd`.
18.s.C wurde mit 10996 bestandenen Tests als
`a3c19498894a3389b98b968dd6b615799d183e59` committed; der Result-Snapshot ist
sauber und stimmt vollständig mit der privaten Vorherbasis überein. Es gibt
keinen offenen Rest und keine Wiederholung erfolgreicher W/R/C-Commits.

## Belegte Blockade und Korrektur

Ein noch ungestarteter pytest-nextitem-Folgetest kann hinter einem langen
laufenden Original reserviert bleiben. Der globale Vorrat ist dann leer;
freie Worker enden, während die korrekte Kopiensperre weiterhin auf den
Folgetest wartet. Die Kopienregel in Spezifikation 2.4.3.8 ist eindeutig und
braucht keine neue Klärung.

Bei freier aktivierter Kapazität entzieht der Controller dem bisherigen
Worker zuerst die Startberechtigung für seinen ungestarteten Folgetest und
stellt diesen atomar wieder in den globalen Vorrat. Der laufende Vorgänger
bleibt erhalten. Sein Worker läuft anschließend aus und erhält für den
entzogenen Folgetest eine reguläre Ablehnung, auch wenn der neue Worker noch
collectet. Der bisherige Prozess zählt bis zum Ende gegen seine Hostbelegung.
So wird der Folgetest nicht erneut hinter demselben belegten Slot festgehalten.

Nur Profilformat 4 verwendet diese Reparatur. Der Vorrang ungestarteter
Originale, Kopienwahl ohne Geschwindigkeitsannahme, separate Versuchskonten,
vollständiger Gewinnerabschluss und bestätigte Prozessbaumbeendigung bleiben.
Pause, fehlende Kapazität, laufende MOVE-Übergabe und Abbruch verhindern eine
neue Übergabe. Fehler werden nicht wiederholt oder als Erfolg umgedeutet.
Die [Bedienbeschreibung](../../development/Test_Control.md#freie-worker-am-laufende-parallele-kopien)
erläutert den erhaltenen Vertrag.

## Eigener Korrekturschritt und Nachweisgrenze

Ein Commit `SCHEDULER-TAIL-FIX`, Rolle `correction`, sichtbare Art OFF-PLAN.
Die Produktposition bleibt 765/918, nächste Position 18.t.W. Die Bundlezählung
702 ist ein erst mit erfolgreichem eigenem Apply-Gate gültiger Zielwert.
Keine Änderung an Spezifikation, Requirements, Laufzeitfilter, Rotationsanker,
Hostkonfiguration, Budgets oder installierter Automatik.

Die sieben privat vorbereiteten Änderungsdateien werden bytegleich übernommen.
25 neue Fälle prüfen Controller-Berechtigungen und Grenzen sowie echte lokale
und Proxy-Prozesse: neu zugeteilter Folgetest, erster Kopiengewinner,
normal endender Vorgänger, Modul-/Session-Finalisierung, echter Teardownfehler
und Prozessverlust. Die bestehende native Kopienabnahme bleibt vollständig;
sie verlangt nun Weiterverteilung statt der bisherigen Blockade. Bestehende
Testidentitäten und Nummern bleiben erhalten; neue Nummern werden angehängt.

Das Apply-Gate erhält die vollständige Pflichtauswahl für Kopien, Live/MOVE,
Remote-/Hoststeuerung, Laufzeitschreiber und deren Prozessnachweise, ergänzt
um relevante Hostprofil-/Supervisorregressionen und die fällige N=3-Gruppe.
Dev hat nur Syntax, vollständige Collection, Registry, Patch-Replay und native
Paketbindung geprüft. Kein Testkörper und kein Test-Unterprozess lief in Dev.
Verhalten und Commit sind bis zum neuen Apply-Result ausdrücklich unbestätigt.
Der bestehende Watcher übernimmt die ZIP; Control bleibt gestoppt.
