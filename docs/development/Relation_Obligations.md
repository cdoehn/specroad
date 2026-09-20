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
