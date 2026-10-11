# Gebundener negativer Relationsreview

`specroad.authoring.negative_reviews.record_negative_relation_review` nimmt
einen menschlichen negativen Review über das native Transaktionsprotokoll auf.
`record_coupled_relation_review` unterstützt zusätzlich eine neue bestätigende
Entscheidung auf derselben Bindung. Der negative Einstieg bleibt ausdrücklich
auf `rejected` begrenzt; der ältere Erstbestätigungsdienst behält seinen Umfang.
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

Die gebundenen Gates liegen gemeinsam in
`specroad.changes._review_outcome_gates`. Das Modul berechnet denselben
gekoppelten Endstand erneut, erhält die Grenzen der unterstützten Subjekte und
prüft verbleibende Freigabeinvarianten. Nur die dort selbst ermittelten negativen
Reviewbefunde werden als fachliche Ergebnisdaten behandelt. Kandidatenbildung
und vollständige negative Reviewbewertung bleiben in `changes.negative_reviews`;
die bisherigen Gate-Einstiege werden dort weiterhin bereitgestellt.

Das Target-Assessment negativer Pläne hält die gelieferten Reviewstatus-Befunde
unter `review_assessment` fest. Negative Urteile bleiben `SRV027`/`error`;
das erfolgreiche Write-Gate behauptet kein bestandenes fachliches Review.
Der native API-Rückgabewert beschreibt den aufgenommenen negativen Review mit
`assessment_status=failed`, `assessment_scope=recorded_review_outcome_only`,
den gebundenen Rücknahmen, Planhash, Zielmodellwurzel und dem nativen Receipt.
Ein identischer Request verwendet dieses Receipt und dieselbe Review-ID erneut.

Eine spätere Bestätigung erzeugt einen neuen unveränderbaren Review mit
monotonem Zeitstempel und setzt den Relationsstatus auf `current`. Das zuvor
herabgestufte Requirement bleibt bytegleich `proposed` mit derselben Revision.
Auch ein weiterer negativer Review erzeugt keine zweite Herabstufung. Ein
negativer Review einer optionalen Relation erhält ein unverändertes Requirement
auf `approved` nur, wenn alle weiterhin verpflichtenden Relationen `current`
sind und ihre Mindestmengen erfüllt bleiben. Unveränderte Standardartefakte in
anderen Reifegraden erhalten keine neue Revision. Das beweist keine neue
Artefaktfreigabe und ersetzt keine Authentifizierung des gelieferten Vorstands.

Die Ausnahme für gebundene negative Reviewbefunde gilt auch bei anderen
bereits gespeicherten negativen Entscheidungen. Das Ergebnis des Aufrufs
bewertet ausdrücklich nur den neu aufgenommenen Review. Die separate
schreibfreie `relation_review_diagnostics`-Abfrage bewertet alle gelieferten
Relationsstatus und liefert bei fortbestehender Ablehnung weiterhin Code 1.
Ein vollständiges CLI-Envelope ist damit noch nicht implementiert.

Die R-Nachweise unterbrechen einen echten Kindprozess nach der ersten oder
letzten normativen Dateiersetzung sowie nach den Commit-Receipts. Die vorhandene
Recovery übernimmt den verwaisten Lock anhand seiner exakten Bindung und
stellt den vollständigen alten Zustand oder den vollständigen neuen Zustand
her. Nach vollständiger Veröffentlichung verwendet derselbe Request dasselbe
Receipt, denselben Review und dieselbe einmalige Rücknahme. Die Recovery- und
Receipt-Implementierung wird dafür nicht verändert.

Der Dienst unterstützt berechnete Requirement-Rücknahmen einschließlich
profilabhängiger inverser Sichten und unveränderte Standardzustände. Andere
notwendige Standardartefakt-Rücknahmen und nicht unterstützte Spezialartefakte
oder Approval-Subjekte werden abgewiesen. CLI-/Envelope-Integration, vollständige
Projekt-/Historienbeschaffung, allgemeine Approval-Dienste und die abschließende
explizite Freigabefolge aus R-36 bleiben offen. Die nativen Teilnachweise aus
R-35 bis R-39 ersetzen keine vollständige CLI-/Produkt- oder Plattformabnahme.
Die API authentifiziert keinen menschlichen Reviewer und entdeckt keine
vollständige Projekthistorie. Es gibt keine generische Fehlerausnahme und keine
automatische neue Artefaktfreigabe.
