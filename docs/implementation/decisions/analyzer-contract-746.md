# ANALYZER-CONTRACT-746 — passive Analyzerwerte

18. November 2026, delegiert gemäß SPECROAD-DECISION-1 und 2.4.3.1.
Ausgang ist das vollständig erfolgreiche Result mit SHA-256
`b14b227a542ab40f5611933da0ade2f265fa942f945c6bc98dc5c92751a3da20`.
801/918 Planpositionen sind bestätigt, der nächste Schritt ist 19.a.W.

T.2 nannte dependency_requirements ohne Wertform; T.3 band Descriptor und
Capabilities, Kontext und Settings ohne vollständige geschlossene Struktur.
Die Präzisierung T.2.1/T.3.1 verwendet kleine passive Objekte, bestehende
JSON-/Namespace-/Identitätsverträge und die bereits bestimmte JCS-Projektion.
Alternativen waren unstrukturierte Freitextobjekte oder ausführbare Plugin-
Metadaten/Dependencyresolver. Erstere verhindern eine eindeutige geschlossene
Validierung; letztere erweitern Scope und Vertrauensgrenze. Gewählt sind
unverändert erhaltene Abhängigkeitsbeschreibungen ohne automatische Auflösung,
ein vollständig gebundener Descriptor je Analyzer und expliziter Kontext.

Das ist eine additive, versionierte und rücknehmbare Detailfestlegung im
bestätigten Scope von 19.a/19.b. Bestehende Produktdaten werden nicht migriert;
keine menschlichen Reviews, Sicherheitsgrenzen oder realen Nachweise werden
ersetzt. Der vorhandene normative Schreib-ID-Typ bleibt unverändert.
Ein bekannter eingebauter Descriptor behauptet noch keinen gelieferten Worker.

Genau dieser optionale OFF-PLAN-Präfix geht den vollständigen Gruppen
19.a.W/R/C und 19.b.W/R/C voraus. Jede Stage behält ihr eigenes Apply-Gate.
Der Präfix erhöht keinen Produktzähler. Vorbereitung/Collection sind kein
Verhaltenserfolg. Worker, Projekt-Subjectauswahl, CLI, Reportimport und Work-
Fortsetzung verbleiben an ihren bestehenden späteren Planpositionen.
