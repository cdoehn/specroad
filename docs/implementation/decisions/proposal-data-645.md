# PROPOSAL-DATA-645 — Proposalinhalt und Herkunft

9. November 2026 · SPECROAD-DECISION-1 / Vertrag 4 · Planrevision 114.

Basis: erfolgreiches sauberes Result
`e2a12bcbb7d0879fe1f35ec8f16ebbac1a7d12f6fb538e773d3fa0d8e31e52d5`,
Commit `532218acf28f023a3d417f45c41d689de08d9083`.
18.a ist offen; 729 von 900 Produktpositionen sind abgeschlossen.
Der gebundene Auftrag erlaubt eine neue Detailklärung bei Restbudget 2.
Keine eigene Budgetänderung, keine Wiederholung abgeschlossener Commits.

**Notwendige Lücke.** SR-REQ-0157/0162/0163 verlangen Modellherkunft,
Änderungsziele, Begründungen, Quellen, Annahmen und Konfidenz. Die konkrete
JSON-Anordnung und die Einzelbegründung für unknown sind offen. Der vorhandene
passive Record-Parser erlaubt diese Felder noch nicht. Insbesondere wäre eine
Erweiterung der geschlossenen nativen Operationsobjekte eine zusätzliche
Änderung des gemeinsamen Change-Plan-Formats.

**Alternativen.** Freitext oder beliebige Extensions wären nicht zuverlässig
prüfbar. Ein zweiter ausführbarer Operationsbaum würde widersprüchliche Pläne
ermöglichen. Gewählt ist die additive, rein deklarative Erläuterungsliste mit
exakter Zuordnung zum vorhandenen Plan und den bereits benannten KI-Feldern.
Die bestehende Provenienzstruktur und random128-Identität werden wiederverwendet.
Ein eigener Modell-/Netzwerkzugriff oder stilles Auffüllen unbekannter Daten
ist nicht erforderlich. Historische Restore-Originalbytes bleiben lesbar.

**Grenzen.** Keine Änderung von Scope, Freigaben, Sicherheitsregeln oder
bestehenden Migrationspflichten. Keine behauptete reale Provenienz oder echte
Human-Freigabe. Identitätsinventar und Writer-Lock bleiben Aufgabe der späteren
nativen Publikation. 18.a liefert den vollständigen reinen Erzeuger; spätere
Plangates, CLI und Statusübergänge bleiben offen wie bisher vorgesehen.

**Übergabe.** Genau ein OFF-PLAN-Klärungspräfix vor 18.a.W/R/C. Jede Stufe hat
ihr eigenes Apply-Gate. 10.3.1 ist die normative Quelle; aktive Katalogbindungen
werden auf deren Specbytes umgebunden. Dev führt keine Verhaltenstests aus.
