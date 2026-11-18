# Bundle 735 — Portable Proposalprüfung und aktuelle Reviewpflicht

Das native Result mit SHA-256
`56d80de42ca9a480c0acd000b1c69bb2b6acab725042b4748de71319f36414e1`
bestätigt Bundle 734 bis einschließlich `18.n.C`, Commit
`66576f5f143f34daa57a9e987e687ec91fb04448`, mit sauberem Arbeitsbaum.
Das Gate enthält 9.304 bestandene Tests, darunter 3.036 Pflichttests.
Bestätigter Ausgang sind 789/918 Produktcommits, ohne offenen Korrekturrest.

Der einzige optionale Präfix PROPOSAL-WORK-735 präzisiert den vollständigen
passiven Workvertrag und die zusätzliche Bindung an den bestehenden Apply.
W speichert vollständige Originale und Basisbytes, prüft Eingabeblöcke,
führt die tatsächliche isolierte Prüfung aus und liefert ihr Ergebnis über
die nativen Work- und Paketwege. Abschluss und erneute Lieferung rechnen die
fachlichen Ergebnisse nach. Apply prüft optional den abgeschlossenen Workstand
gegen aktuelle Inhalte/Basis/Engine und behält alle echten Review-, Host- und
Writerprüfungen. Workabschluss verändert keinen Proposal-Lifecycle.

R ergänzt strenge Audit-/Ergebniskonsistenz und erneute Prüfung des gelieferten
Checkpoints. Tests verwenden reale native Stores und Veröffentlichungen:
verlorene Zustimmung auch unter der tatsächlichen Writersperre, fehlende
Originalprovenienz, neue Inhaltsrevision/Basis/Engine, neue Sandbox, portable
Grenzen, manipulierte nachgehashte Evidenz, fehlgeschlagene Gesamtvalidierung,
Pfad-/Tempgrenzen, Abbruch und exakte historische Apply-Replays. Alle Akteure
und Laufzeitidentitäten sind ausdrücklich synthetische Testfixtures.

C trennt den geschlossenen Datenvertrag von Workausführung und Proposal-
Lifecycle. Die sechs ausgelagerten Prüffunktionen und sämtliche R-Testbytes
bleiben unverändert; die R-Pflichtauswahl gilt auch für C.

Dev führt nur statische Prüfung, Syntax, reine Collection und native
Paketvalidierung aus. Jeder Zielstand benötigt sein eigenes N=3-plus-Pflichtgate
vor dem tatsächlichen Commit. Vorbereitete Fortschrittswerte und Kataloge sind
keine bestandenen Verhaltenstests. Keine erfolgreiche Position wird wiederholt.

Danach folgt 18.p.W. Bei dessen Vorprüfung zeigte sich: Die öffentliche reine
ProposalEdit-API bereitet eine neue Inhaltsrevision vor, aber der vorhandene
native Publikationsadapter veröffentlicht bislang nur neue Drafts, Reviews
und Apply. Ein vollständiger Überarbeitungsdialog darf deshalb nicht mit
direkten Testdateischreibungen als bereits integriert ausgegeben werden.
Die native Überarbeitungsveröffentlichung und ihre vollständigen öffentlichen
Dialogabnahmen gehören in den folgenden eigenständigen Planschritt; 18.p
bleibt hier vollständig offen. Dieser Durchlauf liefert eine vollständige
zusammenhängende W/R/C-Gruppe, keinen gekürzten Teil von 18.p.

Zielstand dieser Stage erst nach ihrem eigenen erfolgreichen Gate: **18.o.C**, **792/918**, danach **18.p.W**.
