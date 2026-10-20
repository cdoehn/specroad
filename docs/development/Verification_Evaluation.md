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
falsch. Diese reine Bytebeobachtung ersetzt das nachfolgende Rollengate nicht.
Weitere Scope-Profile der Pflichtmengenbildung, bekannte
Evaluationsidentitäten im Projekt, Nachweisauswahl, Laufablösung, Aggregation,
CLI- und Readiness-Anbindung gehören weiterhin zu den folgenden Planstellen.
Die zugehörigen Anforderungsnachweise bleiben `partial`.

`12.k.R` ergänzt `assess_evaluation_binding(evaluation, inputs=..., input_roles=...)`
als Gate vor der späteren Pflichtmengen- und Nachweisauswahl. `evaluation` ist
ein `VerificationEvaluation` oder ausdrücklich `None`; `inputs` enthält die
verfügbaren tatsächlichen Prüfbytes oder `None`. Der Prüfer beziehungsweise
Importer liefert unabhängig vom Descriptor ein Rolleninventar `input_roles`:
Dictionary aus logischen Pfaden und den Rollen `input`, `evidence`, `result`,
`evaluation` oder `selection_metadata`. Zu `result` gehören Ausgaben derselben
Prüfung; der eigene Descriptor und seine Auswahlmetadaten erhalten ihre jeweils
ausgeschlossene Rolle. Pfade teilen den logischen Namensraum des Manifests.
Fehlen diese Informationen, ist `None` zulässig und die Bindung unvollständig.

Jede Manifestzeile muss als `input` deklariert sein. Eine ausgeschlossene Rolle
im Manifest ist `SRV175`, Code 3, auch wenn deren Bytes gerade nicht verfügbar
sind. Sie wird nicht stillschweigend herausgefiltert und der Produktstandhash
wird nicht repariert. Jeder zusätzlich deklarierte `input` muss ebenfalls im
Manifest stehen; ein Descriptor darf bekannte Prüfeingänge nicht weglassen.
Ausgeschlossene Dateien außerhalb des Manifests benötigen keine Bytes und
verändern den Produktstandhash nicht. Das Rolleninventar wird getrennt sortiert
und im Beobachtungsbericht gehasht, ohne neue Descriptorfelder oder Selbstbezug.

Die Rollen sind eine ausdrückliche Angabe des aufrufenden Prüfers, keine aus
Dateiendung, Inhalt oder einem fremden Rechner abgeleitete Herkunftsaussage.
Der Core authentifiziert diese Angaben nicht (`input_roles_authenticated=false`).
Der Integrator muss das vollständige tatsächliche Rolleninventar liefern;
ein Angreifer mit Kontrolle über dessen Angaben kann damit keinen externen
Testlauf nachweisen. Dateinamen wie `evidence.json` allein bestimmen keine Rolle.

Ohne Descriptor lautet `verification_result="incomplete"`, mit Diagnose
`SRV176`, Schwere `warning`, Grund `evaluation_required`; der Descriptor wird
auch nicht aus vorhandenen Dateien erraten. Fehlende Rollen, ausgelassene
Inputs, unbekannte Bytes, fehlende Dateien, Byteabweichungen und zusätzliche
Inputs werden ebenfalls als `incomplete` mit getrennten maschinenlesbaren
Gründen berichtet. Strukturell falsche Argumente bleiben Fehler mit Code 3.

Bei vollständiger Eingangsbindung lautet nur `binding_status="ready"`;
`verification_result` bleibt `null`. Das ist keine bestandene Verifikation,
sondern die Voraussetzung für nachfolgende fachliche Prüfungen. Weder eine
Pflichtmenge noch ein Lauf oder Release wurde damit bewertet. Die unveränderliche
`EvaluationBindingAssessment` hält abgetrennte Daten und einen eigenen Hash;
boolesche Verwendung bleibt untersagt. Der Core liest keine Dateien und startet
keine Prozesse, Tests oder implizite Suche nach einem aktuellen Build.

`12.l.W` stellt `resolve_required_checks(model, configuration_id=...)` und
`assess_required_check_coverage(model, evaluation, configuration_id=...)` bereit.
`model` ist ein `TargetModel` mit dem vollständig übergebenen Projektbestand;
die Konfiguration wird ausdrücklich per ID aus dessen Originalbytes aufgelöst
oder mit `None` abgewählt. Dieses erste Profil unterstützt ausschließlich den
ganzen übergebenen Projektbestand, keine Teil-, Query- oder Release-Selectoren.

Die Pflichtmenge entsteht vor dem Descriptorvergleich aus Requirement-,
Capability- und Task-Subjects, ihren gültigen `verified_by`-Zielen und sämtlichen
Slots. Direkt gebundene Tests tragen den impliziten `overall`-Contract bei.
Die Schlüssel und Dimensionen werden deterministisch sortiert; Eingangsbytes,
Scope, effektive Konfiguration und Contract-Auflösungen sind separat gebunden.
Unverknüpfte Contracts oder im Descriptor erwähnte IDs erweitern die Menge nicht.

Fehlende Schlüssel ergeben `incomplete`/SRV176, zusätzliche Schlüssel
SRV175/Code 3. Fehlende Contracts, eine abweichende Konfigurationsbindung oder
ungeklärte Anwendbarkeit bleiben ebenfalls unvollständig. Ohne Konfiguration
bleiben bedingte Subjects und Abhängigkeiten potenziell erforderlich. Ein durch
die gewählte Konfiguration ausgeschlossenes Pflichtziel ist SRV141/Code 3;
seine Slots verschwinden nicht stillschweigend. Planstatus und Waiver werden
hier nicht zur Reduktion der Pflichtmenge benutzt; ihre Priorität gehört zur
späteren vollständigen Aggregation.

`coverage_status="ready"` bedeutet ausschließlich vollständige Schlüssel- und
Konfigurationsabdeckung im übergebenen Modell; `verification_result` bleibt
`null`. Das vorherige Byte-/Rollengate bleibt zusätzlich erforderlich.
`RequiredChecksResolution` und `RequiredCheckAssessment` sind unveränderliche
Beobachtungen ohne booleschen Erfolgswert. Sie bestätigen weder einen live
vollständigen Projektbestand noch bestandene Läufe oder eine Releasefreigabe.
Nachweisauswahl, Laufablösung, Aggregation und CLI-Anbindung bleiben offen.
