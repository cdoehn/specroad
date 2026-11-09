# Bundle 651 — Proposal-Inhaltsrevision und Hashprojektion

9. November 2026. Quelle ist das vollständige erfolgreiche Result
`107ccae89cd8e4deb25d6c0689965de29b69a9a3aec052289805985d042c57c0`, Base-Commit `8f3b4e78ce0e75a01485457fdfe7af5bc276d3ae`.
Bundle 650 wurde sauber abgeschlossen: 18.c.W mit 7.755, 18.c.R mit 7.662
und 18.c.C mit 7.958 bestandenen ausgewählten Tests. Diese drei Commits
werden nicht wiederholt; bestätigt sind 738/900 Planpositionen.

Die vorhandene Spezifikation 10.3 und Anhang K bestimmt die Revisions- und
Projektionsregeln bereits. Es gibt keine neue Detailklärung, keine normative
Ausnahme und keine Änderung des Klärungsbudgets. Die zusammenhängende Folge
18.d.W/R/C führt die bereits lesende Projektion in die Revisionsvorbereitung
ein und bindet sie an die vorhandene native Prüfung von Originalen und Reviews.

## Umsetzung und Grenzen

`ProposalRevision` übernimmt ein natives Original, einen vollständigen
Zielkandidaten, die erwartete physische Revision sowie expliziten Akteur und
Zeitpunkt. Der Wert besitzt unveränderliche Vorher-/Nachherbytes. Ein echter
Inhaltswechsel erhöht physische Revision und Inhaltsrevision einmal; reine
Kontrolländerungen erhalten Inhaltshash, Inhaltsrevision und Freigabebindung.
Unveränderter kanonischer Inhalt erhält sogar die originalen Formatierungsbytes.
Erstellungsdaten bleiben erhalten; Updatezeiten folgen der vorhandenen exakten
Anhang-K-Policy ohne eigene Uhr. Historien dürfen nur unverändert fortbestehen
oder kontrollseitig erweitert werden. Inhalt und neue Kontrollentscheidungen
werden nicht vermischt; ein Inhaltswechsel setzt auf draft zurück.

Die feste RFC-8785-Projektion schließt ausschließlich die elf in 10.3 genannten
Top-Level-Felder aus. Basis, vollständiger Plan, Erläuterungen, Herkunft und
Extensions bleiben gebunden, einschließlich gleichnamiger verschachtelter
Kontrollschlüssel. C führt die bisher doppelte Inhaltsprojektion und Hashbildung
in einem Modul zusammen. Die bisherigen Importpfade bleiben kompatibel.

Der Integrationsfall verwendet eine kleine vollständige native Projektbasis,
echte Rekonstruktion/Checks und ausdrücklich synthetische menschliche
Entscheidungen. Die vorbereiteten Kontrollrevisionen müssen den Originalbytes
der vollständigen Reviewhistorie entsprechen und erneut durch deren Verifier
laufen. Nach Inhaltsänderung bleibt die Historie gültig und sichtbar, hat aber
keine aktuelle Freigabewirkung mehr. Ein weiterer Fall verbindet die geordnete
18.c-Änderungsfolge mit dem vollständigen gebundenen Plan und genau einer neuen
Proposalrevision.

Die Vorbereitung ist kein Writer und keine Erlaubnis zur Freigabe oder
Publikation. Kontrollaufrufer schulden weiterhin die nativen Prüfnachweise und
die Transaktion unter Sperre. Die folgenden 18.e–18.k-Positionen behalten ihre
vollständigen Authoring-, Kontroll- und Apply-Abnahmen; öffentliche Integration
und ganze Abläufe bleiben offen. Die betroffenen Requirements stehen deshalb
weiterhin auf partial und behaupten keinen vollständigen CLI-Abschluss.

## Getrennte Zustände und Abnahmen

- W: beide Revisionen, Inhaltshash, explizites Audit, native Originale und
  vollständige Planbindung; reale Reviewhistorien belegen getrennte
  Inhalts-/Kontrolländerungen und unwirksame frühere Freigaben.
- R: exakte JSON-Semantik für verwaltete Felder und Historienpräfixe, insbesondere
  keine Gleichsetzung von true mit 1; Projektionsmatrix über verschachtelte
  Extensions und Operationen, offene/terminale Zustände, stale Revision,
  unveränderte Originalbytes, typisierte Eingaben sowie Zahl-/Zeitgrenzen.
- C: eine feste Inhaltsprojektion für Erzeugung, Originalprüfung, Revisions-
  vorbereitung und Freigabebindung; W-/R-Testbytes und Fehlerverträge bleiben.

Vorbereiteter W-Zustand: Die Fortschrittswerte gelten erst nach dem
erfolgreichen eigenen Apply-Gate und Commit. R und C bleiben bis zu ihren eigenen Gates offen.

Dev führt keine Verhaltenstests aus. Syntax, reine Collection und native
Paketvalidierung sind keine bestandenen Apply-Gates. Jede Stage verlangt die
eigene gefilterte N=3-Gruppe plus ungefilterte Pflichtunion vor ihrem Commit.
Neue/geänderte Tests sowie Proposal-, Change-Plan-, Audit-/Metadaten-, Schema-,
Migrations- und Restore-Regressionen bleiben in der Pflichtauswahl. Historische
Testnummern bleiben erhalten; neue werden ausschließlich angehängt. Die
Übergabe beendet diesen Auftrag ohne eigene Apply- oder Warteschleife.
