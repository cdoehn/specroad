# Bundle 756 — Schlüssel und Anzahlen der Analyseabdeckung

19. November 2026. Maßgebliches Fehler-Result:
`98526aad9a8c72547310ae79880d58b54ab65d633203d9e0a2f4c6db6b01669a`.
HEAD `a6bbf9242619f1792e512997210d9254bc2008c2`, Zustand
`dcdb7b151af23528`. Bundle 755 scheiterte im Gate von
19.i.W mit einem fehlgeschlagenen und 11.601 bestandenen Tests. Kein Commit
entstand; bestätigt bleiben 19.h.C und 825/918. Alle sechs offenen IDs
19.i.W/R/C und 19.j.W/R/C behalten ihre Reihenfolge, Rolle `implementation`
und jeweils ihr eigenes Apply-Gate.

Die Fehlerzeile vergleicht `coverage.open` mit der Zahl 2. Nach der bestehenden
Spezifikation T.4.1 ist dieses Feld ein sortiertes eindeutiges Schlüsselarray;
die Anzahl steht separat unter `coverage.counts.open`. Die unveränderten
Report-Validatoren prüfen bereits diese getrennten Mengen und Anzahlen.
Es liegt keine normative Spezifikationslücke und kein belegter Produktfehler vor.

Die Korrektur prüft am vorhandenen projektlosen Resume-Fall den unveränderten
vollständigen Request, genau einen Report, beide ursprünglichen Subjectschlüssel
in `expected` und `open`, zwei offene Einträge und leere übrige Statusmengen.
Jedes Berichtssubject bleibt offen; `unavailable` und Code 5 bleiben Pflicht.
Die statische Prüfung der abhängigen Stufen fand dieselbe falsche Listen-/Zähler-
Erwartung im Sieben-Subject-Checkpointtest. Dort gelten dieselben exakten Prüfungen
gegen den bereits versiegelten Request. Die bisherigen Checks für Wiederverwendung,
höchstens einmalige Vorbereitung und unveränderte wiederholte Resultate bleiben.
Testnamen, stabile IDs, Parametrisierungen und alle bisherigen Pflichtdateien
bleiben erhalten. Kein Fall wird übersprungen oder in seiner Abdeckung verkürzt.

Der Produktcode sämtlicher sechs Zielzustände bleibt bytegleich zu Bundle 755;
die ursprünglichen vollständigen Ziele und echten W/R/C-Übergänge werden fortgeführt.
C übernimmt die Tests und Oracles seines R-Zustands bytegleich. Die Spezifikation,
der Entwicklungsvertrag und alle historischen Berichte aus dem Fehler-Snapshot
bleiben unverändert. Kein Klärungspräfix und keine Budgetänderung. Die erste Stage
bindet ausdrücklich alle erhaltenen uncommitteten Dateien einschließlich bereits
korrekter Bytes. Der Korrekturverweis bindet den nativen Plan 755 und exakt den
vollständigen offenen Rest; keine erfolgreichen Commits werden wiederholt.

Ziel dieser Stage: **19.i.C**, **828/918**, danach
**19.j.W** — erst nach eigenem erfolgreichem
Apply-Gate und Commit. In Dev erfolgen ausschließlich statische Prüfung,
reine Collection und native Paketvalidierung. Verhaltenstests, Fixtures und
Test-Unterprozesse werden hier nicht ausgeführt; die Apply-Abnahme steht aus.
