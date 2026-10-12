# Vergleichsquellen (Bibliotheksstand 8.j.W)

`ComparisonSourceSnapshot(root, kind='local')` erfasst ein lokales Projekt nach
dem bestehenden Project-Read-Preflight. `kind='git', reference='<Ref>'` liest
ausschließlich den fest gebundenen Commit über `GitObjectSource`; dessen
[Git-Grenzen](Git_Object_Source.md) gelten unverändert. Optional verlangt
`expected_project_id` eine bestimmte Projektidentität. Baseline und Bundle
sind benannte, ausdrücklich noch nicht verfügbare Quellenarten.

Der unveränderliche Snapshot enthält eine geprüfte `ProjectConfiguration`,
`ComparisonInputs` und eigene Rohbytes aller konfigurierten normativen
JSON-Ressourcen. Artefaktfelder, gemeinsame Hülle, Relationen und ID-/Pfadzuordnung
werden geprüft. Lokale Inventur und gelesene Bytes werden erneut beobachtet;
ein beobachteter Wechsel führt zum Fehler. Das ist kein atomarer Dateisystem-
Snapshot und keine Sperre gegen nicht kooperierende Schreiber. Nach erfolgreicher
Erfassung bleiben die eigenen Werte auch bei späteren Quelldateiänderungen stabil.

`binding` beschreibt Quellenart, Root, gegebenenfalls Commit, Projekt-ID und
Rohbyte-Hashes. `sha256` bindet diese Provenienz; er ist kein SpecRoad-Modellwurzelhash.
Unterschiedliche Pfade oder JSON-Formatierungen dürfen unterschiedliche Bindungen
bei gleichem fachlichem Vergleich erzeugen. Rückgaben besitzen keine Schreib- oder
Freigabeberechtigung.

`compare_sources(before, after, timing_bounds=...)` verlangt zwei solche Snapshots
desselben Projekts. Für Projektkonfiguration und Artefakte liefert es exakt den
bestehenden `compare_semantic`-Vertrag, einschließlich seiner begrenzten Reichweite.
Profile, Regeln und Mappings sind bislang nur als Rohbytes erfasst und unter
`uncompared_resources` ausgewiesen. Abweichende Ressourcen dieses Bereichs führen
zu `comparison_resource_semantics_unavailable`; gleiche Bytes bestätigen keine
inhaltliche Gültigkeit dieser Ressourcen. Vollständige Modellgleichheit wird nicht
behauptet. Fremde Identitäten, inkompatible Schemata und ungültige oder unsichere
Quellen ergeben explizite Fehler. Es gibt keine Ergänzung aus anderen Quellen.

Diff-CLI und Work-Fortsetzung, semantische Profil-/Regel-/Mappingvergleiche,
Konfigurationsauswertung, vollständige Modellvalidierung, Evidence-Currentness,
skalierbare Erfassung und Plattformabnahme bleiben offen. Die konkreten Baseline-
und Bundleadapter folgen gemäß Implementierungsplan erst in M10 und M15.
