# Relationsidentitäten in der Bestandsmigration

Der native Migrationsplaner qualifiziert zuerst den vollständigen Referenzstand
0.1/1.0.1. Sein internes Relationsinventar bindet jede Ableitung an das exakte
SourceOriginal mit Originalbytes, Snapshot, Pfad, Rolle und Klassifikation.
Manifestprojektionen und veränderbare Zielartefakte beziehen ihre IDs daraus.
Unveränderbare Originale werden nicht als 0.2-Artefakte materialisiert.

Die Ableitung ist exakt Anhang Q.3: JCS des Arrays mit festem Namespace,
Projekt-ID, originaler Artefakt-ID, originalem nullbasiertem Relationsindex und
vollständigem Relationsobjekt; SHA-256, erste 16 Bytes, kanonisches 26-stelliges
Crockford-Token. Der ursprüngliche Arrayindex ist weder ein sortierter Index
noch das optionale Relationsfeld position. Unicode und Arraywerte werden nicht
normalisiert. Gleiche kanonische Eingaben in mehreren Snapshots sind dieselbe
Ableitung. Unterschiedliche Eingaben unter einer ID sind ein Fehler.

Der fertige R/C-Stand prüft Kollisionen auch dann, wenn Zieleingaben fehlen.
Das Inventar bleibt ein interner Wert des vorhandenen schreibfreien Planers.
Es autorisiert keine neue Migration, keinen Importgenerator und keinen Write.
Reguläre neue Relationen beziehen ihre random128-v1-IDs weiterhin ausschließlich
aus frischer Entropie. Menschliche Reviews und historische Originalhashes
werden durch abgeleitete Navigationsidentitäten nicht ersetzt.

Die festen erwarteten Präimage-/Hash-/ID-Werte liegen in
tests/data/migration_relation_vectors.json. Sie wurden unabhängig vom Produkt
erzeugt, nicht aus einer bestandenen Testausführung abgeleitet. Neue Abnahmen
laufen ausschließlich in Apply; nachfolgende M16-Funktionen bleiben offen.
