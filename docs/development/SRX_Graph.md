# SRX: begrenzte Graphoperatoren (4.f)

Grundlage: SR-REQ-0293, SR-REQ-0521 und Anhang B.2/B.3/B.5 der unveränderten Spezifikation. Nur lesende Operatoren; Arithmetik, Ressourcenbudgets, Profilkomposition, Projektlader und CLI-Fachbefehle folgen später.

## Explizit geladener Bestand

`LoadedGraph(sources, rule_id=...)` übernimmt eine Liste oder ein Tupel von `SourceRelations`. Die Datensätze werden aus ihren vorhandenen Bytes geprüft und vom Graphkern (`RelationReferences`, `RelationIndex`) vollständig aufgelöst und in beiden Richtungen indiziert. Fehlende Ziele, widersprüchliche Identitäten und unzulässige gespeicherte Kanten sind Fehler. Kein Dateipfad wird geöffnet, kein fremder Loader aufgerufen und kein Anzeige-/Teilindex als vollständig akzeptiert.

`EvaluationContext(..., graph=loaded_graph)` und `parse_context(..., graph=loaded_graph)` binden das Modell ausdrücklich. Der typisierte Parameter ist keine fünfte JSON-Kontextwurzel. artifact, configuration, project und relations bleiben unverändert. Nicht-Graph-Ausdrücke benötigen keinen Graph; ein tatsächlich ausgewerteter Graphoperator verlangt ihn. Ein übersprungener and/or-Zweig lädt nichts nach. Das aktuelle Artefakt muss wertgleich im gelieferten Modell enthalten sein.

`validation_scope=loaded_model_only`: Die Vollständigkeit gilt für den gelieferten Bestand. Eine rein lokale API kann eine vom Aufrufer ausgelassene, sonst unreferenzierte Quelle nicht erkennen. Der spätere Projekt-/Profilaufrufer muss den beabsichtigten Gesamtbestand frisch und vollständig liefern. Dies ist weder atomarer Projekt-Snapshot noch Lifecycle- oder Schreibfreigabe. Die passive relations-Wurzel beweist keine Vollständigkeit eingehender Kanten.

## Konkreter Ausdrucksvertrag

Die in B.2/B.5 semantisch benannten Operanden erhalten diese geschlossenen Felder:

- relation_count: op, direction, types.
- incoming_count: op, types; immer incoming, zusätzliches direction ist ein Fehler.
- has_relation: op, direction, types; optional target_type und target_id, bei gemeinsamer Angabe müssen beide passen.
- reachable: op, direction, types, where, max_depth.

Richtungen sind outgoing, incoming oder both, relativ zur gespeicherten Richtung. types ist eine explizite Liste bekannter Relationstypen oder der String `*`. Eine leere Liste bedeutet keine Kanten. Doppelte Typselektoren, unbekannte Typen, dynamische Selektoren, falsche Typen und unbekannte Felder sind Fehler. superseded_by ist ausschließlich ein berechneter Lesefilter; supersedes wählt bei incoming auch seine Gegenrichtung.

Gezählt werden gespeicherte Relations-IDs, nicht unterschiedliche Ziele. Bei incoming betreffen target_type/target_id die ursprüngliche Quelle. Kein display_id-/Label-Fallback.

## Breitensuche und Prädikat

reachable beginnt beim aktuellen artifact. max_depth ist explizit nichtnegative Ganzzahl, niemals Boolean, Float, String oder Default. Tiefe 0 prüft nur das Startartefakt. Queue und Besuchsmenge verhindern wiederholte Verarbeitung. Nachbarn sind nach Relationstyp, Ziel-ID und Relations-ID sortiert. Mehrere Wege ändern nicht die kürzeste gefundene Tiefe.

Im where-Prädikat ist artifact der Kandidat und relations dessen vollständige berechnete Nachbarsicht mit relation_id, type, source, target, target_type und inverse. project/configuration bleiben gleich. Kein neues item; eine äußere Quantorbindung bleibt verfügbar. Innere Quantoren binden ihr eigenes item. Nach Ende des Prädikats gelten wieder die äußeren Wurzeln.

Die Suche endet beim ersten wahren Boolean-Prädikat. Ein zuvor ausgewerteter Fehler bleibt SRV110, nicht false. Nach einem gefundenen Zeugen oder außerhalb der Tiefe nicht benötigte Kandidaten werden nicht ausgewertet. Der gesamte AST muss trotzdem gültig sein. Die separate vollständige Iterationssemantik von any/all/none bleibt unverändert.

Beispiel:

```json
{"language":"srx","version":"1.0","expression":{"op":"incoming_count","types":["depends_on"]}}
```

## Entwicklung

Verhaltenstests prüfen Richtungen, Mengen, Zielauswahl, explizite Tiefe,
Typ-/Modellfehler und unveränderte Eingaben. Für die Testausführung gilt die
lokale `AGENTS.md`; die technische Anleitung steht in [Testing.md](Testing.md).

## Robustheit (4.f.R)

BFS-Cursor und AST-Fortsetzungen tragen ihre eigenen Kandidatenwurzeln. Auch ineinander verschachtelte reachable-Ausdrücke benötigen keine rekursive Python-Auswertung; ein inneres Ergebnis oder Fehler verändert weder das äußere artifact noch item. Jeder Suchlauf hat seine eigene Queue und Besuchsmenge, ohne globale Daten. Tests ergänzen zyklische und inverse Wege, unabhängige Erreichbarkeits-Oracles, stabile Fehler-/Besuchsreihenfolge, breite Modelle, viele eingehende Kanten, wiederverwendete Kontexte, Fremdobjektablehnung und verschobene Modul-/Zipapp-Distributionen.

## Bereinigung (4.f.C)

Ein kleiner lesender GraphReadContext bündelt pro Operator Startbindung, Richtung, Typauswahl und Kandidatenprojektion. Direkte Operatoren und BFS benutzen dieselbe Grenze. Die Besitzverhältnisse der geladenen Daten, Fehler, Suchreihenfolge und sämtliche W/R-Testerwartungen bleiben unverändert.
