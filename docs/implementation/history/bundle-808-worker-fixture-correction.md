# Bundle 808 — begrenzte Statusbeobachtung und sicheres Fixture-Ende

24. November 2026. Das native Result
`4b16060e82cb706347e041e500dbf24244d2e70bc09c2860457367eed45883a7`
belegt den erfolgreichen Commit 21.d.R
`8755fe8b6fab552974d6dca0abb38d46d3252886` nach 27.039 bestandenen Tests.
W und R sind damit bestätigt: 899/996 Positionen. Im anschließenden C-Gate
bestanden 27.071 Tests; ein Fall meldete einen Fehler und zusätzlich einen
Teardownfehler. Der einzige offene Plancommit bleibt 21.d.C.

Betroffen ist
`BlockedChainWorkerTests.test_stop_keeps_pending_intent_and_no_model_calls`.
Die Statusbeobachtung brach beim nativen `protocol_error` sofort ab, obwohl
ihre eigene Gesamtfrist noch nicht als abgelaufen ausgewiesen war. Die native
IPC-Grenze fasst unter diesem Code auch einen Antworttimeout von zwei Sekunden
zusammen. Beim Aufräumen überschritt derselbe isolierte Testprozess anschließend
die 20 Sekunden für SIGTERM; der Helfer beendete ihn daraufhin nicht garantiert.
Der Log unterdrückt die innere IPC-Ausnahme. Er belegt weder einen dauerhaften
Controller-Deadlock noch allein eine Lastursache.

Die Korrektur ist ausschließlich im gemeinsam verwendeten Testhelfer:
Lesende Statusbeobachtung darf innerhalb ihrer unveränderten festen Gesamtfrist
eine tatsächlich als TimeoutError erhaltene IPC-Ursache erneut beobachten.
Anlaufendes `not_running` bleibt wie bisher zulässig. Ungültige JSON-Antworten,
fehlende Erfolgsfelder, Sicherheits-/Scopefehler und andere Protokollfehler
werden nicht wiederholt. Ohne den geforderten Zustand endet die Beobachtung
weiter mit Fehler; weder Timer noch fachliche Assertions werden zurückgesetzt.
Schreibende IPC-Befehle einschließlich Stop werden niemals so wiederholt.

Ein ausschließlich von der Fixture gestarteter Kindprozess wird beim Cleanup
nach erfolglosem SIGTERM gezielt beendet und eingesammelt. Der ursprüngliche
Shutdown-Timeout wird anschließend erneut ausgelöst: er wird nicht zu einem
erfolgreichen Stop-Test umgedeutet. Regulär beendete Kinder werden nicht getötet.
Die bestehende echte Worker-/IPC-Abnahme prüft weiter Stop, Exit 0, keine
Modellaufrufe und erhaltene Recoveryabsicht. Alle Produkt- und Force-Oracles
sowie sämtliche Produktionsdateien bleiben bytegleich zum fehlgeschlagenen C.

Elf zusätzliche kleine Fälle prüfen verzögerten Start, einen echten Timeout
mit anschließendem geforderten Zustand, eine unverlängerte Gesamtfrist,
vier nicht wiederholbare Antwort-/Schutzfehler, einen bereits beendeten Worker
sowie normales und erzwungenes Cleanup mit erhaltenem Fehler. Ihre Uhren und
Prozessobjekte sind synthetisch; sie ersetzen keine native Workerintegration.
Der echte fehlgeschlagene Test, alle bisherigen Pflichtfälle, die vollständig
geänderten Testdateien und sämtliche statisch ermittelten Helferaufrufer werden
ungefiltert als Pflichtauswahl fortgeführt. Alte IDs/Nummern bleiben erhalten.

Das Korrekturbundle enthält genau die ursprüngliche implementation-Stage
21.d.C mit unveränderter Commitnachricht. correction_of bindet nur den Rest
des Plans `be48428aa35ff2a5b08392b70d78c239bac5b1ddfeceb4dbafc923ff4914188f`.
Vollständige Vorherbytes kommen aus dem erhaltenen C-Arbeitsstand, erfolgreiche
Commits werden nicht wiederholt. Die ursprüngliche C-Auslagerung bleibt erhalten;
ihre W/R-Fachtests sind unverändert. Keine neue Spezifikationsklärung.

Der exakte Core-Build bleibt
`a237a748eaf4fef698652f8d04f50c9168c8cb3e98e48781033d47ef27e6e2d7`.
Seine Originalmessbelege aus [Bundle 807](bundle-807-force-right-correction.md)
bleiben bytegleich und werden erneut passiv gegen denselben Build validiert.
Es gibt keine neue Messung und keine Übertragung auf einen anderen Build.
Das bisherige Ressourcen-Gate bleibt für diesen unveränderten C-Stand aktiv.
Die beauftragte Verschiebung zukünftiger Ressourcenmessungen bis zum
Entwicklungsabschluss ist eine noch offene technische Folgearbeit vor weiteren
Core-Änderungen; diese Fixturekorrektur behauptet deren Umsetzung nicht.

Dev führt keine Testkörper aus. Syntax, Collection, Quell-/Messbindung und
native Paketvalidierung sind Vorbereitungsprüfungen. 21.d.C darf erst nach
seinem eigenen N=3-plus-vollständiger-Pflichtauswahl-Gate committed werden;
der vorbereitete Zielzähler 900/996 ist vorher nicht bestätigt. 21.e,
abschließende Mess-/Review-/Releasefreigaben und menschliche Abnahmen bleiben
offen. Das Bundle startet Control nicht und ändert keine Betriebsbudgets.
