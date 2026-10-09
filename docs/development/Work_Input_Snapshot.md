# Schrittweise Erfassung von Eingangsbytes

`specroad.work.snapshot.InputSnapshotTask(roots, entries, block_bytes=65536)`
erfasst eine vom vertrauenswürdigen Aufrufer ausdrücklich benannte Eingangsmenge.
`roots` ordnet logische Root-IDs bestehenden `ProjectBoundary`-Objekten zu;
`entries` enthält ausschließlich `root_id` und relative `path`-Angaben.
Unbekannte Roots, unsichere Pfade und doppelte Eingänge werden abgewiesen.
Die Enumeration ordnet diese deklarierte Menge nach Root-ID und Pfad. Sie
behauptet keine automatische vollständige normative Projekterkennung.

`advance(max_units)` verarbeitet höchstens die genannte positive Anzahl
erfolgreicher Einheiten: eine Deklaration, ein geöffneter Eingang, ein gelesener
Block, eine versiegelte Datei oder das abschließende Eingangsmanifest.
Leseaufrufe sind auf höchstens 64 KiB begrenzt. Ein laufender Dateideskriptor
behält zwischen Aufrufen seine Position; bereits gelesene Präfixe werden nicht
wegen eines kleinen Arbeitsfensters erneut eingelesen. Der vorhandene
`opened_resource`-Adapter prüft Dateityp, Root, Pfadidentitäten und beobachtete
Größen-/Zeitänderungen. Erst nach dessen erfolgreichem Abschluss gilt die
einzelne Datei als vollständig erfasst.

Die unveränderlichen Bytes liegen unter ihrem SHA-256 im In-Memory-Objektspeicher.
`read_block(hash)` liefert bereits erfasste Blöcke, `read_input(root_id, path)`
eine vollständig erfasste Datei, auch wenn weitere Eingänge noch offen sind.
Fehlende Objekte oder unvollständige Eingänge erzeugen `SnapshotCaptureError`
mit maschinenlesbarer logischer Ressource; Hashes rekonstruieren keine Bytes.

`state` ist eine abgelöste JSON-Projektion mit bestätigtem Fortschritt,
Blockhashes, Bytepositionen und offenem Zustand. Das Manifest `captured-inputs-v1`
wird erst nach allen deklarierten Dateien versiegelt. Es bindet logische Namen,
Dateigrößen und vollständige Dateihashes, unabhängig von Blockgröße, Eingangsreihenfolge
oder absolutem Quellpfad. Nach der Erfassung werden ursprüngliche Bytes aus
diesem Bestand geliefert, auch wenn sich der Quellordner später ändert.
`work_inputs()` materialisiert ausdrücklich die vollständige Menge für den
bestehenden In-Memory-`work-v1`-Codec; es erteilt keine Ausführungsfreigabe.

Dies ist die erste aufteilbare Byte-Erfassung innerhalb derselben Invocation.
Der gesamte Objektspeicher und die deklarierte Menge liegen noch im Speicher;
die Blockgrenze ist keine Gesamt-RSS-Garantie. `close()` gibt offene Lesedeskriptoren
frei und erhält die erfassten Bytes im Taskobjekt. Fehler zählen die betroffene
Einheit nicht als erfolgreich, erhalten vorherige Daten und stoppen diesen Task.
Es gibt keinen automatischen Retry oder stillen Projektwrite.

`model_root_sha256` bleibt `null`, `atomic_project_snapshot` und
`durable_checkpoint` bleiben `false`. Die Erfassung einzelner Dateien bestätigt
noch keine gleichzeitige normative Projektmomentaufnahme: übergreifende Quell-
und Writerprüfung folgen in 6.k.R, Strukturtrennung in 6.k.C, dauerhafte
Generationen in 6.l und tatsächliche Wiederaufnahme in 6.m. Eine kleine
Arbeitsmenge erzeugt hier keinerlei Work-Dateien; auch bei größeren Eingängen
wird weder Code 8 noch eine veröffentlichte Checkpointgeneration behauptet.
