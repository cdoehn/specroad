# Gebundener negativer Relationsreview

`specroad.authoring.negative_reviews.record_negative_relation_review` nimmt
einen menschlichen negativen Review über das native Transaktionsprotokoll auf.
Der Host liefert ein vollständiges `TargetModel`, authentische Historie,
Identitätsinventur, explizite Quellrevision oder Quellhash und die vorhandene
Publikationsautorität. Der Dienst ermittelt die Rücknahmen aus den tatsächlich
gebundenen komponierten Profilregeln einschließlich der Core-Pflichtrelationen.

Der eine `relation_review_record`-Plan enthält den neuen unveränderbaren
Review und die vollständige berechnete Rücknahmemenge. Betroffene zuvor
`approved` Requirements werden im selben nativen Write auf `proposed`
gesetzt und genau einmal revisioniert. Fachinhalt, Relationsinhalt und
Erzeugungsaudit bleiben erhalten. Quelle und Ziel des Reviews binden den
vor der Rücknahme beobachteten Stand. Die Kontexthashes bleiben nach der
Lifecycle-Änderung gleich; der negative Review bleibt aktuell.

Direkte Planung, gespeicherter Plan und Publikationsprüfungen rechnen denselben
Endstand erneut. Fehlende, zusätzliche oder veränderte Rücknahmen werden
abgewiesen. `extension:review-withdrawal` ist für negative Reviewpläne
verpflichtend. Nur frisch aus dem vollständig gebundenen Endstand berechnete
`current_review_rejected`-Befunde sind Ergebnisse des Reviewvorgangs. Andere
Gates, strukturelle Fehler, unzulässige Akteure, stale Basis und verweigerte
Publikationsautorität bleiben blockierend. Ein gleich benannter fremder
Gate-Befund erzeugt keine Ausnahme.

Das Target-Assessment hält die vollständigen gelieferten Reviewstatus-Befunde
unter `review_assessment` fest. Negative Urteile bleiben `SRV027`/`error`;
das erfolgreiche Write-Gate behauptet kein bestandenes fachliches Review.
Der native API-Rückgabewert beschreibt den aufgenommenen negativen Review mit
`assessment_status=failed`, `assessment_scope=recorded_review_outcome_only`,
den gebundenen Rücknahmen, Planhash, Zielmodellwurzel und dem nativen Receipt.
Ein identischer Request verwendet dieses Receipt und dieselbe Review-ID erneut.

Der erste Dienst unterstützt berechnete Requirement-Rücknahmen sowie Reviews
ohne Rücknahme bei ansonsten unterstützten Subjekten. Andere notwendige
Standardartefakt-Rücknahmen und zusätzliche nicht unterstützte Lifecycle-
oder Approval-Subjekte werden abgewiesen. Der bisherige positive Dienst bleibt
in seinem bisherigen Umfang verfügbar. Vollständige Wiederbestätigung,
CLI-/Envelope-Integration, weitergehende Approval-Dienste und die spezifischen
Crash-/Recovery-Abnahmen aus R-35 bis R-39 bleiben weitere Arbeit in 7.i.
Die API authentifiziert keinen menschlichen Reviewer und entdeckt keine
vollständige Projekthistorie. Es gibt keine generische Fehlerausnahme und keine
automatische neue Artefaktfreigabe.
