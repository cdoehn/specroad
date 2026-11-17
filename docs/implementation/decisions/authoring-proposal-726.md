# AUTHORING-PROPOSAL-726

SPECROAD-DECISION-1, Vertrag 4: eine optionale Detailklärung vor 18.l.W/R/C
und 18.m.W/R/C. Die normative Lücke betrifft die äußere Entwurfsoperation,
nicht die schon festgelegte Fachsemantik, Scopegrenze oder Reviewpflicht.

Alternativen: generisches create für Kontrollrecords freigeben würde die
bestehende Sicherheitsgrenze aufweichen; Fachänderungen zusammen mit dem
Entwurf schreiben würde die Proposal-Semantik verletzen. Gewählt ist eine
isolierte geschlossene proposal_create-Operation im bestehenden nativen
Schreibprotokoll. Sie ist additiv, lokal rücknehmbar und verwendet vorhandene
Originale, Qualifikation, Sperren und Receipts. Keine neue Rechtequelle.

Abnahmen: gleiche fachliche Zielbytes und Defaults für direkte Planung und
Umleitung; nur Entwurfsdatei wird veröffentlicht; AI ohne Umleitung Code 7;
fehlende Request-ID, falsche Metadaten, Kollisionen, stale Basis, verbotene
Scopeziele, verweigerte Hostautorität und geänderte Retry-Bindung bleiben
blockierend. Agenten beschreiben ausschließlich registrierte Handler und
native Schemata; erforderliche menschliche Entscheidung bleibt sichtbar.

Keine Produktabnahme oder Testausführung durch diese Entscheidung. Aktive
Katalogbindungen folgen Spezifikation 0.2.92; bestehende Historie unverändert.
