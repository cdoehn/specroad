# Passive Analyzerwerte

`specroad.analyzers.AnalyzerDescriptor` liest vollständige UTF-8-JSON-Bytes
nach [T.2/T.2.1](../specification/SpecRoad_Spezifikation.md). `data` liefert
jeweils eine eigene Datenkopie, `canonical_bytes` die JCS-Bytes und `sha256`
deren vollständigen Hash. Unbekannte Felder/Vertragsversionen und ungültige
Werte werden als `AnalyzerError` abgewiesen. Namespaced Erweiterungen bleiben Daten.

`builtin_descriptor()` liefert die festgelegte Beschreibung von
`specroad.py3langid` 1.0.0. `classify_descriptor()` unterscheidet die exakten
bekannten Bytes von externen Metadaten. Der Sprachworker ist an dieser
Planposition noch nicht implementiert; `execution_supported` ist daher falsch.
Descriptoren sind keine Pluginregistrierung und lösen keine Abhängigkeiten auf.

`require_binding(analyzer_id=..., adapter_version=..., descriptor_sha256=...)`
prüft alle drei unabhängigen Koordinaten. `select_capabilities(...)` verlangt
eine nichtleere, sortierte und dublettenfreie Teilmenge der Deklaration.

`AnalyzerRequest` liest geschlossene Requests nach T.3/T.3.1 ohne Projektzugriff.
`analyzer_binding(descriptor, capabilities)` erzeugt einen gebundenen Eintrag.
`create_request(analyzers=..., subjects=..., context=..., settings=...,
extensions=..., analysis_id=...)` übernimmt nur explizite vollständige Daten.
`prepare_analysis_id()` kann die Kennung vor der Datenauswahl einmal zuteilen;
derselbe typisierte Wert wird dann weitergegeben. Ohne Kennung erfolgt diese
Zuteilung einmal vor der Snapshotbildung. Lesen erzeugt keine neue Kennung.

`AnalysisRequestId` und der bestehende `NormativeRequestId` (Alias
`WriteRequestId`) haben getrennte Typen und Namensräume. Eine String-ID wird
nicht automatisch zur Schreibidempotenz benutzt. Der Snapshothash enthält
exakt contract_version, analyzers, subjects, context, settings und extensions;
die Analyse-ID selbst ist eine unabhängige Bindung. Betriebsfelder gehören
nicht in den Request. Fehler in importierten Daten haben Code 3, fehlerhafte
explizite ID-Optionen Code 2, fehlende Entropie Code 5. Projektselektion,
Dateiexport, Ergebnisprüfung und CLI erhalten eigene spätere Abnahmen.

`request.require_binding(request_id=..., snapshot_sha256=...)` unterscheidet
ID- und Snapshotkonflikt mit Code 6. Diese reine Wertprüfung ist weder ein
Ergebnisnachweis noch ein Work-Resume und schreibt keine Receipts.


## Vollständige native Subjectauswahl

`request_from_project(root, analyzers=..., settings=..., subject_ids=None,
field_pointers=("/statement",), configuration_id=None, context=(),
extensions=None, analysis_id=None)` erstellt den vollständigen Request nach
T.3.2. Die Auswahl erfolgt ohne Pagination über den nativen aktuellen Scope.
Explizite IDs und Pointer wählen separate Originalwerte. Context enthält nur
bereits gelesene explizite Ressourcen mit resource_id, value und sha256;
ein String darin wird niemals als Pfad oder Anweisung aufgelöst. Der Aufruf
publiziert keine Dateien und startet keinen Analyzer. Der Defaulttext-Pointer
eignet sich für Requirements; andere Typen brauchen passende Pointer und
die bereits vorgeschriebenen ursprünglichen Sprach-/Metadaten.

Vor dem Lesen werden veränderliche Aufrufereingaben übernommen. Native
Fehler bleiben unterschieden: Modell 3, Umgebung 5, Konflikt 6, Sicherheit 7;
fehlerhafte Auswahloptionen 2. Die abschließende Prüfung ist eine native
Quellbeobachtung, keine Transaktion gegen nichtkooperierende Schreiber.

## Passive Ergebnisberichte

