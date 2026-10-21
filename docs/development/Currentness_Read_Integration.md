# Gebundene Aktualitätsbeobachtung

`prepare_currentness_read_input(model, verification, code_states=...)` verbindet
einen nativen `VerificationReadInput` mit den nativen `CodeReferenceState`-Werten
für genau alle `code_ref`-Datensätze des übergebenen `TargetModel`. Die Codewerte
werden zuvor mit `assess_code_reference` an einer ausdrücklich gewählten sicheren
Datei- oder Git-Quelle berechnet. Ein fehlendes Ziel ist ein `missing`-Wert; ein
weggelassener Codeverweis ist eine unvollständige Eingabe und wird abgewiesen.

Der unveränderliche `CurrentnessReadInput` bindet die ursprünglichen Modellbytes,
Artefaktbytes, Projektkonfiguration, Evaluation, Scope und Bewertungszeit. Seine
`observation` enthält SHA-256 und die maschinenlesbaren Daten: Codezustände,
Coverage und getrennte Relationsreview-Gruppen mit betroffenen Endpunkten. Fehlende
Evaluation bleibt ausdrücklich unvollständig. `verification` gibt denselben
nativen Eingang für die vorhandenen Query-Filter, Sortierung und Paging zurück.

Die Python-Schnittstellen `validate_model`, `impact_artifact`, `trace_artifact`,
`assess_verification_coverage` und `resolve_builtin_view` für `traceability` und
`verification` nehmen den Eingang über `currentness=` an. Validation benötigt
dazu `ValidationResources` mit der tatsächlichen Projektkonfiguration; sie
registriert die Beobachtung im Report und dessen Eingabebindung. Die Beobachtung
ersetzt keine fehlenden Lifecycle-, Review-, Evidence- oder anderen Gate-Dienste.
Impact und Trace vergleichen die vollständigen gelesenen Artefakte mit dem
Eingang; bei konfigurierter Auswertung ist dieselbe `configuration_id` anzugeben.
Ihre bisherigen Graphprojektionen bleiben getrennt von der zusätzlichen
Beobachtung. Die ursprünglichen Aufrufe ohne diesen Eingang bleiben unverändert.

`compare_semantic`, `compare_sources` und `diff_project` nehmen unabhängig
gebundene Seiten über `before_currentness=` und `after_currentness=` an. Beide
sind erforderlich. Ein geänderter Codezustand ist auch bei unveränderten
Artefaktbytes als `currentness_changed` sichtbar. Beide vollständigen
Beobachtungen bleiben erhalten; `missing` und `stale` werden nicht zusammengelegt.
Die registrierten Result-Schemata erlauben die optionalen Beobachtungsfelder.

Dies sind beobachtete, übergebene Daten. Wiederverwendung liest weder Code noch
Produktinputs erneut und behauptet deshalb keine aktuelle Dateisystem- oder
atomare Snapshot-Prüfung. Neue Beobachtungen müssen aus den neu gewählten Quellen
berechnet werden. Die vorhandenen Live-Graphadapter behalten ihre eigenen
Artefakt-/Konfigurations-Rechecks. Kein Consumer schreibt berechnete Resultate in
Subjects, führt Quellcode aus oder erteilt Schreibrecht, Approval oder Readiness.

12.t.W unterstützt die explizite vollständige Modellbeobachtung. Partielle
Verification-Scopes werden hier abgewiesen. Die Fortsetzung geteilter Arbeit
einschließlich vollständiger Evaluations- und Nachweismenge folgt in 12.t.R;
Release Readiness bleibt Meilenstein 13 vorbehalten. Neue CLI-Optionen werden
durch diesen Python-Eingang nicht registriert.
