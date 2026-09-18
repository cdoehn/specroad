# Scope-Descriptor und Ausgangsmengen – 3.f

Vertrag: Spezifikation 0.2.7, Kapitel 10.8/10.8.1 und 11.6. Die APIs bilden
Ausgangsmengen vor der Closure. Keine neue CLI, Schreibberechtigung,
vollständige Modellvalidierung oder Releasefreigabe.

## Eingaben und Grenzen

`ScopeDescriptor` hält den vollständigen scope-v1-Descriptor unveränderlich.
Sämtliche Felder, exakte Selektorfelder, core-closure-v1 und closed/partial sind
Pflicht. Die Prüfung ersetzt keine fachliche Queryvalidierung. `ScopeSeedInputs`
übernimmt ausdrücklich gelieferte `SourceRelations` und `ScopeResource`-Einträge;
Quellen werden mit ihren ursprünglichen Bytes gebunden. Das ist **keine**
Behauptung einer vollständigen automatischen Projektinventur. Ressourcen-IDs sind
opake logische Identitäten des Ressourcenanbieters. Dieser muss bei versionierten
Ressourcen Identität und Version eindeutig verbinden. Dateinamen, Anzeigenamen
und URLs werden nicht aufgelöst oder ausgeführt.

Die Auswahl arbeitet deterministisch über diesen Bestand:
- specification: Artefakte außer proposal/baseline, semantische Konfiguration,
  ausdrücklich aktive Profile, Regeln und Mappings;
- project: sämtliche aktuellen normativen Eingaberessourcen, einschließlich
  proposal/baseline, Konfiguration und ausdrücklich gebundener Archivressourcen;
- release: Release, über part_of direkt zugeordnete Milestones, eingehende
  scheduled_for-Beziehungen auf diese Ziele sowie Tasks mit part_of darauf;
- document: ausschließlich das ausgewählte Dokument als Ausgangspunkt;
- explicit: genau die beiden angegebenen sortierten, duplikatfreien ID-Mengen;
- query: genau die bereits paginierte, geordnete Seite eines Queryresolvers.

Abschnitte, Inhaltsblöcke und transitive Abhängigkeiten folgen erst über 3.g und
die folgenden Closures. SR-REQ-0409 wird zusammen mit der präzisen Trennung in
10.8 gelesen. Der permanente Kontrollartefaktausschluss muss in der Closure auch
bei jeder späteren Aufnahme gelten. Retired/rejected wird nicht ausgeblendet.

## Query-Anschluss (interner Vertrag)

Das vollständig materialisierte Query-Objekt hat `filters`, `srx_filters`,
`select`, `sort`, `evaluation`, `offset` und `limit`. Eine ausgelassene
Wertfiltergruppe ist gemäß 11.6 neutral. Angegebene Wertelisten sind normalisiert,
eindeutig und sortiert; `select` und `sort` behalten ihre Reihenfolge. Sortiereinträge
bestehen aus `key` und `direction`. SRX-Einträge bestehen aus `expression` und dem
SHA-256 ihres vollständigen kanonischen Inhalts, niemals Dateipfaden. Es werden
hier keine Defaults geraten oder ausgeführt.

`QuerySeedPage` übernimmt eine vom **vertrauenswürdigen Queryresolver** berechnete
Seite und prüft Identitäten, Pagination und Eingangsbindungen. Das ist kein
Query-Evaluator: Filterwahrheit, SRX-Typprüfung, Evaluation und korrekte Sortierung
bleiben Aufgaben des späteren Resolvers. Ohne Seite folgt ein Fehler, nicht ein
erfolgreicher leerer Scope. Seiten zu anderen Daten oder einem anderen Descriptor
werden zurückgewiesen. `artifact_ids` erhält die Queryreihenfolge;
`canonical_artifact_ids` liefert separat die sortierte Mitgliedschaft für Closure.
Der interne Anschluss definiert kein neues CLI-/Importformat.

## Konfiguration und Archive

Eine configuration_id muss existieren und den passenden Typ besitzen. Ohne den
späteren effektiven Konfigurations-/Applicability-Resolver wird ihre Auflösung
abgewiesen, nicht ungefiltert fortgesetzt. Für project muss jeder vorhandene
Baseline-Eintrag eine explizite Archivzuordnung besitzen, auch wenn sie leer ist.
Fehlende Archivressourcen sind Fehler. Der spätere Baseline-Provider muss die
rekursive Vollständigkeit ermitteln; diese Schnittstelle beglaubigt sie nicht.

## Verhaltenstests

Tests prüfen Mitgliedschaft, geordnete Queryseiten, Inputbindungen, unveränderte
Daten und Modellfehler. Keine Konsolen-/Formatierungs-/Doku-Oracles. Die reinen
Vorbereitungsbausteine führen weder Netzwerk- noch Dateischreibzugriffe aus.
Bestehende ModelManifest-Aufrufer bleiben auf ihren implementierten Teilumfang
beschränkt, bis Scope-Closure und Fachresolver integriert werden.

## R: Konfigurationshüllen und frische Projektlesezugriffe

Auch der siebte Descriptor `configuration` ist strukturell definiert: genau eine
configuration_id und ein unkonfigurierter Basisscope anderen Typs. Eine zweite
Hülle oder ein schon konfigurierter Basisscope sind Fehler. Die effektive
Konfigurationsauflösung bleibt wie oben ausdrücklich gesperrt, bis ihr Resolver
vorhanden ist; eine gültige Hülle ist kein ungefiltert gültiger Scope.

`storage.scope_seeds.read_artifact_scope_seeds` verbindet document/release sowie
artifact-only explicit mit der vollständigen **aktuellen Artefaktinventur** aus
3.e. Quellbytes und Mitgliedschaft werden nach der Auswahl erneut geprüft.
Fehlende/ungültige Quellen und beobachtete Änderungen liefern keinen Teilerfolg.
Die lokale Projektbindung wird getrennt mitgeliefert; `atomic_snapshot=false`.
Ressourcenweite project/specification-Scopes und Query-/Konfigurationsauflösung
werden von diesem spezialisierten Reader nicht still auf Artefakte reduziert.
