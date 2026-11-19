# Bundle 760 — aktive Funktionsbindung der Schreibschutzregressionen

19. November 2026. Maßgebliches natives Fehler-Result SHA-256:
`48913774ea2de473da811bc0e948ab5035268ff266bf8070653d4c0ce93938de`.
HEAD blieb `3975512044566bb7e8b2c830e044e83a2a63b7a0`.
Der vollständige erhaltene Arbeitsstand entspricht 19.l.W aus Bundle 759.
Sein öffentlicher Plan ist an SHA-256
`cfbc4509b00fe7162d433d219a1fa935c0783e0c773c0a55d4da8915f1c82377` gebunden.
Das Result protokolliert **22083 bestandene und vier fehlgeschlagene Tests**
in 19.l.W. Kein neuer Commit entstand. Bestätigt bleiben **834/918**;
der vollständige Rest 19.l.W/R/C bleibt offen.

## Belegter Fehler und Korrektur

Alle vier Fehler betreffen die Varianten `False-open0`, `False-open1`,
`True-open0` und `True-open1` von
`test_allowed_process_flag_still_rejects_file_paths_and_regular_descriptors`.
Die erwartete Schreibschutz-Ausnahme blieb aus. Die Parametrisierung hatte
`builtins.open` und `io.open` bereits während der Collection als Callable
gespeichert. Diese ursprünglichen Funktionen wurden später direkt aufgerufen
und umgingen die erst im Testkontext installierten Wrapper.

Die Testdaten benennen jetzt nur das jeweilige Modul. Erst innerhalb von
`no_write_attempts` wird dessen aktuell gebundene Open-Funktion ausgewählt.
Explizite Parameter-IDs erhalten exakt die vier bisherigen Testidentitäten.
Die regulären Dateideskriptoren und Pfade, beide Open-Funktionen, der
Schreibversuch, das Abfangen der unmittelbaren Assertion, die erwartete
nachgelagerte Assertion, die Versuchszahl und die unveränderte Dateiinventur
bleiben erhalten. Keine Assertion, Variante oder Negativabnahme entfällt.

Der Schreibschutzhelfer selbst bleibt bytegleich zu Bundle 759. Seine
begrenzte Pipe-Ausnahme wird nicht erweitert. Produktcode, Hostprofilcodec,
Runner, Sicherheits- und Fehlerverträge bleiben ebenfalls unverändert.
Dies korrigiert fehlerhafte Testvorbereitung und ist keine normative
Spezifikationsklärung. Spezifikation, Entwicklungsvertrag, Budgets,
Freigaben und historische Originalbelege bleiben erhalten.

## Vollständige Fortsetzung

**19.l.W, 19.l.R und 19.l.C** behalten die ursprünglichen IDs, Rollen
`implementation`, Commitnachrichten, vollständigen Fachumfänge und eigenen
Apply-Gates. Die Testkorrektur gilt schon in W und bleibt in R/C bytegleich.
`correction_of` bindet genau den offenen Dreierrest des Plans aus Bundle 759.
Erfolgreiches 19.k wird nicht wiederholt. W erreicht den echten bekannten
Worker, R erhält die Umgebungs- und Antwortgrenzen, C führt ausschließlich
die ursprüngliche Strukturierung fort. Danach bleibt **19.m.W** offen.

Alle bisher verpflichtenden Testdateien, sämtliche 16 Schreibschutzfälle
und die ursprünglichen Analyzer-Integrationen bleiben vollständig in jedem
Gate. Testnummern und Collection-Identitäten werden nicht geändert. Ein
statischer Vergleich erhält alle Assertions und sonstigen Testfunktionen;
C erhält alle R-Testbytes und die verschobenen Funktions-ASTs.

Dev führt nur Syntax, statische Analyse, reine Collection und native
Paket-/Übergabevalidierung aus: keine Testkörper, Fixtures oder
Test-Unterprozesse. Vorbereitete Zielwerte sind noch keine Apply-Abnahme.
Die offenen Plattform-, Klassifikations- und Releasebelege aus Bundle 757
bleiben offen. [Bundle 759](bundle-759-worker-pipe-write-guard.md) beschreibt
die unveränderte Helferkorrektur; sein fehlgeschlagener Versuch wird durch
dieses Result eingeordnet, nicht nachträglich als erfolgreich ausgegeben.

Stageziel `19.l.R`: 836/918, erst nach eigenem Gate.
