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
Bis `12.m` unterstützt der Descriptor ausschließlich `replacements=[]`.
Seit `12.n.W` akzeptiert er die vollständigen menschlichen Entscheidungen
aus dem Abschnitt „Menschlich erklärte Laufablösung“ weiter unten.

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

`12.l.R` ergänzt bei beiden Pflichtmengen-APIs die optionalen Argumente
`scope_descriptor` und `scope_bindings`. Beide werden gemeinsam übergeben:
ein nativer `ScopeDescriptor` und `ClosureBindings` mit vollständigem
Quellinventar sowie ausdrücklichen Ressourcenverwendungs-, Review- und bei
Bedarf Anhangsbeobachtungen. Ohne beide Argumente bleibt das W-Profil des
ganzen übergebenen Projekts erhalten. Die gesonderte `configuration_id` muss
exakt mit dem Scope übereinstimmen; der Bewertungsdescriptor wählt sie nicht.

Quellbytes und Ressourcenbestand werden gegen das aktuelle `TargetModel`
geprüft, danach die nativen Seed- und Closure-Regeln erneut ausgeführt.
Eine fehlende Providerbeobachtung wird nicht als leere Abhängigkeit ergänzt.
Diese expliziten Beobachtungen müssen vom zuständigen Ressourcen-/Reviewdienst
stammen; ihre Herkunft wird durch einen Hash nicht authentifiziert. Der Bericht
bindet die konkrete Closure zusätzlich und behauptet keinen vollständigen
Live-Projektbestand oder normativen Scope-Hash allein aus einem Selectorhash.

Die nativen Projekt-, Spezifikations-, Release-, Dokument-, expliziten und
konfigurierten Scopes sowie unabhängige Query-Scopes werden unterstützt.
Query-Seiten werden aus den tatsächlichen Records neu berechnet. Eine im
Query-Selector eingebettete Bewertung wird abgewiesen; Filter oder Sortierung
nach noch nicht berechnetem `verification_result` bleiben ohne entsprechenden
Provider ebenfalls unzulässig. `required_runs` liefert weder Seeds noch
Closure-Mitglieder. Starke Abhängigkeiten bleiben auch bei `partial` Pflicht;
schwache Beziehungen folgen der gewählten Grenzpolicy. SRV140 und SRV141 der
nativen Zulässigkeitsprüfung bleiben erhalten.

Bei zusätzlichen Prüfschlüsseln ist `RequiredCheckCoverageError` weiterhin
ein `VerificationEvaluationError` mit SRV175/Code 3. Seine abgetrennten
`details` und `diagnostic()` nennen sowohl `missing_checks` als auch
`unexpected_keys`, gebunden an `required_set_sha256`. Zusätzliche Schlüssel
bleiben Fehler, auch wenn gleichzeitig andere fehlen. Reine Fehlmengen bleiben
`incomplete`/SRV176 und haben eine leere Liste `unexpected_keys`. Der Vergleich
berücksichtigt alle vier Schlüsselfelder; eine gleichnamige Prüfung eines
anderen Subjects oder Contracts ersetzt keine Pflichtprüfung.

## Beobachtete und erwartete Laufkandidaten (12.m.W)

`select_verification_runs(model, evaluation, configuration_id=..., ...)` bildet
zuerst die unabhängige Pflichtmenge. Optional gelten dieselben ausdrücklich
übergebenen `scope_descriptor`-/`scope_bindings`-Eingänge wie bei der
Pflichtmengenauflösung. Ein Descriptor kann die Scope-Keys nicht verändern.
Fehlende oder unvollständige Abdeckung bleibt `selection_status="incomplete"`;
fremde Schlüssel behalten den vorhandenen SRV175-Vertrag.

Für jeden Pflichtschlüssel vereinigt der Aufruf sämtliche erwarteten Lauf-IDs
mit allen passenden beobachteten Läufen aus dem vollständigen übergebenen
Modellbestand. Auch Evidence außerhalb der Subject-Closure kann deren Keys
bezeugen; die Evidence erweitert dadurch weder Seeds noch Pflichtmenge.
Produktbezeichner, Produktstandhash, Check und Test müssen exakt passen. Subject,
Contract und gegebenenfalls Test müssen ausdrücklich in den Evidence-Subjects
stehen. Eine fehlende Erwartung bleibt als Lauf mit leerer Evidence-Liste sichtbar.
Jeder Lauf enthält alle passenden Nachweise samt unverändertem Ergebnis,
Subject-Bindungen, Run-Kontext, Vollhash und Quellbytehash. Weder spätere
Erzeugungszeit noch Importreihenfolge oder Evidence-ID ersetzt einen Fehlschlag.

