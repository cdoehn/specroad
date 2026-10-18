# Eingebaute Dokumentansichten

`specroad.documents.resolve_builtin_view(model, view_name)` erzeugt einen eigenen
`BuiltinViewData`-Wert aus einem `TargetModel`-Snapshot. `.data` liefert abgelöste
JSON-Daten, `.sha256` bindet die kanonische Projektion und `.source_files` erhält
die gelieferten Originalbytes. Es wird kein zusätzliches `view`- oder
`document`-Artefakt angelegt. Die Schnittstellen sind reine Python-APIs; sie
lesen keine Pfade und schreiben keine Ausgabedateien.

`specification` verlangt das einzige aktive Primärdokument. Die vorhandene
Rollenprüfung und Include-Komposition bestimmen seine tatsächliche Identität,
Records und geordneten Occurrences einschließlich wiederholter Includes.
Ungültige Dokumentfelder, fehlende oder mehrfache Primärdokumente und native
Kompositionsfehler bleiben Fehler. Ein Vollprojekt wechselt niemals implizit
in den typbasierten Fallback.

`traceability` liefert für jedes gespeicherte Requirement eine Zeile mit
`origin`, `implementation`, `verification`, `evidence` und `release`.
Jede Kategorie enthält Original-IDs und IDs tatsächlich gespeicherter
Relationen. Herkunft folgt `addresses`/`refines`/`derived_from`, Umsetzung
`allocated_to`/`implemented_by`, Verifikation `verified_by` und Evidence
`produces`. Evidence-Subjects werden zusätzlich als unveränderte Felder mit
Quell-ID und JSON Pointer gebunden, ohne synthetische Relation.
Release-Zuordnung folgt `scheduled_for`/`part_of` vom Requirement und seinen
Umsetzungszielen zu Releases/Milestones. Zyklen terminieren ohne duplizierte IDs.
Die Records und Relationstabelle erhalten Originalwerte, Revisionen, relative
Pfade sowie Quell-, Record- und Relationshashes. Freitext und Statusfelder
erzeugen keine abgeleiteten Beziehungen.

Gespeicherte Evidence ist noch kein aktueller Verifikationserfolg.
`verification_result` und `release_readiness` bleiben `null`; die jeweiligen
Auswertungsflags bleiben `false`. `verification` und `roadmap` verweigern mit
`builtin_view_provider_required`, solange die tatsächlichen Berechnungen aus
M12/M13 fehlen. Keine Ansicht behauptet vollständige Validierung, Freigabe,
Schreibberechtigung oder aktuelle Dateisystemvollständigkeit.

`resolve_type_fallback(documents, source_kind=..., scope_descriptor=...,
boundary_references=...)` nimmt explizite `ModelDocument`-Originalbytes an.
Der Aufrufer muss `partial` oder `legacy` wählen; Dateiname, Dateirechte und
fehlende Dokumente erzeugen keine implizite Herkunftsannahme. Ein mitgeliefertes
aktives Primärdokument verweigert den Fallback. Die tatsächlichen Records sind
nach Typ und ID gruppiert, ohne erfundene Primärspezifikation oder Zielrecords.

Bei `partial` gelten die vorhandenen 0.2-Feldschemas, kanonischen Artefaktpfade
und die native Prüfung exakter schwacher Boundary References. Ein partieller
Dokument-/Release-Descriptor und dessen tatsächlicher Root sind erforderlich.
Fehlende starke Ziele bleiben Fehler. Boundary-Hashes werden als Deklarationen
erhalten, nicht als unabhängig geprüfte Originalnachweise ausgegeben.

Bei `legacy` prüft der Adapter nur ein 0.1.0-Envelope aus bekannter Typ-/Legacy-ID,
Titel und Revision. Weder `id_scheme` noch andere aktuelle Pflichtfelder werden
in den Record eingefügt. Original-Schema, Relationsform und JSON-Bytes bleiben
unverändert. Das ist kein versionierter vollständiger Legacy-Leser und keine
Migration. Deren Provenienz-/Semantikprüfungen folgen erst in M16; die Prüfung
und das Laden echter Partial-Bundles folgen in M15. Die Projektion weist deshalb
`source_context_verified=false`, `origin_hashes_verified=false`,
`legacy_semantics_verified=false` und `model_root_sha256=null` aus. Ihr
`input_sha256` bindet stattdessen exakt gelieferte Bytes und Deklarationen.

`render_builtin_view` und `render_type_fallback` liefern ausschließlich
Markdown-/HTML-Bytes über die vorhandenen sicheren Renderer. Die primäre
Spezifikation verwendet `render_document`; Traceability verwendet die
bestehende Requirement-Präsentation. Passive Felder sind Daten, keine Templates.
Die Tests prüfen Quellbindungen, Fachwerte, native Fehler und fehlende
Seiteneffekte; Layout, Markup und Beschriftungen sind keine Testoracles.
