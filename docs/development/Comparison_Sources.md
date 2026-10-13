# Vergleichsquellen (Bibliotheksstand 8.j.C)

`ComparisonSourceSnapshot(root, kind='local')` erfasst ein lokales Projekt nach
dem bestehenden Project-Read-Preflight. `kind='git', reference='<Ref>'` liest
ausschließlich den fest gebundenen Commit über `GitObjectSource`; dessen
[Git-Grenzen](Git_Object_Source.md) gelten unverändert. Optional verlangt
`expected_project_id` eine bestimmte Projektidentität. Baseline und Bundle
sind benannte, ausdrücklich noch nicht verfügbare Quellenarten.

Eine private, unveränderliche Registry ordnet die aktiven Quellenarten ihren
Lesefunktionen zu; Baseline und Bundle behalten gesperrte Einträge. Lokale
Erfassung und Git-Erfassung sind von der gemeinsamen Artefaktprüfung getrennt.
Die lokale Abschlussfunktion läuft weiterhin nach dieser Prüfung und vor der
Snapshot-Rückgabe. Reihenfolge, Fehlerverträge, Rohbyte-Bindung und zulässige
Seiteneffekte bleiben unverändert; die Registry aktiviert keine weiteren Adapter.

Der unveränderliche Snapshot enthält eine geprüfte `ProjectConfiguration`,
`ComparisonInputs` und eigene Rohbytes aller konfigurierten normativen
JSON-Ressourcen. Artefaktfelder, gemeinsame Hülle, Relationen und ID-/Pfadzuordnung
werden geprüft. Lokale Inventur und gelesene Bytes werden erneut beobachtet;
ein beobachteter Wechsel führt zum Fehler. Das ist kein atomarer Dateisystem-
Snapshot und keine Sperre gegen nicht kooperierende Schreiber. Nach erfolgreicher
Erfassung bleiben die eigenen Werte auch bei späteren Quelldateiänderungen stabil.

Der abschließende Preflight beobachtet den Betriebszustand nochmals nach den
letzten Byte-/Inventurprüfungen. Eine dabei erschienene offene Transaktion sperrt
die Rückgabe; sie wird weder repariert noch entfernt. Auch diese letzte Beobachtung
ist keine atomare Sperre. Ungültige erwartete Projektkennungen einschließlich
unzulässiger Unicode-Werte scheitern vor der Quellenöffnung. Projekt-ID und
ID-Präfix müssen vor jeder Ressourcenklassifikation des Vergleichs übereinstimmen.

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

Die zusätzlichen R-Nachweise betreffen frühe Auswahlfehler, Identitätskonflikte,
Schema- und Inventurgrenzen, zwischenzeitliche lokale Änderungen sowie fehlende
Git-Konfigurationen oder Objekte bei gleichzeitig vorhandenen gültigen aktuellen
Dateien. Die aktuellen Dateien ersetzen keine fehlende historische Quelle.
Gespeicherte Evidence-, Baseline- oder Review-Zustände werden als Daten erfasst;
ihre Erfassung authentifiziert keine Freigabe und bestätigt keine Vollständigkeit
des umgebenden Modells.
