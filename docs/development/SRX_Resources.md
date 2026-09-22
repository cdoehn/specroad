# SRX-Ressourcen und Sicherheitsgrenzen

Stand 4.h.W. Die API bleibt eine reine In-Memory-Auswertung. Fachliche Werte
werden weder aus der Hostumgebung beschafft noch durch ein Arbeitsziel verändert.

## Strukturgrenzen

`StructureLimits(ast_nodes=10000, ast_depth=2048)` ist die offengelegte,
versionierte **Bibliotheks-Grundpolicy** `srx-resource-v1`, keine normative
Behauptung über einen bereits vollständig komponierten Release-/Projektstandard.
Der Knotenwert greift die bisherige Beispielkonfiguration auf; 2048 ist eine
konservative Implementierungsentscheidung, die den vorhandenen tiefen Korpus
erhält. Ein Aufrufer kann andere positive Werte ausdrücklich binden.

Gezählt werden ausführbare Ausdrucksvorkommen, einschließlich nicht ausgewerteter
Kurzschlusszweige. Wurzeltiefe ist 1; Hülle, args-Container und Literal-Daten sind
keine zusätzlichen AST-Knoten. Gemeinsame Python-Objekte an zwei Positionen zählen
zweimal, echte Zyklen sind ungültig. JSON-Literalstrukturen bleiben reine Daten;
die AST-Grenze ist ausdrücklich **kein Gesamt-RAM-/CPU- oder JSON-Payload-Limit**.

Der Konstruktor `SrxProgram(..., structure_limits=...)` prüft vor der JSON-Kopie
und anschließend deren eigenen Inhalt. `parse_program` nutzt denselben Vertrag
nach dem bestehenden strikten JSON-Reader. Beim Auswerten gilt zusätzlich die
effektive Projektgrenze des aktuellen `EvaluationContext`. Wiederverwendung eines
Programms umgeht daher keine später strengere Projektgrenze.

`project.resource_limits` kann `srx_nodes`, `srx_depth`, `srx_operations`,
`srx_iterations` und `srx_graph_steps` enthalten. Fehlende Werte werden aus der
obigen offengelegten Bibliothekspolicy materialisiert; Originaldaten bleiben
unverändert. Andere nicht-SRX-Projektgrenzen bleiben bei ihren zuständigen
Komponenten. Unbekannte `srx_`-Namen sowie null, 0, negative, boolesche, gebrochene
oder textuelle Grenzwerte werden abgewiesen. AST-Grenzverletzungen liefern
`SRV111`, die betroffene Ausdrucksposition, Limit und beobachteten Wert.

## Arbeitsziele und Beobachtung

`srx_operations` (1.000.000), `srx_iterations` (1.000.000) und
`srx_graph_steps` (2.000.000) sind weiche Arbeitsziele. Die beiden neuen Namen
sind explizite lokale Konfigurationsfelder; sie werden wie `srx_operations` von
der semantischen Konfigurationsprojektion ausgeschlossen. Knoten/Tiefe bleiben
gebunden. Keine Zielüberschreitung ändert das Fachresultat, erhöht ein Ziel,
startet Worker oder erzeugt automatisch einen Timeout.

`evaluate_with_usage(program, context)` ergänzt die kompatible wertliefernde
`evaluate`-API. Es liefert einen unabhängigen Wert und unveränderliche Nutzung:
- evaluation_steps: tatsächlich betretene Ausdrucksknoten;
- iterations: tatsächlich gestartete Quantorprädikate;
- graph_steps: gelesene Nachbarschafts-/Kontextkanten und gestartete BFS-Kandidaten.

Diese semantischen Messpunkte sind keine genaue CPU-Instruktionsbilanz und
messen weder tatsächlichen RAM noch Uhrzeit. Nicht benötigte Kurzschlusszweige
zählen nicht als ausgeführte Arbeit; sie bleiben Teil der Strukturprüfung.

Überschreitungen stehen mit `soft_budget_exceeded=true` in der Beobachtung.
Die Bibliothek arbeitet in diesem Aufruf vollständig weiter. Es gibt keinen
künstlichen Regelwert, keinen persistenten Checkpoint, keine Resume-Zusage und
keinen fachlichen Fehler bloß wegen der Arbeitszahl. Die spätere Work-Engine
kann sichere Fortsetzungspunkte außerhalb der Operatorsemantik anbinden.

## Nachweisgrenze

Kein CLI-Fachbefehl, keine OS-Sandbox, kein Dateizugriff und kein automatisches
Lockern harter Grenzen. Vollständige Profilkomposition, beobachtete Hostquoten
und persistente Work-/Checkpoint-Protokolle folgen in ihren Planschritten.
Lokal nur ausgewählte vier-Worker-Gates, Volltests und serielle Referenzen in CI.
