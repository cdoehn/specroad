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
