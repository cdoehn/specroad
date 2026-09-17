# Relationsdaten und Referenzprüfung

## Planschritt 3.a.W

`specroad.graph.relations.SourceRelations` liest die unveränderten Bytes eines
Artefakts. Die Relation bleibt an dessen Identität gebunden und enthält zwingend
`relation_id`, `id_scheme`, `type`, `target`, `external_identities`, `extensions`.
Die 17 gespeicherten Kernarten sind zulässig; `superseded_by` ist kein gespeicherter Typ.
Optionale Begründung und Erstellungsdaten sowie `contains.position` bleiben erhalten.

`Relation.data` liefert unabhängige Daten. Externe Identitäten behalten mindestens
die drei Schlüssel aus Spec §10.12 und optional `external_revision`. Ist ein
Importbindungsfeld vorhanden, müssen alle fünf Felder dieser Bindung vorhanden
sein. Das prüft nur ihre Form, nicht Quelle, Hashauthentizität oder Importpolitik.
Gleiche externe Schlüssel innerhalb einer Relation sind unzulässig. Eigene
Erweiterungen gehören in namespaced `extensions` und sind niemals Code.

Der projektgebundene Leser `specroad.storage.relations.read_source_relations`
verwendet die vorhandene Root-/Pfad-/Identitätsgrenze und prüft die Originalbytes
erneut. Er schreibt nichts und erzeugt keinen atomaren Snapshot.

Die ausgewiesene Grenze `relation_fields_only` ist verbindlich: noch keine
Quell-/Zielmatrix, Zielauflösung, vollständigen Indizes, Zyklen, Reviewfreigabe,
Inverse oder schreibenden Authoringoperationen. Die bestehende gemeinsame
Artefaktprojektion bleibt bewusst schwächer; eine solche Projektion ist keine
vollständige Relationsvalidierung. Originale und Spezifikation bleiben unverändert.
