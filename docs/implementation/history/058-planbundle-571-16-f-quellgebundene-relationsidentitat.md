# Planbundle 571 — 16.f: quellgebundene Relationsidentität

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Planbundle 571 — 16.f: quellgebundene Relationsidentität

Basis ist das vollständig nativ geprüfte saubere Result mit SHA-256
`6a7729727fea4dd7d94f95ac74b37bee9566e51511db71ea7ce2009c5fe4c13f`
und Abschlusscommit `037bf769bdda60f9f83d71ac27109b178ef6afe7`.
Der Korrekturrest 16.e.R/C ist mit eigenen Gates (6981 beziehungsweise 6939
bestandene Tests) und beiden Commits vollständig abgeschlossen. Der tatsächliche
Ausgangspunkt umfasst 675/900 Produktcommits. Frühere Erfolge bleiben erhalten.

Q.3, 9.2, 12.20.2 und SR-REQ-0273/0509 legen die Fachregel bereits vollständig
fest. Keine normative Lücke, kein Klärungspräfix und keine neue Spezifikations-
fassung. Die in 16.c benötigte Grundberechnung wird zum an Originale gebundenen
gemeinsamen Relationsinventar vervollständigt. Das Inventar gehört ausschließlich
zum qualifizierten Referenzquellvertrag 0.1/1.0.1; es registriert keinen freien
Generator und erteilt keine Schreib-, Review- oder menschliche Freigabebefugnis.

W berechnet die Q.3-Projektionen für aktuelle und transitive historische
Originale. Originalbytes, Snapshot, Pfad, Rolle und Klassifikation binden jede
Abfrage. Manifest und veränderbares Ziel verwenden dieselben Projektionen.
Immutable Originale bleiben bytegleich und dürfen nur navigierbare Manifest-
projektionen erhalten. Ausgegeben werden eigene Kopien, kein mutierbarer Alias.
Unabhängig verfasste Datenvektoren binden den exakten Namespace, Projekt-ID,
Source-ID, Originalindex, RFC-8785-UTF-8, SHA-256/erste 16 Bytes und 26-stelliges
Crockford-Token. Unicode-Reihenfolge, Zahlen, Arrays und unveränderte Quell-
darstellung gehören dazu. Die Testdaten wurden ohne Produktcode erzeugt;
Vektorerzeugung und Collection sind keine ausgeführten Verhaltenstests.

R prüft das gesamte Ableitungsinventar bereits vor fehlenden Zieleingaben.
Unterschiedliche kanonische Ableitungseingaben mit derselben ID scheitern;
gleiche Eingaben in mehreren Snapshots bleiben zulässig. Keine zufällige
Umbenennung und kein Ausweichen auf einen zweiten Namespace. Zusätzliche
Gegenproben schützen historische Kollisionen, exakte Originalbindungen,
unveränderbare Klassifikation, ungeeignete Quellwerte und reguläre Zufalls-IDs.
C trennt die gemeinsame Ableitung vom Originalarchiv und vom regulären
random128-v1-Erzeuger. Testdaten, erwartete Werte, Fehler und Katalog bleiben
gegenüber R bytegleich; keine neue Fachentscheidung im Refactoring.

Jeder echte W/R/C-Zustand erhält seine eigene fällige N=3-Gruppe (1/2/0)
plus vollständige ungefilterte Pflichtauswahl vor seinem Commit. Dev führt
keine Testkörper oder Fixtures aus. Source-/Plan-/Hash-/Identity-Regressionen
und alle neuen Testdateien sind Pflicht. Keine Vollsuite- oder Releasebehauptung.
Vorbereiteter Zwischenstand: C; Häkchen werden nur nach Apply-Gate committed.

Die weiteren M16-Gates bleiben offen: öffentliche Registrierung, Writer,
aktuelle Legacy-Lesbarkeit, Verification, CLI/Restore und Abschluss. Die
Querreferenzen SR-REQ-0512/0513 verlangen weiterhin Einzelverlustberichte
und den Sicherungsbundle-Verweis ohne verlustfreien Downgrade. Ihre Kataloge
bleiben unverändert offen; Relations-IDs werden nicht als deren Abnahme
ausgegeben. Diese Pflichten bleiben zusätzlich bei 16.h/16.k nachvollziehbar.
Nach erfolgreichem C wäre 678/900 erreicht; nächster Schritt ist 16.g.W.