`bound` verlangt denselben Konfigurationshash. `independent` verlangt eine
explizite Policy des aktuellen Verification Contracts; bei fremdem
Konfigurationshash muss auch dessen aufgezeichneter Kontexthash aktuell sein.
Ein direkt gebundener Test erhält keine erfundene Unabhängigkeitspolicy.
Fehlende Konfigurationsangaben werden nicht ergänzt. Widersprüchliche
Produktbindungen derselben Lauf-ID werden mit dem bestehenden nativen
`evidence_run_identity_conflict` abgewiesen. Beobachtete Lauf-IDs müssen bereits
namensraumqualifiziert sein; ein Producer wird nicht aus anderen Feldern geraten.

Das Ergebnis ist ein eigener `VerificationRunSelection`-Wert mit abgetrennter
`data`-Kopie und Hash; boolesche Verwendung ist unzulässig. Die gesamte gelieferte
Evidence-Inventur bleibt gebunden, nicht ausgewählte IDs werden separat erhalten.
Die detaillierte Disposition `historical_other_state`, `unbound`, `missing` und
`stale` gehört zu 12.m.R. Der W-Stand erhält auch kontextveraltete Beobachtungen des
passenden Stands, bewertet deren Subject-Aktualität aber noch nicht abschließend.

`selection_status="selected"` bedeutet ausschließlich erfolgte Kandidatenauswahl.
Der Aufruf prüft keine realen Produktdateien, authentifiziert keinen Producer,
führt keinen Testcode aus und liefert kein abschließendes `verification_result`.
Prüfeingangs-/Rollengate, vollständige Freshness, Laufablösung, priorisierte
Aggregation und Readiness bleiben getrennt. Bestehende Evidence wird nie verändert.


## Laufdispositionen und Kontextaktualität (12.m.R)

`assess_verification_runs` ergänzt die bestehende Kandidatenauswahl um einen
reinen, schreibfreien Bericht `verification-run-assessment-v1`. Die API nimmt
denselben `TargetModel`, Descriptor, explizite Konfiguration und optional
unabhängige Scope-Bindungen wie `select_verification_runs` entgegen. Sie baut
beide aus ihren Originalbytes auf; die unveränderte Auswahl und deren Hash
bleiben im Bericht enthalten.

Alle Evidence-IDs werden mit Quell-/Artefakthash und Disposition aufgeführt:
`historical_other_state` für fremde Produkt-/Standbindung, `unbound` bei
fehlendem Laufkontext, `candidate` für mindestens einen passenden
Pflichtschlüssel, ansonsten `unselected` mit Ausschlussgründen je Prüfung.
Ohne vollständige Pflichtmengen-/Descriptorbindung werden keine Läufe oder
fehlenden Erwartungen beurteilt; sonstige Records bleiben `not_evaluated`.
Historische Fehlschläge werden dadurch nicht zu Fehlschlägen des neuen Stands.

Je Kandidat werden die vorhandenen Appendix-L-Kontextvergleiche für Subject,
Contract und gegebenenfalls Test ausgeführt. Alle Ergebnisse bleiben erhalten:
`current`, `stale` oder bei nicht definiertem Kontextvertrag `incomplete`.
Capability/Task erhalten keine erfundene Hashprojektion; ihre direkten
Testkandidaten bleiben mit `subject_context_unsupported` sichtbar. Reine
Audit-/Workflowänderungen entwerten keinen definierten Kontext. Eine
Konfigurationsausnahme verlangt weiterhin den expliziten aktuellen Contract.

Erwartete Läufe ohne passenden Kandidaten haben `presence=missing` und eine
SRV176-Diagnose mit `reason=required_run_missing` samt vollständigem Schlüssel
und Lauf-ID. Ein vorhandener stale Kandidat ist dagegen `present`; aktuelle,
stale und ungeklärte IDs bleiben getrennt aufgelistet. Importzeit und
lexikografische Evidence-ID wählen keinen Gewinner. Native Laufkonflikte und
ungültige Bindungen bleiben Fehler. Alte Evidencebytes werden nie geändert.

Der Bericht aggregiert keine Rohresultate, wendet keine Laufablösung an und
liefert kein `verification_result`. Er verifiziert weder Produktinputs noch
den Bestand auf dem Dateisystem und gewährt weder Readiness noch Schreibrechte.


## Interne Auswahlstruktur (12.m.C)

