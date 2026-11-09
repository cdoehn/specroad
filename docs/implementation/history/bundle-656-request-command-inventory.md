# Bundle 656 — Befehlsinventar der strukturierten Requests

9. November 2026. Quelle ist das nativ geprüfte Fehler-Result
`2d5778f2b4d17dd58efe079551885dc3ba05819b1bfe93d380fe9b7d398a545a`, HEAD `051fac80a82dfa2f577591e9920614c42a7c4ad0`.
Bundle 655 scheiterte erneut vor 18.f.W: 9.100 ausgewählte Tests bestanden,
ein Test schlug fehl. Die vier in Bundle 655 korrigierten Fehler traten in
dieser Auswahl nicht erneut auf. Kein Commit entstand. Der vollständige
uncommittete W-Zustand ist die neue Basis; bestätigt bleiben 744/900 Positionen.

## Korrektur

RequestWorkTests.test_unavailable_aliases_are_not_silently_registered enthält
eine eigene geschlossene Erwartungsliste aller öffentlichen Befehle. In dieser
Liste fehlte der in 18.f.W tatsächlich implementierte proposal.validate-Befehl.
Er wird in genau dieser Liste ergänzt. Die Gleichheitsprüfung bleibt geschlossen;
es wird weder der Istbestand als erwartete Menge übernommen noch die Prüfung
entfernt. Die bisherigen Ablehnungen von retire, init.unavailable und
work.unavailable bleiben bytegleich. Keine zusätzliche Produktverhaltensänderung.

Die statische Quellprüfung der Tests findet zwei vollständige feste Befehls-
inventare, in test_registry.py und test_requests.py; beide nennen jetzt die
42 registrierten Befehle einschließlich proposal.validate. Das eigene feste
Ergebnisschemainventar enthält bereits proposal-validation-v1. Die existierenden
Capability-, Beschreibungs- und Requestprüfungen bleiben im Pflichtgate; die
Proposal-Gruppe behauptet weiterhin keinen vollständigen Review-/Apply-Workflow.
Es werden keine Testidentitäten, Nummern, Parametervarianten oder Gates entfernt.

## Vollständiger Rest und Nachweisgrenzen

Der native Fehlerfortschritt zum Vorgängerplan
`58180d92264d4c50fa68c4bf9b05b4e8e6fb8dcfe7cf5be773d3bc1718750c39` belegt unverändert
18.f.W, 18.f.R und 18.f.C, jeweils mit Rolle implementation. Die erste Stage
übernimmt sämtliche schmutzigen W-Dateien und ihre vollständigen Vorherbytes
aus diesem Result. Die angekündigte R-Vervollständigung einschließlich der sechs
zusätzlichen Pfadfälle und die reine C-Modultrennung bleiben vollständig erhalten.
Alle Testdateien bleiben zwischen R und C bytegleich. Frühere Berichte 654 und
655 bleiben in ihren tatsächlich erhaltenen Resultbytes bestehen; ihre
vorbereiteten Zielaussagen ersetzen keinen erfolgreichen Apply-Commit.

Vorbereiteter R-Zustand: Die Fortschrittswerte gelten erst nach dem
erfolgreichen eigenen Apply-Gate und Commit. C bleibt offen.

Die gesamte bisherige Pflichtauswahl bleibt erhalten, einschließlich der nun
korrigierten vollständigen Requesttestdatei. Jede Stage wird einzeln ausgebracht,
mit gefilterter fälliger N=3-Gruppe plus ungefilterter Pflichtunion geprüft und
erst nach Erfolg committed. Kein vorab ausgebrachter Endstand, kein übersprungenes
Gate und keine wiederholten erfolgreichen Commits. Spezifikation, Befugnisse,
Klärungsbudget, Testnummerierung und Laufzeitpolicy bleiben unverändert.
Keine neue Detailklärung. Dev führt keine Verhaltenstests aus; Syntax, Collection
und native Paketprüfung sind ausschließlich Vorbereitungsnachweise.
