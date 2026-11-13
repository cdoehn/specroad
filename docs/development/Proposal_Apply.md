# Proposal Apply

Der implementierte Eingang `proposal apply <Proposal-ID oder verwaltete Datei>`
benötigt `--expected-revision`, `--actor-type` und `--actor-id`. Für tatsächliche
AI-/CI-Schreibaufrufe ist außerdem `--request-id` erforderlich. Der eingebettete
Host registriert `PublicationAuthority` und `RestoreServices.proposal_inputs`;
die CLI erfindet weder Herkunftsnachweise noch menschliche Freigaben.

`--dry-run` prüft dieselbe aktuelle Genehmigung, den unveränderten inneren Plan
und dessen vollständiges Ziel ohne Journal oder Projektänderung. Das Resultat
`proposal-apply-v1` enthält die gebundenen IDs, Auditdaten und bei tatsächlicher
Veröffentlichung den nativen Abschlussbeleg. Ergebnisfelder sind keine neue
Schreibberechtigung.

Die Umsetzung verwendet den gemeinsamen Writer. Fachresultate behalten die
Metadaten des genehmigten Plans; der äußere Apply-Akteur und dessen Zeit gehören
zur zusätzlichen `approved -> applied`-Kontrollrevision. Ressourcen-Normalisierung
behält ihren bytegebundenen Vertrag. Bereits bestätigte gleiche Request-IDs
lesen den vorhandenen Abschluss, ohne erneut anzuwenden. Bei Abbruch bleiben
Journal und Vorherbilder für die ausdrücklich autorisierte native Recovery
bestehen; ein normaler Retry umgeht die Sperre nicht.

Die normative Schnittstelle steht in Spezifikation 10.3.6. Die Apply-Abnahme
läuft je W/R/C-Stufe über N=3 plus ungefilterte Pflichtauswahl. Dev erstellt
Verhaltenstests, führt aber nur statische Prüfungen und reine Collection aus.