`subject_result(subject, status=..., payload=..., findings=None)` übernimmt
die vollständige Originalbindung. `create_report(request, analyzer_id=...,
engine=..., subjects=..., run_status=..., findings=(), operational=None,
extensions=None, run_id=None)` bindet alle Ergebnisse. Subjects sind nach
subject_key sortiert; der Konstruktor repariert keine fehlenden Ergebnisse.
Die genauen geschlossenen Datenformen stehen ausschließlich in T.4.1.

`AnalyzerReport(raw_bytes, request)` validiert gespeicherte Beobachtungen.
`data`, `observation`, `provenance` und `operational` liefern eigene Kopien.
`result_sha256` bindet die T.4-Fachprojektion, `full_file_sha256` hingegen die
unveränderten ursprünglichen Bytes, `canonical_bytes` die JCS-Darstellung.
Unbekannte externe Payloads bleiben Daten, keine Fachfreigabe oder Evidence.

`require_provenance(analyzer=..., engine=...)` und
`require_transport_hash(expected_sha256)` prüfen unabhängige erwartete
Bindungen und melden Konflikte mit Code 6. Übereinstimmende Hashes beweisen
keine Authentizität. Dateioperationen und Work-/CLI-Verknüpfung bleiben den vorgesehenen
Bedienadaptern vorbehalten; die folgende Package-API prüft bereits gelesene Bytes.


## Reportpackages

`ReportPackage(raw_bytes, request=None)` prüft den vollständigen eingebetteten
Request und sämtliche Reports. Ein optionaler expliziter Request muss genau
übereinstimmen. `create_package(request, reports)` übernimmt gebundene
AnalyzerReport-Werte. Mehrere unterschiedliche Läufe bleiben erhalten;
mindestens ein Bericht je gewähltem Analyzer und eindeutige Run-IDs sind Pflicht.
`data`, `request` und `reports` liefern eigene bzw. unveränderliche Werte;
`original_bytes` und `full_file_sha256` beziehen sich auf die ursprüngliche
äußere Datei, `canonical_bytes` auf das JCS-Objekt. Eingebettete Reports sind
Objekte, keine angeblichen separaten Originaldateien. Es wird nichts publiziert.

`verify_worker_result(raw, request, analyzer=..., engine=...)` validiert die
explizit erwartete Antwort mit denselben Reportregeln. Es ist ein reiner
Protokollvalidator, kein Workerstart oder Nachweis einer installierten Engine.

`require_transport_hash(expected)` prüft zusätzlich die äußeren Originalbytes.
`read_unbound_report(raw)` prüft intrinsische Struktur und Hashes, wenn kein
Request vorhanden ist. Das Ergebnis ist keine Bestätigung der vollständigen
Requestbindung oder Aktualität. Der Package-/Workerpfad braucht weiterhin
seinen vollständigen Request.

## Lesende Auswertung

`evaluate_reports([raw_bytes, ...], request=None, project=None,
current_inputs=None, configuration_id=None)` erhält jede ausgewählte Datei
und jeden Bericht. `current_inputs` ist ein ausdrücklich unabhängig ermitteltes
Objekt mit `analyzers`, `settings`, `context` (explizite Ressourcen) und
`extensions`. Der Aufrufer darf dafür keine unbelegte Aktualität des alten
Requests unterstellen. Fehlen Arbeitsstand oder aktuelle Eingaben, bleibt die
Aktualität unavailable; intrinsische Berichtfehler bleiben invalid.

Die Ausgabe `AnalysisEvaluation` enthält eigene `data`/`canonical_bytes` sowie
unveränderte `originals`. Pro Bericht bleiben currentness, Grund, nativer
Fehlercode, vollständige Originalbeobachtung und geänderte Bindungen sichtbar.
`all_reports_current` ist ausschließlich eine Aktualitätszusammenfassung,
kein Sprach-, Qualitäts-, Gate- oder Evidence-Erfolg. Unterschiede werden
explizit strukturell verglichen; alle Varianten und Provenienzen bleiben erhalten.

`result.reevaluate(project=..., current_inputs=..., configuration_id=...)`
erzeugt eine neue getrennte Sicht über exakt dieselben Originalbytes und den
ursprünglich expliziten Request. Weder die erste Auswertung noch Projektdateien
werden dadurch verändert. Die neue Sicht muss erneut native Aktualität prüfen.


## Analyzer-CLI

