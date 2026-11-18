# Bundle 739 — Proposal-Dialog: unterstützter Schemavertrag

Das native Result mit SHA-256
`5b9e5dfd726379f1f94b156ac04dece41f54097c2b9524389d68c16242ddd4cb`
bestätigt den Klärungspräfix `PROPOSAL-DIALOG-738` als Commit
`f86b093b52de50addbf03db034e47f50610e6f1b` mit 7.067 bestandenen Tests,
darunter 147 Pflichtfälle. Der bestätigte Produktfortschritt bleibt 792/918.
Das anschließende W-Gate meldet 53 fehlgeschlagene und 13.943 bestandene Tests;
W blieb uncommitted erhalten, R und C wurden nicht ausgebracht.

Die neue äußere `proposal_change`-Operation verwendete `maxItems`, obwohl
der eingebaute, geschlossene Schema-Prüfer dieses Schlüsselwort nicht kennt.
Deshalb scheiterten bereits Schemaressource und Parser; auch `schema.list`
und darauf beruhende Workabläufe konnten ihren Vertrag nicht abschließen.
Die Korrektur verwendet die bereits unterstützte Negation von `minItems: 2`
innerhalb des weiterhin verpflichtenden Arrays. Leere Liste und genau eine
ID bleiben zulässig; zwei oder mehr Einträge bleiben ausgeschlossen.
Die getrennte native Prüfung von Anzahl und Change-ID-Werten bleibt erhalten.
Kein neues Schema-Vokabular, keine Erweiterung des fachlichen Editvertrags,
keine Abschwächung der bestehenden Fail-closed-Prüfung.

Der bestehende vollständige Feldgrenzentest prüft zusätzlich die öffentliche
Change-Plan-Schemaressource und den nativen Operationsparser gemeinsam:
leere Liste, einzelne gültige ID, zwei verschiedene IDs, doppelte IDs,
falscher Containertyp sowie ungültige leere oder numerische Einträge.
Eingabewerte bleiben unverändert. Bestehende Testidentitäten, Parametervarianten,
Assertions und stabile Nummern werden erhalten; keine neue Umnummerierung.
Die vollständigen realen Dialog-, Review-, Writer-, Katalog- und Workabnahmen
bleiben in der Pflichtauswahl aller betroffenen Stages.

Der vollständige offene Rest bleibt `18.p.W`, `18.p.R`, `18.p.C`, jeweils mit
Rolle `implementation` und unveränderter Commitnachricht. Der erfolgreiche
Klärungspräfix wird nicht wiederholt. Sämtliche Vorherbytes sind an den
erhaltenen W-Arbeitsstand dieses Results gebunden. Alle drei angekündigten
Zielstände erhalten dieselbe Korrektur; C behält die echte strukturelle
Extraktion und übernimmt exakt die R-Testbytes. Spezifikation 0.2.94 und
Entscheidungsvertrag bleiben bytegleich, ohne neue Klärung oder Budgetänderung.

Dev führt ausschließlich Syntax-, statische, reine Collection- und native
Paket-/Fortsetzungsprüfungen aus. Kein Testkörper oder Fixture läuft in Dev.
Jede Stage benötigt ihr eigenes Apply-Gate vor dem Commit. Der nachfolgende
Rückpaketexport 18.q bleibt der nächste vollständige Planschritt; die offene
Writerintegration wird zuerst in allen drei angekündigten Zuständen korrigiert.
Vorbereitung oder Collection sind kein bestandener Verhaltenstest.

Ziel erst nach dem eigenen erfolgreichen Gate dieser Stage: **18.p.W**, **793/918**, danach **18.p.R**.
