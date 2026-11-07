# MERGE-CONFLICTS-608 — vollständiger Konfliktvertrag und Schritt 17.g

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## MERGE-CONFLICTS-608 — vollständiger Konfliktvertrag und Schritt 17.g

Autorität: SPECROAD-DECISION-1, 2.4.3.1 und aktueller Control-Vertrag 4,
clarification_allowed=true, Restbudget 3. Keine menschliche Reviewfreigabe
wird behauptet. Das nativ geprüfte Result 1fa54a bindet SHA-256
`75ab571ab381cceb5aee0518e9f736a16e06df5a13229b9f8d359afed0172078`
an den sauberen HEAD `a75ef0e994c433d723314bb0f0b3638c124bb131`.
Bundle 607 ist mit 17.f.W/R/C vollständig committed; seine Gates weisen
7334, 7389 und 7890 bestandene Tests aus. Produktstand: 711/900.

Lücke: SR-REQ-0371/0375 und 17.g verlangen stabile Konflikt-IDs, drei Werte,
Impact, Auflösungsarten und maschinenlesbaren Zugriff, ohne deren JSON-Form,
ID-Bindung oder Fehlend/null-Unterscheidung festzulegen. Geprüft wurden
10.15.1–3, 12.26, K.3, 17.g–17.l, die bestehenden Feld-, Relations-,
Lifecycle- und Anhangkonflikte sowie native Quellen und CLI-Verträge.

Alternativen: flüchtige Listennummern; freie UUIDs; oder deterministische IDs
mit vollständiger Plan-/Quell-/Herkunftsbindung. Gewählt ist letzteres.
Für fehlende Werte wurde ein expliziter Anwesenheitstag statt JSON-null
gewählt. Direkter belegter Relationsimpact vermeidet spekulative Folgen.
Eine gespeicherte lesende CLI-Anzeige und ein separates natives Quelllesegate
vermeiden erfundene Herkunftsprovider oder Zugriff auf fremde Quellpfade.
Schutzkonflikte bleiben unauflösbar durch Take/Value; kein Sicherheitsgate
wird abgeschwächt. Die additive, versionierte Hülle ist reversibel und
ändert keine bestehenden Projektbytes, Kompatibilitätszusagen oder Reviews.

Zuerst gelten 10.15.4, die folgenden Planabnahmen und aktive Katalogbindungen.
Diese Klärungsstage lässt sämtliche Produktcommits offen. Danach folgt der
vollständige 17.g-W/R/C-Schritt mit getrennten Apply-Gates. W liefert alle
Konfliktzweige und den lesenden CLI-Zugriff. R härtet manipulierte Daten,
Fehlend/null, Quellenwechsel und Schutzgrenzen. C trennt Datenmodell und
Darstellung ohne neue Fachlogik. Folgeschritte 17.h–17.l bleiben offen;
keine Auflösung, Metadatenberechnung, Zielvalidierung oder Publikation wird
als fertig behauptet. Dev führt keine Verhaltenstests aus. Keine Änderung
von Control, lokalen Betriebsdaten, Historie oder Budget.
