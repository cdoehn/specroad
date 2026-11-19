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
