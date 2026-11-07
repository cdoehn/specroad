# MERGE-RESOLUTION-612 — auditierte Auflösung und vollständiger Schritt 17.h

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## MERGE-RESOLUTION-612 — auditierte Auflösung und vollständiger Schritt 17.h

Autorität: SPECROAD-DECISION-1, 2.4.3.1 und aktueller Vertrag 4 mit
clarification_allowed=true, Restbudget 3. Das native Result 4a12a2 ist
sauber an HEAD 5f0044d603ae5d7eb4f8bbe9293b1b66015920fc gebunden;
SHA-256 735c6efa948bbedf0cacb8ff3f49d387b9759726396850d798a4734c1ac28ff6.
17.g.C ist committed, sein Apply-Gate hat 7856 Tests bestanden; 714/900.
Keine menschliche Freigabe oder lokale Verhaltensprüfung wird behauptet.

Lücke: SR-REQ-0372/0375 verlangen explizite auditierte Einzelauflösung,
aber bisher fehlen Ereignisformat, Kettenbindung, Akteur-/Zeitübergabe,
Zielwertprojektion und die explizite Quellzuführung an die echte CLI.
Geprüft: 10.15.1–4, 12.27, K.3, 17.h–17.l sowie native Quellen,
Feld-/Collections-, Schutz-, Actor-/UTC- und CLI-Verträge.

Alternativen: Konfliktzeilen überschreiben; freie ungebundene Audittexte;
oder ursprünglichen Katalog unverändert bewahren und genau ein gebundenes
Ereignis ergänzen. Gewählt ist das letzte, weil es reversibel, überprüfbar
und ohne Projektwrites bleibt. Quellen könnten implizit aus gespeicherten
Pfaden geöffnet werden; gewählt ist stattdessen ein ausdrücklich ausgewählter
Deskriptor mit vorhandenen SourceRequests und tatsächlichen Herkunftsbelegen.
Die vollständige erwartete Plan-SHA bindet die Auswahl des Aufrufers.
Akteur und UTC sind explizite Auditdaten, keine erfundene Authentifizierung.
Explizites JSON ist ein Kandidat im bestehenden kanonischen Wertebereich;
die uneingeschränkte vollständige semantische Zielprüfung bleibt in 17.j.
Schutzkonflikte bleiben unauflösbar; keine Lösch- oder Publikationsbefugnis.

Zuerst werden 10.15.5, die nachstehenden Abnahmen und alle aktiven Katalog-
Hashbindungen fortgeschrieben. Diese Stage lässt 17.h.W/R/C offen. Danach
folgt derselbe vollständige fachliche Schritt als echte W/R/C-Stände, jeweils
mit eigenem Apply-Gate. W umfasst native API, echte CLI, alle Take-Arten und
explizite Werte; R härtet manipulierte Ketten, Quellenwechsel, ungültige Werte
und sichere Eingaben; C trennt passive Werte von quellengebundener Auflösung.
17.i–17.l bleiben offen. Kein Scope, Sicherheitsgate, Kompatibilitätsvertrag,
Review, Budget oder historischer Nachweis wird geändert.
