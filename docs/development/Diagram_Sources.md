# Diagrammquellen aus gebundenen Graphdaten

`specroad.documents.resolve_diagram(model, diagram_kind, start_id=...,
direction=..., max_depth=..., max_nodes=..., max_edges=...)` liefert eigene,
unveränderbare `DiagramData` aus einem `TargetModel`-Snapshot. `.data` gibt
abgelöste JSON-Daten zurück; `.sha256` bindet deren kanonische Bytes.
`render_diagram` nimmt dieselben Auswahlargumente und zusätzlich
`output_format='mermaid'` oder `'dot'` an und liefert UTF-8-Quellbytes.

Die Auswahlarten sind:

- `trace`: Relationsgraph aller ausdrücklich gelieferten Projektartefakte.
- `architecture`: nur Komponenten und Interfaces sowie gespeicherte Relationen
  zwischen ihnen. Ein Start außerhalb dieser Typen wird abgewiesen.
- `release`: der Start muss ein Release sein. Die bestehende native
  Release-Seed-Auswahl bestimmt die zulässigen Mitglieder: Release, zugehörige
  Milestones und direkt zugeordnete beziehungsweise eingeplante Artefakte.
  Andere Releases werden nicht durch Abhängigkeiten hinzugeladen.

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

Die initialen Quellprofile heißen `mermaid-flowchart-ids-v1` und
`graphviz-dot-ids-v1`. Sie verwenden ausschließlich validierte Artefakt-IDs und
Core-Relationstypen als Beschriftung. Beliebiger Titel-/Artefakttext bleibt in
den Daten und wird in diesem W-Zustand nicht in Quellsyntax eingesetzt. Beide
Quellen tragen eine Generated-Markierung und den Hash der Diagrammdaten.
Mermaid verwendet Flowcharts mit expliziten Kanten-IDs; ein externer Consumer
muss diese Syntax unterstützen. DOT verwendet einen gerichteten, nicht-strikten
Graphen, damit unterschiedliche Relationen desselben Endpunktpaars erhalten
bleiben. Die Syntaxgrundlagen stehen in der
[Mermaid-Dokumentation](https://mermaid.js.org/syntax/flowchart.html#attaching-an-id-to-edges)
und der [DOT-Sprachbeschreibung](https://graphviz.org/doc/info/lang.html).

Es gibt keine Templates, Callbacks, Imports aus dem Modell, Netzwerkzugriffe,
Dateiausgabe oder Renderer-/Browseraufrufe. Auch SVG-/PNG-Ausgabe wird nicht
implizit an ein Fremdwerkzeug delegiert. CLI-Anbindung, konfigurierte Varianten
und Erweiterungen des Beschriftungsprofils sind durch diesen W-Schritt nicht
implementiert. Die Tests prüfen Graphdaten, Bindungen und Seiteneffekte; DOT-
oder Mermaidtexte, Layout und visuelle Darstellung sind keine Testoracles.
