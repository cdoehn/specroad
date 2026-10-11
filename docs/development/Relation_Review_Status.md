# Relationsreview-Status aus einem gelieferten Modell

`specroad.graph.review_status.RelationReviewStatuses` nimmt eine Sequenz von
`SourceRelations` entgegen und liefert für jede gespeicherte Relation eine
unveränderliche Statusbeobachtung. Die vollständigen Feldverträge, eindeutige
Artefakt-/Relationsidentitäten und der gemeinsame Projektpräfix werden geprüft.
`for_relation(source_id, relation_id)` wählt eine konkrete Beobachtung;
`as_fields()` und `data` liefern abgetrennte JSON-kompatible Werte.

Intern bleiben Inventur und Historienaufbereitung in `review_status`.
`_review_status_selection` berechnet die reinen Statuswerte;
`_review_status_diagnostics` bildet sie auf typisierte Befunde ab.
Die öffentlichen Imports und JSON-Verträge bleiben unverändert.

`specroad.authoring.review_status.relation_review_status(model, source_id,
relation_id)` übernimmt dafür einen eigenen Snapshot des gelieferten
`TargetModel`. Die Abfrage lädt keine weiteren Dateien, erzeugt keine IDs,
schreibt keinen Status in die Relation und erteilt keine Freigabe.

`RelationReviewStatuses.diagnostics` liefert typisierte Core-Diagnosen:
`SRV025`/`warning` für `unreviewed`, `SRV026`/`warning` für `suspect` und
`SRV027`/`error` für `invalid`. Nur `current_review_rejected` erhält die
Kategorie `review_outcome`; strukturelle Fehler bleiben `relation_structure`.
Pfad und JSON-Pointer beziehen sich auf die tatsächliche Speicherposition der
Relation, auch wenn Statusbeobachtungen anders sortiert werden.

`relation_review_diagnostics(model, fail_on="error", strict=False)` beurteilt
diese Diagnosen mit der vorhandenen Fail-Policy. Strenge Warnschwellen ändern
die ursprüngliche Schwere nicht; aktuelle Ablehnungen bleiben Fehler. Das
Ergebnis enthält Statusbeobachtungen, Diagnosen und deren expliziten
`validation_scope`. `checks_complete` bezeichnet ausschließlich die gelieferten
Relationsbeobachtungen. Es entsteht keine allgemeine Projektfreigabe oder
Write-Ausnahme; unvollständige Eingaben werden nicht als Gesamtinventur bestätigt.

Die Auswahl folgt Anhang J: Strukturelle Ungültigkeit hat Vorrang. Bei gültiger
Struktur müssen Relationsinhaltshash und beide Kontexthashes passen. Unter den
passenden Reviews entscheidet der neueste Zeitpunkt, bei Gleichheit die
lexikografisch höchste Review-ID. `confirmed` ergibt `current`, `rejected`
`invalid` mit `current_review_rejected`. Ohne passende Reviews ergibt vorhandene
Historie `suspect`, sonst `unreviewed`. Zeitbruchteile werden exakt verglichen;
ältere passive Datensätze ohne `reviewed_at` verwenden `created_at`.

Vollständige Endpunkthashes und Revisionen bleiben Auditdaten. Ihre Abweichung
ist kein zusätzlicher Aktualitätsschlüssel. Die Berechnung authentifiziert keine
Historie und beweist keine vollständige oder frische Projektinventur. Ihr
`validation_scope` lautet `supplied_relation_review_status_only`;
`approval_granted` bleibt `false`. Sie ersetzt keine allgemeine Validierung,
kein Approval-Gate und keinen nativen Review-Aufnahmeplan. Die bestehende
Writer-Verbindung und registrierte CLI bleiben gesonderte Integrationsschritte.
