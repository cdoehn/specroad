# Den Implementierungsplan pflegen

Diese Regeln gelten für diesen Verzeichnisbaum. [Projektregeln](../../DEVELOPMENT.md)
und [Dokumentationsregeln](../AGENTS.md) zusätzlich beachten.

## Ablage

| Inhalt | Maßgebliche Stelle |
|---|---|
| Gesamtfortschritt und nächste Position | YAML-Block in `SpecRoad_Implementierungsplan.md` |
| Meilensteinziel, Schrittumfang, W/R/C-Abnahmen und Checklisten | `milestones/M01.md` bis `M20.md` |
| Ergänzende fachliche Details und bereits vorhandene Schrittbelege | Verlinkte Datei in `supplements/` |
| Neue begründete Detailentscheidungen | Eigene Datei in `decisions/`, mit Datum und stabiler Kennung |
| Neue Ausführungs-/Korrekturberichte | Eigene kurze Datei in `history/`, mit Datum und Bundle-/Commitkennung |
| Requirement-, Verifikations-, Szenario- und Regressionszuordnung | `matrices/` |
| Gemeinsame Phasenregeln | `../development/Plan_Arbeitsregeln.md` |
| Wortgleiche C-Invarianten und C-Regressionsabnahme | `rules/C_Abnahme.md` |
| Übernommene Audit-Nacharbeiten | `audit/Audit_Nacharbeiten.md` |

Der Planeinstieg ist ein Wegweiser und die zentrale Fortschrittsstelle. Keine
neuen Ausführungsprotokolle, vollständigen Logs oder langen Entscheidungsbelege
davor oder danach anhängen. Die vorhandenen Sprungmarken bleiben als Verweise
auf die Detaildateien erhalten; neue fachliche Inhalte nicht in diese Verweise
kopieren. Der gemeinsame Plan umfasst alle ausdrücklich verlinkten Detaildateien.

## Änderung eines Schritts

1. Den Fortschrittsblock und die betroffene Detailposition samt verlinkter
   Ergänzungen lesen. Ergänzungen enthalten auch verbindliche Abnahmen; ihre
   Auslagerung erklärt sie nicht pauschal für historisch oder optional.
2. Kennung, Reihenfolge, Voraussetzungen, exakte Commitnachricht, Scope und
   Abnahmen erhalten, sofern der Auftrag deren Änderung nicht ausdrücklich
   abdeckt. OFF-PLAN-Arbeit verändert weder die 900 Produktpositionen noch
   stillschweigend ihre Erledigt-Kennzeichen.
3. Neue fachliche Klärung nur im zulässigen Entscheidungsrahmen vornehmen.
   Begründung, normative Spezifikation, aktive Katalogbindungen und betroffene
   Abnahmen zusammen aktualisieren. Allgemeine Regeln ausschließlich zentral
   pflegen; ein Link nimmt ihre vollständige Geltung in den Schritt auf.
   Ein optionaler Klärungspräfix aktualisiert weiterhin die Spezifikation und
   den Planeinstieg tatsächlich, dort mit einem kurzen Verweis auf die neue
   Entscheidung. Die vollständigen Abnahmen stehen in den betroffenen
   Detaildateien. Kein unveränderter Marker und keine erneute Detailkopie im
   Einstieg. Die geschlossenen zulässigen Planpfade beschreibt das
   [Apply-Verfahren](../development/Apply_Commit_Plans.md).
4. Einen neuen Nachweis direkt aus dem betroffenen Schritt und aus
   `history/README.md` verlinken. Alte Belege bleiben unverändert;
   spätere Korrekturen nennen konkret, welche Aussage sie ersetzen.
5. Fortschrittsblock und betroffene Checklisten im erfolgreichen Commit
   konsistent halten. Nicht nur aufgrund eines angekündigten Bundles oder
   eines einzelnen grünen Präfixes weitere Positionen abschließen.

## Verlustfreie Ablageänderungen

Vor einer weiteren Aufteilung die Vorherbytes sichern und die Zuordnung jedes
verschobenen Abschnitts festhalten. Einmalig statisch prüfen: alle Inhalte
wiederauffindbar, IDs und Abnahmen vollständig, Relativepfade angepasst, keine
abweichende zweite Fortschrittsquelle. Bei wortgleichen Wiederholungen ist
Zentralisierung mit ausdrücklich gleichbleibender Geltung zulässig. Individuelle
Abweichungen bleiben beim Schritt. Der Nachweis gehört zur Bundlevorbereitung;
er wird nicht als Dokumentationstest oder vorgetäuschter Produktnachweis geführt.