`analyzer list` und `analyzer describe ID` beschreiben den tatsächlich
installierten Umfang ohne Modellinitialisierung. `analyzer request --analyzer
specroad.py3langid` bildet den vollständigen nativen Request; ohne --output
bleibt er im JSON-result. `--analysis-id` korreliert ausschließlich Analysen.
`analyzer run` akzeptiert diese Auswahl oder einen datentragenden --request;
noch nicht implementierte Worker liefern vollständige unavailable-Berichte
mit Code 5, keinen fingierten Erfolg und keinen Checkpoint.

`analyzer import FILE`, `show FILE` und `evaluate FILE...` verwenden dieselben
Request-/Reportvalidatoren. Ein expliziter --request bindet Standalone-Reports.
`--inputs FILE` liefert die unabhängigen aktuellen analyzers/settings/context/
extensions-Werte nach T.5.2; ohne Arbeitsstand oder Inputs bleibt Aktualität
unavailable. Evaluate prüft sämtliche Positionsdateien und kann daraus keinen
aktuellen Erfolg behaupten. Import/show dürfen integre alte Beobachtungen
anzeigen. Originale und lokale Auswertung bleiben getrennt.

Ein relatives --output liegt unter generated_path/analysis im gewählten
Projekt; Eltern müssen bereits vorhanden sein. Externe Ausgaben wählen
--output-root DIR oder einen absoluten Dateipfad. Es entstehen weder
Modellwrites noch Receipts. Die atomare Veröffentlichung überschreibt nichts;
bytegleiche Ziele sind No-op, unterschiedliche Bytes Konflikt 6. Import
behält die vollständigen Originalbytes. Keine Originaldatei wird zur lokalen
Aktualitätsanzeige geändert. Die nachfolgenden Work-/Workerstufen bleiben offen.


`--inputs FILE` bei list/describe und Requestbildung lässt gültige fremde
Descriptoren bereits als Dateischnittstelle zu. Die Datei enthält genau die
vier T.8.1-Koordinaten; die gewählte Analyzer-ID-Menge muss exakt passen.
Unbekannte Erweiterungen bleiben Daten. Kein execution_mode, Dependency-
String, Subjecttext oder Projektwert kann einen Worker registrieren.

## Sprachpolicy und beobachtete Engine

`language_policy.materialize_policy` materialisiert die T.8-Aktionen und prüft
sie vor dem Modellzugriff. `assess_language(request, decisions, registry=...)`
bindet vorhandene Scoreentscheidungen an Originalsubjects und den ausdrücklichen
Sprachregisterstand; `.report` ist der vollständige T.4-Bericht, `.data` die
separate Policybewertung mit execution_complete, all_languages_confirmed,
findings_failed, gate_passed und exit_code. `fail_on` ist error oder warning.
Ignore löscht keine Beobachtung. Nichtentscheidungen und coarse sind keine
volle Sprachbestätigung. Backendfehler bleiben Code 5 vor fachlichem Code 1.

`worker.analyze_language(request, fail_on='error')` ruft den vollständigen
Adapter ausdrücklich auf, mit einer seriell gehaltenen Modellinstanz. Er
schreibt keine Projektdateien. Der bisherige generische Dispatcher und die
dauerhaften Work-Subjectübergänge erhalten ihre gesonderte Integration und
Abnahme in 19.w; ihre Verfügbarkeitsauskunft wird hier nicht vorweggenommen.

`engine_identity(engine)` liefert die geschlossene Engineprojektion und
separat ihre tatsächlich beobachteten Runtime-/NumPy-Inventare. Unbekannte
Fakten bleiben null mit Grund; `.reproducible` verlangt alle gebundenen Fakten.
Inventare enthalten Hashes und numerische Eigenschaften, keine lokalen Pfade,
Zugangsdaten oder Projektkonfigurationen. Der Bericht bindet die Inventare unter
`extensions.specroad.engine_inventory` an seinen deterministischen Resulthash.
Gleiche Engine und Eingaben ergeben gleiche Beobachtungsprojektion; Run-ID und
Betriebsdaten bleiben davon getrennt. Dies ist keine Korpus-/Releaseabnahme.

`bind_engine(request, engine).require_current(request, engine)` prüft die
JSON-only Request-/Enginebindung für die spätere Fortsetzungsintegration.
Eine unbekannte Identität ergibt 5, eine geänderte bekannte Bindung 6. Modelle
werden niemals in diesem Wert serialisiert. Laufzeitübergreifende gleiche
Labels und Entscheidungen sind keine Zusage bytegleicher Scores oder Reports.
