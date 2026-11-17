# Bundle 729 — Proposalrechte und Gitgrenze

Das native Result mit SHA-256
`ea0c7ec1c0a90e398ae057321471f30e29644424ba8c9a03fcac1ac25a328e63`
bestätigt Bundle 728 vollständig bis einschließlich `18.m.C`, Commit
`6e847f5ed3a3fa0cc1f9c34ddbec50f9fa8b733a`, mit sauberem Arbeitsbaum.
Die drei Gates enthalten 15.063, 15.078 und 15.192 bestandene Testidentitäten.
Bestätigt sind 786/918 Produktcommits; es gibt keinen offenen Korrekturrest.

Die vollständige Gruppe 18.n.W/R/C erhält die bestehende Spezifikation und
ihre Freigabegrenzen. Es ist keine normative Detailklärung erforderlich.

W weist einen nichtmenschlichen Proposalreview auch bei Vorschauen bereits
an der gemeinsamen Requestgrenze ab. Der Review-Fachadapter prüft den Akteur
vor einer fehlenden Hostautorität und vor Projektzugriff; öffentliche Agenten-
Requests erhalten damit den konkreten Policyfehler `human_review_required`.
Legitime nichtinteraktive Apply-Aufrufe behalten die unabhängigen Voraussetzungen
aus tatsächlichen menschlichen Reviews, aktueller Basis und Hostautorität.
Die Integrationsfälle verwenden reale native Veröffentlichungen und Receipts
in einem eigenen Projekt ohne Git.

R prüft nichtleere Proposal-Apply-Operationsfolgen vor Konstruktion der gemeinsamen
Authoring-Anfrage: genau ein abschließender Apply-Kontrollschritt und dessen
geschlossener Nachweis. Leere Anfragen bleiben reine Actor-/Request-Vorprüfungen.
Ein geparster Nachweis erteilt keine Schreibbefugnis; aktuelle Originale,
Reviewprovenienz, Sperre und Hostautorität bleiben beim nativen Writer verpflichtend.
Fehlende, falsch kodierte, doppelte, versetzte und fehlgeleitete Nachweise werden
abgewiesen. Ein nachträglicher Verlust echter Zustimmung bleibt wirksam.

Ein echtes temporäres Git-Repository mit Commit, Branch, Tag, Remote und Hook
prüft den vorhandenen Entwurfswriter sowie Validate, isoliertes Check,
Reviewstart, menschliche Entscheidung und Agenten-Apply. Das vollständige
Gitinventar und externe Dateien bleiben byte- und modusgleich; Prozess- und
Netzwerkversuche werden zusätzlich beobachtet. Projektseitige Ausführungs-
deklarationen werden vor dem Proposalhandler abgewiesen. Die bestehenden
reinen Create-/Edit-, Autoritäts-, Receipt- und Agentenregressionen bleiben Pflicht.

C trennt die reine Proposal-Operationsprüfung von generischem Authoring.
Produktpolicy erhält keine Entwicklungsautomatik oder Transportbefugnis.
Alle R-Testbytes und die R-Pflichtauswahl bleiben unverändert.

Jede Stage wird erst nach ihrem eigenen Apply-Gate committed. Dev prüft nur
Syntax, statische Konsistenz, reine Collection und native Paketverträge.
Ein vorbereiteter Zielzähler oder ein Katalogeintrag ist kein ausgeführter Test.
Stabile Testnummern, N=3 und die ungefilterte Pflichtauswahl bleiben erhalten.

Anschließend folgt der eigenständige Schritt 18.o: persistierte Proposal-
Fortsetzung mit Inhalts-/Basis-/Enginebindung und frischer menschlicher
Reviewprüfung. Seine Workadapter und geschlossenen Datenverträge sind hier
nicht als bereits umgesetzt oder abgenommen ausgewiesen.

Zielstand dieser Stage nach ihrem erfolgreichen Gate: **18.n.R**, **788/918**, danach **18.n.C**.
