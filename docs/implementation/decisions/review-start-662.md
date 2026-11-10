# REVIEW-START-662 — persistierte native Kontrollbelege

10. November 2026 · 18.h · delegiert gemäß SPECROAD-DECISION-1 / 2.4.3.1.
Quelle: erfolgreiches sauberes Result mit SHA-256
`723d0494210ebfe473b94bbf2f319e10a963abc4ef26086006964b9ff594b247`.

10.3/11.10 verlangen die atomare Kontrollfolge; 10.7.10 benötigt Original-
Prüfergebnisbytes. Der bisherige generische control_history-Eintrag und das
Vierfelderereignis definierten deren persistierte aktuelle Darstellung nicht.
Der Legacy-0.1-Vertrag ist kein Schreibvertrag für 0.2.

Betrachtet wurden nur Hashes (verlieren Originalbelege), ein neues separates
Belegarchiv (zusätzliche Ablage-/Transaktionsverträge) und inline gebundene
Originalberichte. Gewählt wird die letzte, kleinste additive Variante:
versionierte Kontrollzeilen, bestehende native Berichtstypen und ein enger
Operationsteil. Originalkontexte und explizite Herkunftsverifier bleiben nach
10.7.10 zwingend; weder Containerhash noch grüner Check ersetzen Human-Reviews.

Normativ: [Spec 10.3.3](../../specification/SpecRoad_Spezifikation.md#1033-persistierte-review-start-belege--review-start-662).
Abnahmen: [18.h](../milestones/M18.md#step-18-h) und [Ergänzung](../supplements/18-h.md).
Die Klärung bleibt innerhalb des bestätigten Schritts (SR-REQ-0426, 0431, 0646).
Keine neue Produktposition, Architektur-/Sicherheitsgrenze oder automatische
Fachfreigabe. Altbytes werden nicht migriert; der neue Marker und optionale
Operationsteil erlauben getrenntes Lesen. Eine spätere formatierte Änderung
muss die Originalberichte erhalten. Kein externer Fakt wird angenommen.

Dieser Dokumentzustand ist der optionale OFF-PLAN-Präfix vor 18.h.W/R/C.
Umsetzung und tatsächliche Apply-Nachweise sind hier noch offen. Keine Tests
in Dev; jede Stage erhält ihr eigenes N=3-plus-Pflichtauswahl-Gate.
