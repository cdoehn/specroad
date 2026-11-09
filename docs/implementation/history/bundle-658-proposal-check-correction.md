# Bundle 658 — Proposal-Check und Schema-Katalog korrigieren

9. November 2026. Quelle `8deef4bc7f2dbd052956cf7004e3e9d74756537e892a600ee0e1b3d0a06b3f71`,
Base-Commit `e4c7e72791a9385a898036e3eeb73f75c3bd770f`.
Das native Result von Bundle 657 belegt den erfolgreichen Klärungscommit
`PROPOSAL-CHECK-657` mit 7.290 bestandenen ausgewählten Tests. Dieser Commit
bleibt erhalten und wird nicht wiederholt. 18.g.W scheiterte danach; R/C wurden
noch nicht ausgebracht. Das Log meldet 38 Fehler und 10.184 bestandene
Test-/Subtestergebnisse bei 10.220 ausgewählten Testidentitäten. Das ist
kein erfolgreicher W-Nachweis. Der vollständige erhaltene Arbeitsstand ist
byte- und modusgleich mit dem angekündigten W-Zustand; die committed Basis
stimmt mit dem abgeschlossenen Klärungszustand überein.

Zwei belegte Ursachen werden eng korrigiert:

- Das neue Ergebnisschema verwendete `uniqueItems`, das weder zum unterstützten
  nativen Schema-Vokabular noch zum publizierten Meta-Vertrag gehört. Die
  ID-Listen verwenden nun die bestehende Array-/String-Beschreibung. Native
  Diff-Inventare liefern weiterhin die tatsächlichen IDs; geschlossene
  Feldmengen, Typen, Hashbindungen und Fachprüfungen bleiben erhalten.
- Das Query-/Rendering-Testprojekt verband ein Dokument direkt mit einem
  Inhaltsblock. Der vorhandene Modellvertrag verlangt die Section dazwischen.
  Der Test verwendet nun diesen gültigen Graphen und prüft zusätzlich native
  Renderbytes und deren Berichtshash sowie unveränderte Originaldateien.
  Die fachliche Relationsregel wird nicht gelockert.

Der vollständige Rest `18.g.W`, `18.g.R`, `18.g.C` behält IDs, Rollen,
exakte Commitnachrichten und ursprüngliche Pflichtauswahlen. Alle bereits
vorbereiteten Tests und stabilen Testnummern bleiben erhalten; sämtliche
fehlgeschlagenen Testdateien sind in jedem Korrektur-Gate verpflichtend.
W startet auf den vollständigen Vorherbytes des Fehler-Results einschließlich
aller 26 dirty Pfade. R enthält weiterhin sämtliche Robustheitsfälle, C die
ursprüngliche Strukturtrennung bei identischen R-Testbytes. Keine neue
Spezifikationsentscheidung, keine Klärungsstage und keine Budgetänderung.
Die historische Vorbereitung von Bundle 657 bleibt bytegleich erhalten.

Dieser Zielzustand W setzt den Plan erst nach seinem eigenen erfolgreichen
Apply-Gate und Commit auf 748/900, nächste Position 18.g.R. Vor Übergabe
bleiben diese Abnahmen offen. Nur der vollständige C-Abschluss schließt Bundle
658; 18.h und spätere Arbeit bleiben offen. Native Paket-/Stufenprüfung,
Syntaxprüfung und reine Collection in Dev sind keine Verhaltenstest-Erfolge.
Alle Verhaltenstests laufen ausschließlich durch Apply. Keine Änderung an
Testauswahlpolicy, Betriebsdaten, Diensten oder an der normativen Spezifikation.
