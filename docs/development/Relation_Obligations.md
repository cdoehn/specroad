# Pflichtbeziehungen und Reviewkontexte – 3.k

Die API prüft übergebene `SourceRelations`, nicht die Vollständigkeit eines
Projekts. Sie schreibt nichts. `RelationObligations` stellt die Herkunfts- und
Verifikationsminima freigegebener Requirements fest. Verweise müssen auflösbar
und typzulässig sein. Die Mindestregeln nach 9.4/9.8 und SR-REQ-0061/0062 sind
additiv; Tags, Priorität, Freitext, Waiver und fremde eingehende Beziehungen
ersetzen sie nicht. Freigegebene Requirements benötigen nach 9.8 ohnehin einen
prüfbaren Vertrag; eine unbelegte Nicht-Verifizierbarkeit wird nicht geraten.

Ein positives Ergebnis sagt nur, dass diese Minima erfüllt sind. Es sagt nicht,
dass die Beziehungen `current` sind, die Zielnachweise bestanden wurden oder
das Requirement freigegeben werden darf. Der Aufrufer muss die erforderliche
vollständige Quellmenge bereitstellen. Leere Eingaben bedeuten explizit eine
leere geprüfte Menge, nicht die erfolgreiche Prüfung eines gesamten Projekts.

`EndpointReviewContext` bindet den vollständigen kanonischen Artefakthash und
getrennt davon die Projektion `relation_context_hash-v1` aus Anhang J.2. Nur
die ausdrücklich genannten Top-Level-Felder entfallen. Gleichnamige Felder
in Extensions oder fachlichen Unterobjekten bleiben gebunden. Originaldateien
und normative Zeichenketten werden nicht normalisiert oder verändert.

`relation_content_sha256` entfernt gemäß J.1 ausschließlich `created_at` und
`created_by`. Änderungen an Begründung, Position oder Erweiterungsdaten bleiben
reviewrelevant. `RelationReviewContext` verlangt eine tatsächlich am Quellobjekt
vorhandene Relation, passende Endpunkte und kanonische symmetrische Speicherung.

Die spätere Reviewauswahl, menschliche Reviewentscheidung, atomare Rücknahme
von Freigaben und der J.3-Statusalgorithmus werden hier nicht vorgezogen.
Die Hashes sind Integritätswerte über gelieferte Daten, keine Signaturen.

Verhaltenstests prüfen fachliche Daten und unveränderte Eingaben; keine
Konsolenformulierungen, Farben, Layouts, Dokumentation oder neue Testtimeouts.

## Explizite profilabhängige Minima (R)

`MinimumRelationRule` ist ein unveränderlicher interner Wert für bereits
aufgelöste Regeln. Er führt keinen Code oder SRX aus und erfindet kein neues
persistentes Profilformat. Der spätere Profilcompiler bleibt verantwortlich
für Komposition, Auswahl und bedingte Regeln. Filter berücksichtigen alle
Core-Artefakttypen, alle sieben Reifegrade, gespeicherte Beziehungstypen und
bei Bedarf den Typ des gegenüberliegenden Endpunkts. Richtungen sind
`outgoing`, `incoming` und `both`, relativ zum geprüften Artefakt.

`minimum` zählt verschiedene gespeicherte Relations-IDs. Mehrere echte
Beziehungen zum gleichen Ziel bleiben verschiedene Beziehungen; berechnete
inverse Sichten erzeugen keine zusätzliche Identität. Alle Treffer-IDs und
die deduplizierten Endpunkt-IDs bleiben für die Erklärung erhalten. Auch
mehr als hundert Treffer werden nicht durch eine Anzeigegrenze abgeschnitten.
Die Richtung nutzt die gespeicherte Art: Eine eingehende `supersedes`-Regel
braucht keine illegale gespeicherte `superseded_by`-Relation.

Die Diagnose behält die ausdrücklich gelieferte Severity `info`, `warning`
oder `error`. `requirements_satisfied` prüft sämtliche Minima, `has_errors`
nur verletzte Fehlerregeln. Beide sind von einer fachlichen Freigabe getrennt.
Regeln mit der reservierten Kennung `core:` und doppelte Profilregel-IDs werden
abgewiesen. Auch `minimum=0` kann die zusätzlich geprüften Core-Minima nicht
abschalten. Nicht passende Filter erzeugen keine Pflicht für andere Typen.

Die SHA-256-Werte für das gesamte gelieferte Quellmodell und die sortierte
explizite Regelmenge sind getrennt. Sie beweisen keine Frische lokaler Dateien,
keine Vollständigkeit eingehender Quellen außerhalb des übergebenen Bestands
und keine Echtheit eines Profils. Dafür sind spätere aufrufende Gates zuständig.

## Interne Trennung (C)

Die öffentliche API bleibt gleich. Reine Hashdomänen liegen in
`_review_projection`, unveränderliche Review-Beobachtungen in
`review_context_values`, voraufgelöste Pflichtregeln in `_obligation_rules`
und Prüfergebniswerte in `obligation_values`. Die gemeinsame Zählung verwendet
bei Core- und Profilregeln dieselbe gespeicherte Relationsidentität. Keine
Reviewauswahl oder automatische Freigabe wird in diese Bausteine aufgenommen.
