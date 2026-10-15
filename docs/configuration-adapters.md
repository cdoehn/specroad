# Konfigurationsauswahl in Fachadaptern

Eine Auswahl bezeichnet die stabile ID eines tatsächlich geladenen
`configuration`-Artefakts. `resolve_configuration(records, configuration_id)`
löst dessen vollständige Parent-Kette aus den Originalbytes auf. Es gibt keine
implizite erste Variante oder Auswahl nach Anzeigename. Fehlende Auswahl und
eine ausdrücklich ungültige Auswahl sind verschiedene Fälle.

Die vorhandenen Schnittstellen sind `query_project(..., configuration_id=...)`,
`query_records`, `QueryWork`, die Query-CLI mit `--configuration`,
`validate_project_read_only(..., configuration_id=...)` und konfigurierte
`ScopeDescriptor`-Eingaben für `read_artifact_scope_seeds`. Die Query-Auswahl
wertet Anwendbarkeit vor Sortierung und Pagination aus. Ein Query-Scope übernimmt
genau diese tatsächliche Seite; er füllt ausgeschlossene Treffer nicht nach.

`EffectiveConfiguration.binding` enthält ID, Revision und Hash des effektiven
Manifests einschließlich Parent-Kette. `srx_context` liefert ausschließlich die
beiden zulässigen SRX-Felder `configuration_id` und `effective_values`.
`scope_sha256(ProjectConfiguration)` verbindet den effektiven Konfigurationshash
mit der semantischen Projektkonfiguration. Native Query und Validierung geben
ihn als `configuration_scope_sha256` aus; derselbe Wert steht in
`ScopeSeeds.configuration_sha256`. Anzeigeoptionen und reine JSON-Formatierung
sind keine semantischen Änderungen; normative Projektwerte und Parent-Revisionen
sind Teil der Bindung. Zur aktuellen Beobachtung gehören trotzdem alle
Originalbytes und die abschließende Prüfung ihrer Unverändertheit.

Dieser Konfigurationshash ist keine Modellwurzel. Eine echte Scopewurzel benötigt
zusätzlich den kanonischen Descriptor, aktuelle Seeds, vollständige Beobachtungen
der benötigten Ressourcen und Abhängigkeiten, `resolve_scope_closure` und
`fingerprint_scope`. Gleiches Eingabemodell, gleicher Descriptor, gleiche
Konfiguration und dieselben überprüften Providerbeobachtungen müssen unabhängig
vom aufrufenden Adapter dieselbe Wurzel ergeben. Fehlende Provider dürfen nicht
durch leere Beobachtungen ersetzt werden. Die native Artefakt-Seed-Schnittstelle
bestätigt keine Ressourcen-Vollständigkeit, Freigabe oder Evidence-Gültigkeit.

Spätere Validate-, Render-/View-, Coverage-, Readiness-, Baseline-, Evidence-,
Export- und Bundleadapter müssen diese Auswahl und Bindung ausdrücklich
übernehmen, aktuelle Eingaben prüfen und ihre eigenen Scope-/Freigabeverträge
erfüllen. Ein Hash allein erlaubt keine Evidence-Wiederverwendung. Der besondere
Vollprojektvertrag bleibt erhalten: `bundle create --scope project` erlaubt
keine Konfigurationsfilterung; konfigurierte Dokument-/Release-Bundles bleiben
partiell. Diese Anleitung registriert oder implementiert keine fehlenden Befehle.
