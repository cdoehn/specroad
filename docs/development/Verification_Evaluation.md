# Bewertungsdescriptor und Prüfeingangsbytes

Der erste Core-Stand aus `12.k.W` stellt `VerificationEvaluation`,
`prepare_verification_evaluation` und `assess_evaluation_inputs` unter
`specroad.verification` bereit. Er bindet einen ausdrücklich bezeichneten
Produktstand. Er berechnet noch kein `verification_result` und verändert
weder Projektdateien noch Evidence oder Baselines.

`prepare_verification_evaluation` erhält ausschließlich explizite Argumente:
`evaluation_id`, `subject_id`, `inputs`, `configuration`, `required_runs`,
`created_at` und `created_by`. `inputs` ist ein Dictionary aus portablen relativen
logischen Pfaden und unveränderlichen `bytes`. Pfade werden mit der nativen
Pfadprüfung validiert, niemals geöffnet. Die übergebenen Bytes bleiben unverändert;
leere Dateien sind zulässig, eine leere Eingangsmenge ist es nicht.
`configuration` ist eine native `EffectiveConfiguration` oder ausdrücklich `None`.
Identität, Uhrzeit, Konfiguration oder Git-Zustand werden nicht ermittelt.

Der Descriptor hat die Schemaidentität `verification-evaluation-v1`,
`format_version="1.0.0"` und genau die acht Felder aus Spezifikation 10.5.1.
`evaluation_id` verwendet `EVAL-` mit einem vollständigen `random128-v1`-Token.
Die erste Implementierung unterstützt ausschließlich `replacements=[]`;
nichtleere Ablösungsentscheidungen werden zurückgewiesen. Die fachliche
Laufablösung ist der späteren Planstelle `12.n` zugeordnet.

Das Eingangsmanifest enthält je Datei `logical_path`, `size` und SHA-256 der
tatsächlichen Bytes, sortiert nach UTF-8-Bytes des logischen Pfads.
`state_sha256` bindet ausschließlich die RFC-8785-Bytes von
`{subject_id, manifest}`. Auditdaten, Auswahl, Evaluations-ID und Konfiguration
gehören zum Descriptorhash, nicht zusätzlich zum Produktstandhash.
`required_runs` wird nach dem vollständigen Pflichtschlüssel sortiert, `null`
steht vor einer Test-ID. Lauf-ID-Mengen werden nach UTF-8-Bytes sortiert;
doppelte Schlüssel, Lauf-IDs und logische Pfade werden abgewiesen.

`VerificationEvaluation(raw)` prüft UTF-8-JSON, den geschlossenen Vertrag,
Pfadbindungen und den Selbsthash. `source_bytes` erhält die Originalbytes,
`canonical_bytes` liefert den vollständig normalisierten Descriptor und
`sha256` dessen `evaluation_sha256`. `data` liefert abgetrennte Werte.
Fehler sind `VerificationEvaluationError` mit `SRV175` und Exit-Code 3.
Ein gültiger Selbsthash belegt allein noch keine verfügbaren Prüfeingänge.

`assess_evaluation_inputs(descriptor, inputs=...)` vergleicht die explizit
gelieferten Bytes mit jeder Manifestzeile. Die Beobachtung unterscheidet
`matched_inputs`, `missing_inputs`, `mismatched_inputs` und `unexpected_inputs`.
`input_bytes_verified` ist nur bei vollständiger exakter Übereinstimmung wahr.
Fehlende Bytes werden nicht durch Hostdateien oder einen angenommenen aktuellen
Build ersetzt. Der Befund ist ein unveränderlicher Wert mit abgetrennter
`data`-Kopie und eigenem Hash; boolesche Verwendung ist untersagt.

Die Byteprüfung bestätigt weder Herkunft oder Ausführung eines externen Tests
noch die fachliche Vollständigkeit der vom Aufrufer gewählten Eingänge.
`input_roles_verified`, `project_required_checks_complete`,
`full_verification_evaluated`, `write_authorized` und `approval_granted` bleiben
falsch. Die Prüfung, dass keine Evidence, eigenen Ausgaben oder Descriptoren
als fachliche Inputs gewählt wurden, sowie die Behandlung fehlender
Bewertungsauswahl werden in `12.k.R` ergänzt. Pflichtmengenbildung, bekannte
Evaluationsidentitäten im Projekt, Nachweisauswahl, Laufablösung, Aggregation,
CLI- und Readiness-Anbindung gehören weiterhin zu den folgenden Planstellen.
Die zugehörigen Anforderungsnachweise bleiben `partial`.
