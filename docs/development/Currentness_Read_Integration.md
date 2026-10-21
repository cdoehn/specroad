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

Modellgebundene Coverage-, Verification- und Traceability-Ansichten können auch
einen expliziten nativen Verification-Scope verwenden. Die Coverage benennt genau
diesen Scope. Die vollständige Modell-/Nachweismenge und alle Codeverweise bleiben
gebunden, auch außerhalb des ausgewerteten Scopes. Validation und die Adapter für
ganze Artefaktinventare (Impact, Trace, Diff, Query) weisen solche partiellen
Eingänge weiterhin ab; sie deuten sie nicht in eine Ganzprojektbewertung um.

Für geteilte Arbeit stellt `currentness.work_input` kanonische, versionierte
JSON-Bytes bereit. Sie enthalten die vollständige Evaluation einschließlich
Run-Auswahl, Ersetzungen, Scope, Konfiguration und Bewertungszeit sowie Bindungen
an alle Artefaktbytes und alle nativen Codebeobachtungen. Auch historische,
supersedierte und nicht ausgewählte Evidence bleibt Teil der Eingabe. Queryfilter,
Offset und Limit verkleinern diese Nachweismenge nicht.

Diese Bytes sind die semantische Komponente eines Work-Snapshots, kein kompletter
Projekt- oder Codeexport. Der Work-Host muss zusätzlich die ursprünglichen
Modell-, Konfigurations-, Profil-/Ressourcen-, Produktinput- und Codequellenbytes
im gebundenen nativen Work-Store erhalten. Hashes ersetzen fehlende Bytes nicht.
Der Store und sein initiales Manifest benötigen eine unabhängige Vertrauensbasis;
gespeicherte Pfade oder ein Hash aus demselben unbekannten Dokument reichen nicht.

`resume_currentness_read_input(model, raw, expected_sha256=..., inputs=...,
input_roles=..., code_states=..., scope_bindings=..., waiver_reviews=...,
waiver_verifier=...)` prüft diese Bindung und berechnet Verification, Coverage und
gemeinsame Aktualität erneut. Das Modell und die Produktinputs stammen aus dem
geprüften Snapshot. Die Codezustände werden vom Host erneut mit
`assess_code_reference` an der erhaltenen nativen Datei- oder Git-Quelle bewertet.
Native Scopebindungen und erforderliche Waiver-Vertrauensnachweise werden separat
übergeben. Ein gespeichertes Erfolgsresultat, Dictionary oder Callback ersetzt
keine dieser Fähigkeiten. Veränderte Codebeobachtungen oder andere rekonstruierte
Ergebnisse erzeugen `VerificationReadBindingConflict` (Exit 6); fehlende oder
ungültige native Eingaben bleiben Fehler. Die Funktion liest keinen gespeicherten
Locator und verwendet keine implizite Uhr.

`QueryWork(..., currentness=value)` übernimmt dieselbe native Verification und
behält über alle echten Sortier-/Ausgabeeinheiten `currentness_input`,
`currentness_observation` und `evaluation_input` vollständig bei. Die Ausgabe-Seite
bleibt zum synchronen Queryresultat identisch; auch eine leere Seite bewahrt den
vollständigen Eingang. Ein zusätzlich übergebener Verification-Eingang muss exakt
übereinstimmen. `QueryWork` bleibt ein prozesslokaler Cursor und erhält dadurch
keine Berechtigung zum Öffnen gespeicherter Spoolpfade. Die dauerhafte Ablage und
Einheitenfortsetzung organisiert weiterhin der native Work-Host.

Release Readiness bleibt Meilenstein 13 vorbehalten. Diese Python-Eingänge
registrieren keine neuen CLI-Optionen und erteilen keine Releasefreigabe.
