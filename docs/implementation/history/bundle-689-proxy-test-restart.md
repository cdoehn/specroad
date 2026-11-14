# Bundle 689 — Transportwechsel in der isolierten Testvorbereitung

Maßgeblich ist das native Fehler-Result vom 14. November 2026 mit SHA-256
`76a22ca5f552ada9fc330f51b955647b80203786ccdd1115b58c68ef19ccf309` und HEAD
`bbc9bca1b0c21fd42e6f6fcd3a132456c4e4252d`. Bundle 688 hat keinen neuen Commit erzeugt;
der vollständige Rest bleibt CONFIG.W, CONFIG.R, CONFIG.C, jeweils implementation.
Die früher erfolgreichen START.R/C-Commits bleiben erhalten und werden nicht
wiederholt. Der erhaltene CONFIG.W-Arbeitsbaum ist die neue Korrekturbasis.

## Befund und Korrektur

Das CONFIG.W-Gate meldet 8243 bestandene und einen fehlgeschlagenen Test.
Von den 242 zuvor fehlgeschlagenen Tests bestehen jetzt 241; der verbliebene
Test erreicht nun eine weitere, bisher verdeckte Schutzprüfung.
Der verbliebene Proxy-Nachweistest änderte Datei und Config-Attribut einer
bereits aufgebauten Engine von exec auf app-server-proxy. Die neue Prüfung
weist einen solchen Transportwechsel ohne kontrollierten Neustart korrekt mit
runtime_configuration_changed zurück, bevor der eigentliche Nachweistest beginnt.

Die Testvorbereitung prüft jetzt zuerst diese Ablehnung samt unveränderter
Engine, unveränderten Ledgerbytes und ausbleibendem Modellaufruf. Anschließend
schließt sie die isolierte Engine, lädt die geänderte private Konfiguration
und erzeugt eine neue Engine mit denselben Transport-Doubles und demselben
Ledger. Der bestehende Test prüft danach unverändert sowohl manipulierte
Turnidentität als auch manipulierten Prompt-Hash und die gültige Übernahme.
Test-ID und Nummer bleiben erhalten; keine Produktionssperre wird gelockert,
kein interner Policy-Cache im Test manipuliert und kein echter Dienst gestartet.

Die Korrektur gilt in allen drei offenen Stages. CONFIG.R führt weiterhin die
angekündigten konkurrierenden Zugriffe, atomare Speicherung, laufende Aufträge
und erschöpfte Budgets aus; CONFIG.C bereinigt ausschließlich die Struktur.
correction_of bindet den exakten alten Rest an Plan-SHA-256
`cd348dc25fc8374011cb326c363c0c9a093beddf3cd98fd91e43c98e81ec3660`.

Stage-Zielstand: **CONFIG.C**; danach **LIVE.W**. Diese Fortschreibung gilt
erst nach erfolgreichem eigenem Apply-Gate und Commit. Keine neue Klärung,
kein Budgetreset, kein wiederholter Erfolgscommit. Produktstand bleibt 762/918;
LIVE/MOVE bleiben die vollständigen nächsten geplanten Gruppen.

## Prüfung

Dev: Syntax, vollständige reine Collection, stabile Nummern, Katalogbindung,
native Vorherbytes/Resultbindung und Paketvalidierung. Keine Testkörper oder
Fixtures ausgeführt. Apply muss je Stage die fällige gefilterte N=3-Gruppe
und alle Control-Tests sowie relevante Commitplan-/Registrierungsregressionen
ausführen. Der frühere Proxy-Fehler und die 242 zuvor reparierten Fälle bleiben
in jeder Stage Pflicht; kein Verhaltenserfolg dieser Korrektur ist vorweggenommen.
