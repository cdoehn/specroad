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

## Planschritt 3.a.R

`prepare_relation_update` berechnet eine neue Metadatenprojektion, ohne Datei oder
Originalobjekt zu verändern. `relation_id`, `id_scheme`, `type`, `target` sowie
das Quellartefakt dürfen bei einem Update nicht wechseln. Identische Werte sind
zulässige No-ops. Begründung, externe Bindungsdaten, Extensions und bei Contains
die Position können als vollständige Feldwerte vorgeschlagen werden.
`require_retained_relation_keys_unchanged` erkennt auch einen unzulässigen
Zielwechsel in einer ersetzten Artefaktdatei, unabhängig von der Relationsordnung.

Entfernen und Hinzufügen einer Relation mit frischer ID ist kein Update. Der
Vergleich erteilt dafür ausdrücklich keine Authoringfreigabe: vollständige
Inventur, frische ID, Revisionierung, Spezialartefaktregeln und die transaktionale
Veröffentlichung werden erst in ihren späteren Schritten integriert.

## Planschritt 3.a.C

Die öffentliche API bleibt in `graph.relations`. Neutrale Relationswerte,
Feldprüfungen und reine Update-Guards sind in getrennten Modulen. Der bestehende
Leser und sämtliche Verhaltenserwartungen bleiben unverändert. Diese Trennung
führt keine persistenten Indizes oder Writeroperationen vorzeitig ein.

## Planschritt 3.b.W

`validate_relation_references` prüft die explizit übergebenen `SourceRelations`
gegen die vollständige Quell-/Zielmatrix aus §9.7. Ziele werden ausschließlich
über echte Artefakt-IDs aufgelöst; display_id, externe Kennungen und Dateipfade
sind keine alternativen Zieladressen. Alle Kanten einschließlich `references`
verlangen vorhandene Ziele; jeder Self-Link ist verboten. Doppelte Artefakt-
oder Relations-IDs und gemischte Projektpräfixe werden zurückgewiesen.

`refines` zeigt unverändert von Detail zu Allgemeinem; `depends_on` bleibt eine
andere Beziehung. Die Datenprüfung kann nicht aus natürlicher Sprache beweisen,
ob eine Anforderung tatsächlich detaillierter ist oder eine Voraussetzung braucht.
`ResolvedRelation` enthält die beobachteten Endpunktidentitäten, keine Reifegrad-
oder Reviewfreigabe. Das Ergebnis trägt `relation_references_only`.

Der Aufrufer muss den vorgesehenen vollständigen Modellbestand liefern.
Das Ergebnis ist vollständig für diese Eingabe, aber keine Behauptung, dass ein
Projekt vollständig gescannt wurde. Grenzreferenzen partieller Scopes, inverse
Sichten, Zyklen und Review-/Lifecyclegates folgen später. Ein temporäres Lookup
ist kein persistenter Adjazenzindex. Es gibt weiterhin keinen neuen CLI-Befehl.

## Planschritt 3.b.R

Ein unabhängiger Testvertrag prüft alle 17 × 28 × 28 Quell-/Zielkombinationen.
Jede erlaubte Kombination wird zusätzlich durch echte Relations-/Artefaktobjekte
aufgelöst. Self-Links bleiben unabhängig von der Typkombination immer verboten.

Externe Relationsidentitäten werden innerhalb der übergebenen Objektklasse
projektweit auf doppelte `(source_system, source_document, external_id)` geprüft;
eine andere externe Revision macht denselben Schlüssel nicht zu einer anderen
Identität. Artefakt- und Relationsidentitäten sind getrennte Objektklassen.
Fehlende Ziele, Schlüsselkonflikte oder fremde Eingaben ergeben niemals ein
teilweise erfolgreiches Resultat und verändern weder Eingaben noch Dateien.
Mehrere Verfeinerungsbeziehungen und verschiedene Relationstypen zwischen
denselben Endpunkten bleiben getrennte Kanten mit eigener Relation-ID.

## Planschritt 3.b.C

`graph.relation_types` ist das eine unveränderliche Register für gespeicherte
Arten und ihre vollständigen Quell-/Zielregeln. `graph.relation_matrix` bewahrt
die öffentliche Prüf-API. Der Feldparser und die Referenzprüfung verwenden
dieselbe Registry; zukünftige Authoring- und Importpfade sollen diese APIs
wiederverwenden statt eigene Matrixkopien anzulegen. Regeln, Ergebnisse,
Fehlerklassen und Nebenwirkungsgrenzen bleiben identisch.

## Entwicklungsabnahme

Für die Testausführung gilt die lokale `AGENTS.md`; die technische Anleitung
steht in [Testing.md](Testing.md).
Die lokale CPython-3.13-Vorprüfung ist kein Nachweis der gesamten 3.10–3.14-
Matrix und ersetzt nicht den Pixel-Apply. Die lokalen Upstream-Entwicklungsbuilds
von xdist/execnet gehören nicht zum ausgelieferten Core oder Patchpaket.


