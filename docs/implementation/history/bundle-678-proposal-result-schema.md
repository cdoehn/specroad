# Bundle 678 — Ergebnisschema von Proposal Apply registrieren

13. November 2026. Quelle ist das native Fehler-Result 677 mit SHA-256
`dbbe934a3ec271b224cce805b3564b4b1427cdb69586efb32056d104747e19ce`.
Der Lauf meldet 13939 bestandene und 13 fehlgeschlagene Tests bei 5916,90
Sekunden pytest-Laufzeit. Es gab keinen Produktcommit: HEAD bleibt der bereits
erfolgreiche Klärungscommit `8af77c07279e1784a11de2809834723296940dc7`.
18.k.W ist offen, R/C wurden nicht ausgebracht. Die W-Checkliste des erhaltenen
Fehlerstands bezeichnet den vorbereiteten Zielzustand, keinen bestätigten Erfolg.

## Ursache und Korrektur

Die bisherige Profilbarriere ist beseitigt. Die nativen Apply-Pfade erreichen
nun die Ergebnisprüfung; dort weist result_json_schema das bereits implementierte
proposal-apply-v1 mit „Unknown local result schema“ ab. Der öffentliche
Commandvertrag und der konkrete geschlossene Schemaanbieter sind vorhanden,
aber der Eintrag in der gemeinsamen RESULT_IDS-Registrierung fehlt. Dieselbe
Auslassung verhindert den Eintrag im öffentlichen Schema-Katalog und erzeugt
interne Fehler in CLI-, Request- und Beispielintegrationen. Bei echten
Publikationstests liegt diese Ausnahme nach dem nativen Write; daraus darf
kein allgemeiner Rückschluss auf schreibfreie Fehler oder eine sichere
ungebundene Wiederholung gezogen werden.

Die Korrektur ergänzt genau die vorhandene Schema-ID in der zentralen
Distributionstabelle. Native Ergebnisvalidierung, Providerindex und
Identitätsmetadaten verwenden dadurch den bereits vorhandenen Vertrag aus
Spezifikation 10.3.6. Es werden weder Schemaprüfungen umgangen noch unbekannte
IDs pauschal zugelassen. Der geschlossene Ergebnisvertrag, Freigabegrenzen,
Writer, Replay-/Recoverypfade und menschliche Reviewpflichten bleiben unverändert.
Keine neue fachliche Klärung, Spezifikationsänderung oder Budgetänderung.

## Abdeckung und vollständige Folge

Zwei kleine zusätzliche Katalogregressionen prüfen die Auflösbarkeit aller
von eingebauten Befehlen deklarierten Ergebnisschemata ohne Ausführung dieser
Befehle sowie proposal-apply-v1 über öffentliche Liste, argv- und strukturierte
Schemaabfrage ohne Projekt. Der abgerufene Vertrag bleibt geschlossen und
passiv; unbekannte Folgeversionen bleiben abgewiesen. Die vorhandene vollständige
Abnahme mit echten Befehlsbeispielen, native Proposal-Apply-, Quorum-, Herkunfts-,
Receipt-, Crash-/Recovery- und Retrytests werden nicht ersetzt oder verkürzt.
Die gesamten Schema-Katalog-, CLI-/Request- und bisherigen Pflichtauswahlen
bleiben je Stage ungefiltert enthalten. Alle vergebenen Testnummern bleiben;
die neuen W-Tests werden vor den noch nicht ausgebrachten R-Tests angehängt.

Alle Korrekturen aus 675–677 und die vollständige ursprüngliche Folge
18.k.W, 18.k.R, 18.k.C bleiben mit unveränderten IDs, Nachrichten, Rollen
implementation und Abnahmen erhalten. W umfasst den gesamten uncommitteten
Arbeitsstand. Jede Stage erhält vor ihrem Commit ein eigenes
N=3-plus-Pflichtauswahl-Gate; erst dann folgt die nächste. Erfolgreiche Commits
werden nicht wiederholt, der C-Endstand wird nicht vorab installiert.
Historische Berichte bleiben bytegleich. Vorbereitete Planwerte gelten erst
nach den jeweiligen erfolgreichen Gates; anschließend bleibt 18.l.W offen.

Dev prüft Syntax, reine Collection, stabile Katalog-/Stagebindungen und das
native Paket. Keine Verhaltenstests, Fixtures oder Test-Unterprozesse in Dev;
die fachliche Abnahme der Korrektur erfolgt ausschließlich in Apply.