Die öffentlichen Funktionen behalten ihre nativen Eingabe-, Scope-, Fehler-
und Berichtverträge. Die Kandidatenregeln liegen in `_run_candidates` und
arbeiten pro Pflichtschlüssel ausschließlich auf einem privaten kanonischen
JSON-Bytesnapshot. Contractauflösung und Fehlerreihenfolge bleiben beim
öffentlichen Adapter. `_run_dispositions` erhält die eingefrorene Auswahl
sowie ein Tupel der ursprünglichen Dokumentpfade und Bytes. Beide Funktionen
liefern eigene Ergebniswerte; sie entdecken keine Dateien und starten weder
Prüfprozesse noch Laufablösungen. Die bisherigen W-/R-Verhaltenstests werden
unverändert für die Strukturänderung verwendet.
# Menschlich erklärte Laufablösung (12.n.W)

`prepare_verification_evaluation(..., replacements=...)` und der native
Descriptor akzeptieren vollständige Entscheidungen aus §10.5.3. Ohne diese
optionale Angabe bleibt die bisherige leere Auswahl erhalten. Jede Entscheidung
bindet Pflichtschlüssel, alten Lauf, Evidence-Set-Hash, Ersatzläufe, Grund,
UTC-Zeitpunkt und ausdrücklich deklarierten menschlichen Akteur. Der Parser
normalisiert die Reihenfolge und weist doppelte Entscheidungen, Zyklen oder
unzulässige Akteure mit SRV175 zurück (Code 3 beziehungsweise 7).

`assess_run_replacements(model, evaluation, configuration_id=...)` baut auf der
unabhängigen Pflichtmenge und dem vollständigen nativen Laufbericht auf. Der
Evidence-Set-Hash umfasst die nach ID geordnete Liste `{id, sha256}` aller
vorhandenen Nachweise des alten Laufs für denselben Pflichtschlüssel und
Produktstand; `sha256` ist jeweils der volle kanonische Artefakthash. Ein
zusätzlicher Nachweis wird auch bei ausgeschlossener Konfiguration nicht aus
dieser Mengenbindung entfernt. Er verlangt eine erneute menschliche Auswahl.

Nur vollständig gebundene Entscheidungen mit vorhandenen, aktuellen und
vollständigen erreichbaren Endläufen werden wirksam. `passed` und `failed`
sind vollständige Endergebnisse; ein Fehlschlag wird nicht zum Erfolg umgedeutet.
Der Bericht trennt `active_run_ids`, `superseded_run_ids` und
`effective_expected_run_ids`, enthält die Originalentscheidung, tatsächliche
Evidence-Menge und Bindungsprobleme sowie den unveränderten Ausgangsbericht.
Unwirksame Bindungen liefern `incomplete` und SRV176 mit
`replacement_binding_changed`. Die API schreibt und startet nichts.

Das ist eine Auswahlstufe, kein aggregiertes Verification-Ergebnis und keine
Readiness-Freigabe. Eingangsbytes/-rollen, vollständiger realer Modellbestand,
projektweite Bewertungs-ID-Historie und tatsächliche menschliche Identität
werden dadurch nicht bestätigt. Frühere Auswahl-/Kontext-APIs bleiben getrennt
und wenden Ablösungen nicht stillschweigend an.

## Vollständige Bindungsdiagnose (12.n.R)

`old_run_observed` zeigt an, ob der alte Lauf tatsächlich zulässige Nachweise
in der unabhängig gebildeten Kandidatenauswahl besitzt. Ein korrekter Hash
eines ausschließlich konfigurationsfremden Evidence-Satzes genügt nicht:
`replaced_run_missing` lässt diese Erwartung offen. Das gilt auch für
Zwischenknoten. `evidence_set_matches` beschreibt weiterhin ausschließlich
die Gleichheit des vollständigen Mengenhashs.

Jede Entscheidung enthält `terminal_runs` mit allen erreichbaren Endläufen,
Präsenz, `current_complete`, allen Bindungsgründen und unveränderten
Ergebniswerten samt Evidence-ID, vollem Artefakthash und Originalbytehash.
Fehlende, stale und nicht aufgelöste Endläufe werden getrennt erklärt;
gleichzeitige Mängel bleiben sichtbar. Gemeinsam erreichte Endläufe werden
je Entscheidung nur einmal aufgeführt. Eine defekte Zwischenbindung
entwertet sämtliche davon abhängigen Ablösungen, ohne unabhängige gültige
Entscheidungen zu verwerfen. Ein staler Zwischenlauf kann selbst wirksam
abgelöst werden; maßgeblich bleiben die vollständigen Bindungen und
aktuellen Endläufe. Ihre fehlgeschlagenen Ergebnisse bleiben `failed`.
Die priorisierte Gesamtaggregation ist weiterhin ein eigener Planschritt.

