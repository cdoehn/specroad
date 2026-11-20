# Bundle 771 — unabhängige aktuelle CLI-Testeingaben

20. November 2026. Das native Fehler-Result mit SHA-256
`28b57fa885844b16df5801a20854d786b5519810225038fac6e24d730c07fd97`
belegt für Bundle 770 **5 fehlgeschlagene und 8305 bestandene Tests** im
W-Gate. Kein Commit entstand; HEAD bleibt
`bac8455b09c077cfa3dc97041bdb4c479070483d`. Bestätigt bleiben 858/918.
Die IDs **19.u.W/R/C** und ihre Rollen `implementation` bleiben vollständig
offen. Die Häkchen des erhaltenen W-Zielstands sind kein Apply-Erfolg.

## Belegter Fehler und begrenzte Korrektur

Alle neun Score-Fehlerfälle bestehen nun. Die fünf Runtime-Varianten erreichen
erfolgreich die Assertions für echte Modellladung, vollständige Berichte,
Originalbindings und die jeweilige Runtime. Sie scheitern erst bei der
abschließenden CLI-Auswertung: Exitcode 3 statt 0. Die neue Testdiagnostik
meldet keinen unerwarteten Workerabbruch.

Die statische Prüfung findet die ungültige Testeingabe: Der Test kopiert
`request.context` einschließlich `subject_keys` in die separate Inputs-Datei.
Nach Spezifikation T.5.2/T.8.1 ist `--inputs.context` dagegen eine explizite
Ressourcenliste. Die native Validierung lehnt das kopierte Objekt korrekt ab.
Der Test erzeugt die aktuellen Eingaben jetzt unabhängig vom alten Request mit
`default_inputs({})`, entsprechend seiner expliziten Standardkonfiguration.
Keine Produktionsprüfung wird gelockert und kein Fehlerstatus als Erfolg
akzeptiert. Exitcode 0, aktuelle Bindung, vollständige Ausführung, fehlende
menschliche Freigabe, Projektinventar und fehlender Ausführungsmarker bleiben
verpflichtend. Bei einem unerwarteten CLI-Fehler zeigt das Assert zusätzlich
das strukturierte Ergebnis. Alle übrigen Testorakel bleiben unverändert.

Die Modelllade-Korrektur aus [Bundle 770](bundle-770-analyzer-scratch-correction.md)
bleibt unverändert erhalten, ebenso der vollständige ursprüngliche Umfang aus
[Bundle 769](bundle-769-analyzer-acceptance.md). Die Korrektur der CLI-Testdaten
ist in allen drei abhängigen Zielständen enthalten. C bleibt eine reine
Helfertrennung mit unveränderten R-Testbytes, Workerbytes und Funktions-AST.
Keine Test-ID, Parametervariante, stabile Nummer oder Abnahme entfällt.

## Übergabe und Nachweisgrenzen

Die erste Stage bindet sämtliche vollständigen Vorherbytes des erhaltenen
schmutzigen Snapshots. `correction_of` bezeichnet exakt den offenen alten
Rest; es gibt keine erfolgreichen Commits zu wiederholen. Jede Stage erhält
ein eigenes Apply-Gate aus fälliger gefilterter N=3-Gruppe und ungefilterter
Pflichtauswahl, einschließlich aller Analyzer-/CLI-Regressionsfälle und aller
fünf originalen Runtime-Matrixfälle. Erst nach dem Gate erfolgt ihr Commit.
Dev führt ausschließlich statische Prüfung, Syntax, reine Collection und
native passive Paket-/Stagerekonstruktion aus, keine Testkörper oder Fixtures.
Zielwerte 859/860/861 sind vor erfolgreichem Apply keine bestätigten Ergebnisse.

Danach bleibt **19.v.W** die nächste Position. Die vorgeschriebene lastfreie
Referenzplattform für die Ressourcenabnahme ist weiterhin nicht nachgewiesen;
es wird kein Messnachweis ersetzt oder ein Planschritt übersprungen. Die
zurückgestellten 19.t-Positionen und menschlichen Korpus-/Herkunftsreviews bleiben
offen. Spezifikation, aktive Katalogbindungen, Reviewdaten und Sicherheitsregeln
bleiben erhalten. Keine normative Lücke, kein Klärungspräfix, kein Budgetreset.
Historische Berichte 769/770 bleiben unverändert; dieser Bericht ergänzt den
tatsächlich beobachteten Ausgang von 770.
