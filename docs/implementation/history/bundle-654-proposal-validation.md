# Bundle 654 — Öffentliche Proposal-Strukturvalidierung

9. November 2026. Quelle ist das vollständig geprüfte erfolgreiche Result
`4f00fbe298f1797c482cf12468c2d00c02cd855062218c028370133f323658ea`, Base-Commit `051fac80a82dfa2f577591e9920614c42a7c4ad0`.
Bundle 653 schloss 18.e.W/R/C mit 8.627, 8.491 und 8.488 bestandenen ausgewählten
Tests sauber ab. Es verbleiben keine offenen Stages dieses Bundles. Bestätigt
sind 744/900 Positionen; diese Commits werden nicht wiederholt.

Die vorhandenen Abschnitte 10.3 und 11.10 sowie SR-REQ-0164/0165/0645 bestimmen
die rein lesende Strukturvalidierung bereits. Keine neue Detailklärung und keine
Änderung von Spezifikation, Projektbefugnis oder Klärungsbudget. 18.f.W/R/C setzt
den vollständigen öffentlichen Befehl `proposal validate <PROP>` um.

## Umsetzung und Abnahme

W registriert den echten read_only-Befehl für argv und strukturierte Requests.
Er liest eine Proposal-ID, ihren verwalteten Pfad oder eine ausdrücklich externe
Prüfdatei. Native ProposalOriginal-, ProposalContext- und Target-Rekonstruktion
prüfen Schema, Inhaltshash, Plan-/Erläuterungskorrespondenz, Referenzen, deklarierte
geschlossene specification-Basis, geordnete Operationen und erwarteten Zielroot.
Es entsteht kein Kontrollwrite und keine persistierte validated-Revision.

Das maschinenlesbare Ergebnis bindet Originalbytes und nativen Quellkontext
mit vollständigen SHA-256 sowie das Ergebnis selbst über die vorhandene JCS-
Hashfunktion. Es nennt observed_status und eligible_transition; letzteres kann
bei einem gültigen draft validated sein und ist sonst null. Die Beobachtung
verleiht weder Review- noch Schreibrechte. Der eigene Result-Schemaeintrag und
das veröffentlichte CommandRequest-Beispiel sind an reale native Daten gebunden.
Ein kleines vollständiges Projekt ist Standard; ein vollständiger gebündelter
Sprachregisterfall bleibt als Integrationsreferenz enthalten.

R erhält den tatsächlich lesbaren Status auch im fehlgeschlagenen Result, ohne
fehlende oder fehlerhafte Angaben zu erfinden. Ein Fehler meldet keinen zulässigen
Übergang. Ungültige JSON-/Inhaltshash-/Basis-/Zielbindungen, fremde IDs, verwaltete
Aliasdateien, Symlinks, Steuerzeichen und unzulässige Writer-/Variantenoptionen
werden abgewiesen. Vor und nach gültigen und ungültigen Prüfungen vergleichen die
Tests das vollständige Projektinventar; Schreib-/Prozess-/Netzwerkversuche werden
zusätzlich abgefangen. Native Quellen und externe Originalbytes werden am Ende
erneut gelesen. Konkurrierende Änderungen bleiben erhalten und ergeben Fehler,
auch wenn die fachliche Prüfung selbst schon fehlgeschlagen ist. Es wird keine
atomare Momentaufnahme gegenüber unkooperierenden externen Schreibern behauptet.

C trennt Eingabe-/Currentness-Grenze, native Strukturprüfung und passive
Ergebnisprojektion in eigene Module. Keine neuen Fachresultate, Fehlerklassen
oder Seiteneffekte; die W-/R-Testbytes bleiben exakt erhalten. Die vorhandenen
Revisions-, Review- und Writerpfade werden nicht von der Validierung aufgerufen.

18.f liefert ausschließlich Struktur und Anwendbarkeit. Der vollständige
isolierte Validator-/Query-/Render-/Diff-/Impact-Check gehört weiterhin zu 18.g,
Review-/Apply-Schreibbefehle und der öffentliche Gesamtablauf zu den folgenden
Positionen. SR-REQ-0645 und die Gesamtbefehlsgruppe bleiben deshalb partial.
Die eng begrenzten SR-REQ-0164/0165 sind im vollständigen R/C-Zustand implementiert;
das ist kein bestandener Apply- oder Release-Nachweis.

## Übergabe

Vorbereiteter W-Zustand: Die Fortschrittswerte gelten erst nach dem
erfolgreichen eigenen Apply-Gate und Commit. R und C bleiben bis zu ihren eigenen Gates offen.

Dev hat keine Verhaltenstests ausgeführt. Syntax, reine Collection und native
Paketprüfung sind keine Verhaltensabnahme. Jeder echte Zustand erhält vor seinem
Commit die gefilterte fällige N=3-Gruppe plus ungefilterte Pflichtunion. Neue und
geänderte Testdateien sowie Proposal-/Restore-, ChangePlan-/Fold-, lesende
Quellgrenzen-, CLI-/Request-/Schema-/Katalog- und relevante Helferregressionen
sind Pflicht. Bestehende Testnummern und historische Belege bleiben unverändert;
neue Nummern werden angehängt. Nach atomarer Übergabe endet dieser Auftrag.