## Interne Ablösungsstruktur (12.n.C)

`_run_replacement_graph` berechnet ausschließlich erreichbare Endläufe,
transitive Bindungsprobleme und deren unveränderte Ergebnisbeobachtungen.
Es arbeitet auf der bereits validierten Topologie, den nativen Laufkandidaten
und den vollständigen alten Mengenbindungen. Es verändert keine Eingaben und
erzeugt kein aggregiertes Verification-Ergebnis. Die iterative native
Zyklusprüfung bleibt gemeinsam mit der Descriptornormalisierung erhalten.

Der öffentliche Adapter behält Modell-/Descriptorprüfung, Evidence-Set-Hash,
wirksame Erwartungen, aktive beziehungsweise abgelöste Kandidaten und den
kanonischen Bericht. Berichtfelder, Reihenfolge, Hashes, Fehlerverträge und
Schreibfreiheit bleiben gleich; bestehende W-/R-Verhaltenstests bleiben unverändert.

## Priorisierte Ergebnisse je Subject (12.o.W)

`aggregate_verification_results(model, evaluation, configuration_id=...,
inputs=..., input_roles=..., evaluated_at=...)` berechnet einen eigenen
`VerificationResultAggregation`-Wert über den gelieferten Modellbestand.
Die API verbindet die nativen Eingangs-, Pflichtmengen-, Lauf-, Freshness-
und Ablösungsprüfungen. Optionale `scope_descriptor`/`scope_bindings` bleiben
unabhängig von der Bewertungsauswahl. `evaluated_at` ist eine ausdrücklich
gelieferte maschinenlesbare UTC-Zeit; die API liest keine Uhr oder Dateien.

Die Subject-Ergebnisse folgen der Priorität aus §10.5: Konfigurationsausschluss,
wirksamer Waiver, nicht geplante Verifikation, unvollständige Eingangs-/
Auswahlbindung, maßgeblicher aktueller Fehlschlag, laufender Plan, fehlende
Pflichtnachweise, ausschließlich stale Evidence einer Pflichtprüfung und
schließlich vollständig aktuelle bestandene Läufe. Übrige Fälle bleiben
`incomplete`. Ein weiterer bestandener Lauf oder ein anderer fehlender Lauf
verdeckt keinen aktuellen Fehlschlag. Innerhalb desselben Laufs bleiben alle
Beobachtungen erhalten; gemischte aktuelle und stale Nachweise sind ohne
wirksame Ablösung unvollständig. Stale Evidence wird nicht als fehlend behandelt.

`waiver_reviews` ordnet Subject-IDs native `HumanWaiverReview`-Werte zu.
Nur ein ausdrücklich übergebener vertrauenswürdiger `waiver_verifier` kann
deren menschliche Herkunft bestätigen. Der bestehende Waiver-Vertrag prüft
Inhalt, exakten Scope, Konfiguration und Ablauf zum Bewertungszeitpunkt.
Abgelaufene, veränderte, unbestätigte und historische Freitext-Waiver begründen
keine Ausnahme. Ein wirksamer Waiver ergibt `waived`, niemals `passed`.

Der Bericht `verification-result-aggregation-v1` erhält die unveränderten
nativen Eingangs- und Ablösungsberichte mit ihren Hashes, sämtliche aktiven
Laufbeobachtungen sowie Ergebnis und Gründe je Subject. Unvollständige
Ergebnisse führen SRV176-Diagnosen; strukturelle Eingabefehler und nicht
menschliche Ablösungen behalten SRV175 mit Code 3 beziehungsweise 7.
`data` liefert eine abgetrennte Kopie, `sha256` bindet den kanonischen Bericht.
Boolesche Verwendung ist unzulässig. Subject- und Evidencebytes bleiben gleich.

Die Aggregation bestätigt keinen vollständigen realen Dateibestand,
keine projektweite Bewertungs-ID-Historie und keine externe Testausführung.
Diese Grenzen sind als falsche Berichtflags sichtbar. Es gibt weder einen
Gesamt-Pass noch Readiness, Schreibrechte oder eine Freigabe. Die vollständige
gemischte Entscheidungsmatrix und Robustheit folgen in 12.o.R; CLI-/Query-
und Releaseintegration bleiben eigene Planschritte.
