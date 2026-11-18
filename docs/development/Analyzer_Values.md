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
