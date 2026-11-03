# Explizite Requirementmappings im Migrationsplan

`specroad.migration.planning.migration_inputs` nimmt je Requirement eine
explizite Zuordnung mit `artifact_id`, `source_sha256`, `language`,
`normative_force` und `statement` entgegen. Der Hash bezeichnet die volle
JCS-Fassung der tatsächlichen aktuellen 0.1-Quelle. Sprache, eine der vier
Verbindlichkeiten und der vollständige Zieltext sind Autorenentscheidungen.

Mit `requirement_default_language='en'` kann der Aufrufer ausdrücklich eine
gemeinsame Sprache für Zeilen ohne `language` liefern. Eine vorhandene Sprache
bleibt erhalten; ein vorhandener ungültiger Wert wird nicht ersetzt. Ohne
diesen Parameter gibt es keinen Ersatz aus Konfiguration, Locale oder Text.
Die anderen Pflichtwerte bleiben je Zeile erforderlich. Eingabedaten werden
nicht verändert. Die Normalisierung schreibt jede resultierende Sprache in
die einzelne Mappingzeile; der gespeicherte `migration-inputs-v1`-Vertrag
erhält keine zusätzlichen Felder.

`plan_migration` bindet diese Entscheidungen und getrennt davon die nötigen
Schemaergänzungen in den gemeinsamen Change Plan. Fehlende Mappings erzeugen
Blocker ohne Teilziel; ungültige Angaben oder veränderte Quellen sind Fehler.
Neue Inhalte erhalten keine alte Freigabe. Historische immutable Originale
und ihre Hashes bleiben erhalten. Ein fertiger Plan ist weder menschliches
Review noch Schreibberechtigung, Backup- oder aktuelle Verificationsevidenz.
Normative Grundlage: Spezifikation 12.20.2, Q.0.2 und S.7.
