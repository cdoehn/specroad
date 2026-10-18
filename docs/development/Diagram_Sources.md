# Diagrammquellen aus gebundenen Graphdaten

`specroad.documents.resolve_diagram(model, diagram_kind, start_id=...,
direction=..., max_depth=..., max_nodes=..., max_edges=...)` liefert eigene,
unveränderbare `DiagramData` aus einem `TargetModel`-Snapshot. `.data` gibt
abgelöste JSON-Daten zurück; `.sha256` bindet deren kanonische Bytes.
`render_diagram` nimmt dieselben Auswahlargumente und zusätzlich
`output_format='mermaid'` oder `'dot'` sowie `label_mode='id'` (Standard) oder
`'title'` an und liefert UTF-8-Quellbytes.

Die Auswahlarten sind:

- `trace`: Relationsgraph aller ausdrücklich gelieferten Projektartefakte.
- `architecture`: nur Komponenten und Interfaces sowie gespeicherte Relationen
  zwischen ihnen. Ein Start außerhalb dieser Typen wird abgewiesen.
- `release`: der Start muss ein Release sein. Die bestehende native
  Release-Seed-Auswahl bestimmt die zulässigen Mitglieder: Release, zugehörige
  Milestones und direkt zugeordnete beziehungsweise eingeplante Artefakte.
  Andere Releases werden nicht durch Abhängigkeiten hinzugeladen.

Beide Funktionen erlauben zusätzlich `artifact_ids` und `relation_types`.
`None` erhält jeweils die bisherige Auswahl. Explizite Werte sind Listen oder
Tupel eindeutiger Strings, keine Wildcards oder Callbacks. `artifact_ids`
verengt die obige Auswahl; unbekannte oder außerhalb der Diagrammart liegende
IDs sind Fehler. Der Start muss enthalten sein. Die übrigen IDs sind zulässige
Knoten, keine zusätzlichen Startpunkte: über ausgeschlossene Zwischenknoten
wird nicht traversiert. `relation_types` bezeichnet gespeicherte Core-Typen,
auch bei rückwärts durchlaufenen Relationen. Beispielsweise wählt `supersedes`
beide Traversierungsrichtungen, während die abgeleitete Sicht `superseded_by`
kein zulässiger gespeicherter Auswahltyp ist. Eine leere Relationsliste wählt
keine Kanten. Explizite Auswahlen werden sortiert im Datenvertrag gebunden.

`direction` ist exakt `incoming`, `outgoing` oder `both`. Der Start zählt als
Knoten in Tiefe 0. Erreichte Knoten an `max_depth` werden aufgenommen und nicht
weiter expandiert. Der Export enthält die dabei durchlaufenen gespeicherten
Relationen, keine zusätzlich ergänzte induzierte Kantenmenge. Jede Relation
erscheint einmal mit ihrem ursprünglichen Source, Target und ihrer Identität,
auch wenn die Traversierung sie rückwärts oder von beiden Seiten erreicht.
Fachfelder eines Interface erzeugen keine erfundenen Relations-IDs.

Alle drei Grenzen sind ausdrücklich erforderlich. `max_nodes` ist mindestens 1,
`max_edges` und `max_depth` sind nichtnegative Integer; Booleanwerte sind keine
Grenzen. Eine Überschreitung der Knoten-/Kantenanzahl ist ein fachlicher Fehler,
kein still gekürztes Erfolgsresultat. Der native Graphkern prüft Referenzen,
Relationsmatrix und kanonische Speicherung auch außerhalb der besuchten Auswahl.

Der Vertrag `diagram-data-v1` enthält geordnete Knoten-/Kantenidentitäten,
Originaltitel, Revisionen, Quell-/Record-/Relationshashes und die vollständige
gespeicherte Relation. Auswahl, Modellwurzel, Inputhash, Profil- und Toolversion
sind gebunden. Diagramm-IDs bestehen aus `n_` beziehungsweise `e_` plus dem
vollständigen UTF-8-Hexwert der ursprünglichen Identität; weder Titel noch
Reihenfolge bestimmen sie. Der Vertrag bestätigt keine aktuelle Dateisystem-
oder vollständige Projektvalidierung, Readiness, Approval oder Schreibrechte.

Die Quellprofile `mermaid-flowchart-ids-v1` und `graphviz-dot-ids-v1` verwenden
weiterhin validierte Artefakt-IDs und Core-Relationstypen als Beschriftung.
`label_mode='title'` wählt die Profile `mermaid-flowchart-text-v1` beziehungsweise
`graphviz-dot-text-v1`: Originaltitel werden als einfache Textlabels ausgegeben.
C0-/C1-Steuerzeichen erscheinen darin als sichtbare literale `\uXXXX`-Sequenzen;
die Diagrammdaten behalten den vollständigen unveränderten Titel. Mermaid kodiert
jedes Zeichen des Titellabels als dezimale Entity innerhalb eines gewöhnlichen
zitierten Textlabels, einschließlich bereits vorhandener Entitymarker. Titel
werden weder HTML-/Markdownlabels noch Konfigurationsdirektiven. DOT verwendet
zitierte UTF-8-Strings mit geschützten Anführungszeichen und verdoppelten
Backslashes; insbesondere bleiben `\N`, `\G` und ähnliche Eingaben literaler
Text statt Graphviz-Substitutionen. Es werden keine benutzerdefinierten Attribute
oder URLs erzeugt. Beide Quellen tragen eine Generated-Markierung und den Hash
der Diagrammdaten. Labelmodus und Ausgabeformat ändern den Graphumfang nicht.
Mermaid verwendet Flowcharts mit expliziten Kanten-IDs; ein externer Consumer
muss diese Syntax unterstützen. DOT verwendet einen gerichteten, nicht-strikten
Graphen, damit unterschiedliche Relationen desselben Endpunktpaars erhalten
bleiben. Die Syntaxgrundlagen stehen in der
[Mermaid-Dokumentation](https://mermaid.js.org/syntax/flowchart.html#attaching-an-id-to-edges)
und der [DOT-Sprachbeschreibung](https://graphviz.org/doc/info/lang.html).
Die Labelkodierung folgt den
[Mermaid-Entities](https://mermaid.js.org/syntax/flowchart.html#entity-codes-to-escape-characters)
und [Graphviz-Stringregeln](https://graphviz.org/docs/attr-types/escString/).

Es gibt keine Templates, Callbacks, Imports aus dem Modell, Netzwerkzugriffe,
Dateiausgabe oder Renderer-/Browseraufrufe. Auch SVG-/PNG-Ausgabe wird nicht
implizit an ein Fremdwerkzeug delegiert. CLI-Anbindung und konfigurierte Varianten
sind durch diese API-Schritte nicht implementiert. Die Tests prüfen Graphdaten,
Auswahl- und Fehlerverträge, Bindungen und Seiteneffekte; DOT-
oder Mermaidtexte, Layout und visuelle Darstellung sind keine Testoracles.
