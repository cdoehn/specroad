# ANALYZER-OBSERVATION-747 — vollständige Auswahl und Beobachtungsdaten

19. November 2026. Detailklärung für die bereits beauftragten Gruppen 19.c/d,
nach SPECROAD-DECISION-1, 2.4.3.1 und dem gebundenen Vertrag 4 mit positivem
Restbudget. Genau ein Klärungspräfix vor echter vollständiger Umsetzung;
keine Änderung der Scope-, Sicherheits-, Review- oder Nachweispflichten.

T.3/T.4 nennen Originalbindung, Findings, Coverage und Engineprovenienz, aber
noch keine geschlossenen Mengen-/Zählerformen, Subject-Finding-Verweise oder
Darstellung unbekannter Engine-Fakten. Ein interoperabler Reader benötigt
diese normativen Datenformen vor der Implementierung. Die feste Umschlag-
Version ist von der bereits deklarierten Adapter-Payloadversion zu trennen.

Alternativen: freie verschachtelte Resultate ließen widersprüchliche Mengen
und verlorene Bindungen zu. Automatische Status-/Engine-Ergänzungen würden
unbelegte Verarbeitung oder Runtimefakten erfinden. Strenge Pflichtwerte ohne
Unknown-Repräsentation würden T.4 widersprechen. Gewählt sind deshalb kleine
geschlossene Hüllen, eine vollständige disjunkte Subjectpartition, explizite
null/Grund-Fakten und passive namespaced Payloads/Details. Engineinventare
werden nur gehasht gebunden, niemals aus lokalen Betriebsdaten geraten.

Für Auswahl und Aktualität werden native vollständige Query-/Partial- und
Quellbeobachtungsdienste wiederverwendet. Impliziter Kontext, Pagination,
Textnormalisierung oder Dateipfadinterpretation sind keine Alternativen zur
ausdrücklich geforderten Vollständigkeit und Datenminimierung. Originalhash
ist der bestehende vollständige JCS-Artefakthash, kein Dateiformat-Whitespace.

Normativ maßgeblich sind T.3.2 und T.4.1. M19 c/d ergänzen ihre Abnahmen um
die konkreten Bindungs-/Grenzfälle; aktive Kataloge werden an dieselben
Specbytes gebunden. Es werden keine Require­ment-IDs oder Planpositionen
hinzugefügt. CLI, Reportpackages, tatsächlicher Sprachworker, Work-Fortsetzung
und fachliche Evaluation behalten ihre späteren eigenen Abnahmen.
