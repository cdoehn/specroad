# Bundle 806 — Fortschritt bei unbekannten Testlaufzeiten

24. November 2026. Das native Fehler-Result
`342fd8e652ef4f5905fff3e0e7dba8c428196a8b210fb2a3258d738473f2628f`
belegt den abgebrochenen Apply von Bundle 805. Sein W-Gate meldet 26.590
bestandene Tests und KeyboardInterrupt nach 30.548,36 Sekunden; 188 der
26.778 ausgewählten Tests waren noch nicht abgeschlossen. Es entstand kein
weiterer Commit. Bestätigt bleiben 897/996 Positionen bis 21.c.C sowie der
bereits erfolgreiche Klärungscommit. Teilresultate ersetzen keine Abnahme.

Die Diagnose zeigt einen Widerspruch im Verteiler: Tests ohne Baseline können
vollständige Hostmessungen besitzen. Ein unbekannter Kandidat wurde nur
schnellen Erkundungsworkern angeboten, seine früheste Fertigstellung aber
über alle Hosts berechnet. Ein ausgeschlossener Host konnte dadurch alle
zugelassenen Worker überbieten. Bei leeren Queues blieb der gesamte Rest
liegen; der bisherige Nachfolger-Fallback für eine belegte Queue half nicht.

Der Fertigstellungsvergleich verwendet für unbekannte Kandidaten dieselben
Worker wie deren bestehende Erkundungsregel: begrenzte schnelle Slots neben
bekannten Tests, beim unbekannten Rest die schnellsten verfügbaren Worker.
Hostmessungen und Restlast bleiben innerhalb dieser Menge maßgeblich.
Bekannte Tests vergleichen weiterhin den gesamten verfügbaren Pool. Weder
Testauswahl noch Hostgrenzen, Prognosedaten oder Wiederholungsregeln ändern
sich. Dies korrigiert die Implementierung von 2.5.5 ohne neue Detailklärung.

Acht Regressionfälle prüfen Einzeltest, Paar und 188 unbekannte Resttests,
frühe Erkundung bei zwei und acht schnellen Slots, den besten gemessenen
Fertigstellungszeitpunkt unter zugelassenen Workern und den vollständigen
Hostvergleich bekannter Tests. Sie verwenden den echten Scheduler mit den
vorhandenen kleinen Transport-Doubles und einer deterministischen Uhr.
Der vollständige Ablauf prüft Fortschritt, xdist-Nachfolger und genau einmalige
Abarbeitung; unbekannte Tests werden nicht auf schwächeren Hosts aufgefüllt.

Die Korrektur erhält exakt 21.d.W, 21.d.R und 21.d.C, ihre ursprünglichen
implementation-Rollen und Nachrichten. correction_of bindet den offenen
Plan `0bf5f2f7d24b0b6ad0c5f2ba1de667a6409c9eba83885d4980f2c6f15e11cfcc`.
Alle bisherigen Produktkorrekturen und zusätzlichen R-Fälle bleiben erhalten;
C behält die R-Testquellen. Die bisherigen Pflichtauswahlen werden vollständig
übernommen und um Scheduler-, Hostpool-, Live-/MOVE-/Speculate-Regressionen
und die gesamte neue Testdatei ergänzt. Stabile Testnummern bleiben erhalten.

Die drei gemessenen Core-Builds aus Bundle 805 und ihre Originalbelege bleiben
bytegleich; die Korrektur betrifft den Testverteiler außerhalb des Core-Builds.
Jede Stage prüft weiterhin ihren eigenen exakten Ressourcenbeleg. Es werden
keine Messwerte auf veränderte Builds übertragen und keine neuen Messungen
behauptet. Die unveränderten CPU-/RSS-Gates bleiben Pflicht.

Jeder Zustand wird erst nach seinem eigenen N=3-plus-Pflichtauswahl-Gate
committed; kein Endstand wird vorab installiert. Dev führt keine Testkörper
aus. Syntax, reine Collection und native Paketvalidierung ersetzen nicht die
noch offene Apply-Abnahme. Zielzähler gelten erst nach dem jeweiligen Commit.
21.e und menschliche Endabnahmen bleiben offen; kein neuer Automatikauftrag.
