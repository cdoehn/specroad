# Bundle 695 — Vollständige Supervisor-Nachrichten

14. November 2026. Quelle: natives Fehler-Result mit SHA-256
`d69ad2a8dc933483f32e4730c6289bcdc66d1694868a29af13a6ce57d49659e7`,
HEAD `0d9ef4c473c7722c394fb13a96ab430b50400002`.
MOVE.R wurde in Bundle 694 nach 8.892 bestandenen Tests committed. MOVE.C
brach mit einem internen xdist-Fehler ab; kein C-Commit entstand. MOVE.W und
MOVE.R bleiben erhalten. Dies setzt den in Bundle 694 dokumentierten Rest fort.

## Ursache und begrenzte Korrektur

Der Workerabschluss meldete noch den parametrisierten Test
`test_materialization_preserves_exact_binary_attachment_bytes` aus
`tests/test_baseline_materialization.py`. Dessen bestehende Testidentität
umfasst 280.102 Zeichen. Die vollständige JSON-Reservierung benötigt rund
350 KB; der Supervisor las bisher höchstens 64 KiB pro Nachricht. Damit wird
dieser reguläre Test bereits vor seinem Körper abgewiesen. Die Beobachtung
weist eine erteilte Berechtigung ohne abgeschlossenen Versuch aus. Der
anschließende xdist-Abschluss behauptet einen leeren Rest und scheitert;
das Gate bleibt richtigerweise erfolglos. Es gab keinen Bundle-Timeout.

Der private Supervisor transportiert jetzt vollständige JSON-Objekte bis
16 MiB einschließlich abschließendem Zeilenumbruch, einheitlich auf beiden
Seiten und in beiden Richtungen. Die Grenze berücksichtigt auch angesammelte
Abschlussbelege und JSON-Escaping. Abgeschnittene, übergroße, syntaktisch
ungültige oder nicht objektförmige Nachrichten werden weiter abgewiesen.
Leseströme werden explizit geschlossen. Private Socketpfade, Eigentümerprüfung,
Authentisierung, Versuchstoken, vollständige Testidentitäten und die echte
Bestätigung beendeter Kindprozesse bleiben erhalten. Keine Testauslassung,
Namensverkürzung, automatische Wiederholung oder Abschwächung der Gateprüfung.

Die vorhandene native Supervisor-Abnahme prüft lange aktive Identitäten,
vollständige vorherige Abschlussbelege, falsche Abbruchtoken sowie gewöhnliche
und abgekoppelte Kindprozesse. Die native MOVE-Abnahme verwendet in lokalen
und Proxy-Läufen einen 280-KB-Testnamen und prüft weiter frische Fixtures,
ungültige abgebrochene Messung, vollständige Wiederholung und Gatebelege.
Die kleine Fixture wählt ihre unverändert sechs Tests über die Testdatei,
damit die lange Identität nicht die Betriebssystemgrenze eines argv-Eintrags
überschreitet. Sie bleibt vollständig im gebundenen Testprofil enthalten.
Neue Protokollabnahmen prüfen Bytegrenze, Escaping, unvollständige und kaputte
Frames. Der ursprüngliche binäre Materialisierungstest bleibt unverändert
und gehört mit seiner gesamten Datei zur ungefilterten Pflichtauswahl.

## Rest und Nachweisgrenzen

`correction_of` bindet den vorherigen Plan
`9627b8ac6f9781c1e77f37a6895a0e47bff4d6975240b10921ac3a3e74f325b7`
exakt an **MOVE.C**. ID, Rolle und Nachricht bleiben erhalten; die vollständigen
Vorherbytes schließen den erhaltenen uncommitteten C-Stand ein. Die eigentliche
C-Strukturbereinigung wird beibehalten. Kein neuer Klärungspräfix, keine Änderung
von Spezifikation, Budgets oder Produktpositionen; Produktstand bleibt 762/918.
18.s.W folgt erst nach erfolgreicher vollständiger OFF-PLAN-Abnahme.

Dev prüft ausschließlich Syntax, reine Collection, unveränderte alte Testnummern,
appendierte neue Nummern, Stage-Rekonstruktion und das native gebundene Paket.
Verhaltenstests sind in Dev nicht ausgeführt. Die bisherige vollständige
START/CONFIG/LIVE/MOVE-Pflichtauswahl, sämtliche geänderten Testdateien und die
ursprüngliche Fehlerregression bilden mit der fälligen gefilterten N=3-Gruppe
das einzelne Apply-Gate vor dem C-Commit. Keine zusätzliche Schluss-Suite und
kein vorweggenommener Erfolgsnachweis.