## 3.c – Kanonische Symmetrie und berechnete Sichten

`canonical_relation` und `canonical_relations` bereiten `conflicts_with` und
`duplicates` in lexikografischer Reihenfolge der vollständigen Artefakt-IDs vor.
Relations-ID, ID-Schema und sämtliche Metadaten bleiben erhalten. Mehrere
Speicherkopien derselben symmetrischen Typ-/Endpunktkombination sind ein Fehler,
nicht ein Anlass, IDs zu verwerfen oder Metadaten automatisch zusammenzuführen.
Andere gerichtete Beziehungstypen werden nicht umgedreht.

Die vorhandenen generischen Immutable-Key-Prüfungen bleiben unverändert streng.
`require_canonical_reorder` prüft ausschließlich die exakte Symmetrie-Umordnung,
einschließlich aller sonstigen Metadaten; es autorisiert keine Mutation. Die
spätere Schreibtransaktion muss diese vorbereitete Änderung separat planen,
Revisionen behandeln und alle vollständigen Zielinvarianten prüfen.

`RelationViews` akzeptiert nur bereits kanonische, aufgelöste Eingabemengen.
`for_artifact(id, direction="outgoing"|"incoming"|"both")` bezieht die Richtung
auf die physisch gespeicherte Kante. Eingehende Sichten tauschen die dargestellten
Endpunkte; `inverse=True` macht dies ausdrücklich. Nur `supersedes` erhält dabei
den spezifizierten Namen `superseded_by`; für andere gerichtete Typen ist der
Richtungsindikator maßgeblich. Alle Sichten sind `normative=False` und behalten
Relations-ID und Verweis auf das unveränderte gespeicherte Original.

Prüfumfang: `canonical_relations_and_views_only`. Keine implizite Korrektur
gespeicherter Dateien, keine vollständige Projektinventur, kein persistenter
Index, keine Graph-/Lifecycle-Freigabe und keine neue CLI-Schreibfunktion.
Die Tests prüfen Identitäten, Eingabeerhalt und erlaubte/abgewiesene Operationen,
nicht Darstellung oder Konsolentexte.


## 3.d – Hierarchien und Dokumentpositionen

`validate_hierarchies(RelationReferences(...))` prüft `refines`, `part_of`,
`supersedes` und `contains` jeweils getrennt auf gerichtete Zyklen. Die Regeln
werden nicht auf die Vereinigung aller Beziehungstypen übertragen. Insbesondere
ist ein `depends_on`-Zyklus durch diese lokale Hierarchieregel allein nicht
verboten; Planungs- und Readiness-Regeln dürfen darüber später separat urteilen.
Die bestehende Referenzprüfung weist fehlende Ziele und Selbstbeziehungen vorher ab.

Eine gemeinsame iterative Tiefensuche benötigt keinen rekursiven Python-Stack.
Bei einem Zyklus wird eine deterministisch ausgewählte erste blockierende
`HierarchyCycleError` mit Beziehungstyp, geschlossener Artefakt-ID-Folge und
zugehörigen Relations-IDs erzeugt. Es wird nicht behauptet, dass dieser eine
Pfad alle möglichen Zyklen aufzählt. Die Typreihenfolge ist `refines`, `part_of`,
`supersedes`, `contains`; innerhalb eines Typs werden IDs deterministisch geordnet.
Ein erfolgreicher Rückgabewert hat `validation_scope=hierarchies_only` und
bezieht sich ausschließlich auf die übergebene Menge, nicht auf eine automatisch
ermittelte vollständige Projektmenge.

`ordered_children` ordnet ausgehende `contains`-Beziehungen eines expliziten
Dokuments oder Abschnitts nach numerischer Position, vollständiger Ziel-ID und
Relations-ID. Null ist gültig; boolesche, negative und gebrochene Werte sind es
nicht. Gemäß vorhandener JSON-Integer-Semantik ist `0.0` ebenfalls Null. Die
Ordnung betrifft die normativen Dokumentdaten, nicht die visuelle Ausgabe.
Weder Relations-IDs noch die Reihenfolge der ursprünglichen Arrays werden geändert.

Nicht enthalten: Include-Graph-Auflösung, Prüfung genau eines Abschnittselterns,
Document-Rendering, Source-Inventur, Authoring, Revisionserhöhung und sichere
Schreibtransaktionen. Diese bleiben den passenden späteren Planschritten zugeordnet.
Neue Tests prüfen beide Symmetrietypen, ID-/Metadaten-Erhalt, inverse Projektion,
alle Drei-Knoten-Digraphen pro Hierarchietyp gegen einen unabhängigen
Erreichbarkeitsoracle, tiefe Ketten/Zyklen und Positionen. Keine Darstellungstests.
