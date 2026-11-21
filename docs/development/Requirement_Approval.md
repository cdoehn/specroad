# Explizite Requirement-Freigabe

`specroad.authoring.requirement_approval.approve_requirement` veröffentlicht
nur einen isolierten menschlichen Übergang `in_review` → `approved` über den
vorhandenen nativen Writer. Der Host liefert vollständiges `TargetModel`,
`ApprovalContext`, `HumanRequirementReview`, `ReviewVerifier`, einen expliziten
`ApprovalPrerequisiteProvider` sowie die normale Publikationsautorität.

Zuerst erzeugt `bind_requirement_approval(operation, context, review)` aus dem
normalisierten Transition-Intent die drei Referenzfelder nach
[§ 9.6.4](../specification/SpecRoad_Spezifikation.md). Für einen Retry bleiben diese Operation,
Request-ID und der ursprüngliche fachliche Intent erhalten. Die Referenzen
sind passive Daten; die Bibliothek entdeckt weder Identität noch Zugangsdaten
und liest keine ausführbaren Dienste aus dem Projekt. Direkte und gespeicherte
Pläne verwenden dieselbe reine Kandidatenbildung und denselben Zielcheck.

Neue Writes prüfen sämtliche Originalbytes, Profil, Konfiguration, Quellzustand,
Planvorbedingungen, Reviewbindung, acht menschliche Kriterien und sieben
aktuelle semantische Pflichtdienste. Zusätzlich berechnet der native Dienst
die verpflichtenden Relationsstatus neu. Fremde Gates, unzulässige Akteure und
fehlende Publikationsautorität bleiben blockierend. Die Dienste werden auch
unter dem Writer-Lock erneut ausgewertet. Erfolgreiche aktuelle Beurteilung
ist keine Erlaubnis, fremde Änderungen oder beschädigte Roots zu überschreiben.

Der Fachinhalt bleibt gleich, Revision und Änderungsaudit steigen genau einmal.
Eine neue Relationsbestätigung allein belässt das herabgestufte Requirement auf
`proposed`; zuerst erfolgt der separate Übergang nach `in_review`, dann die
neue Freigabe. Historische Reviews und Receipts bleiben unverändert. Ein bereits
bestätigter identischer Request liefert sein ursprüngliches Receipt ohne neue
Freigabeprüfung und ohne zweiten Write. Ein neuer Request benötigt aktuelle
Dienste. Das ist keine allgemeine CLI-Freigabe und keine menschliche Abnahme
des SpecRoad-Produkts; die automatisierten Tests verwenden synthetische Akteure.
