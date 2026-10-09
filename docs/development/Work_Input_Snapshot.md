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
Block, eine versiegelte Datei, ein erneut gehashter Validierungsblock, ein
abschließend geprüfter Eingang oder das abschließende Eingangsmanifest.
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

Die reinen Projektionen liegen in `work._snapshot_projection`: Das kanonische
Eingangsmanifest und die abgelösten Fortschrittsdaten erhalten ausschließlich
logische Dateneinträge und Skalare. Absolute Quellpfade, Prozessidentität,
Dateideskriptoren, native Sperren und laufende Hashobjekte bleiben im
Erfassungsadapter `work.snapshot`. Der öffentliche Task und seine Fehlerklasse
bleiben dort erreichbar; Datenfelder, Hashbytes und Fortschrittsgrenzen werden
durch diese Strukturtrennung nicht verändert.

Dies ist die erste aufteilbare Byte-Erfassung innerhalb derselben Invocation.
Der gesamte Objektspeicher und die deklarierte Menge liegen noch im Speicher;
die Blockgrenze ist keine Gesamt-RSS-Garantie. `close()` gibt offene Lesedeskriptoren
frei und erhält die erfassten Bytes im Taskobjekt. Fehler zählen die betroffene
Einheit nicht als erfolgreich, erhalten vorherige Daten und stoppen diesen Task.
Es gibt keinen automatischen Retry oder stillen Projektwrite.

Vor dem ersten Eingangsbyte erfasst der Task die vorhandenen nativen
Root-Inode-Mutexe aller deklarierten Quellen über `LockFiles`. Er erzeugt
keine Projekt-Sperrdatei und benötigt keinen Schreibzugriff auf die Quellen.
Mehrere logische Root-IDs derselben physischen Quelle teilen sich einen Mutex.
Die bestehenden Writer-, Recovery- und Operational-Sperren schließen diese
Erfassung gegenseitig aus. Die Sperren bleiben über `advance`-Aufrufe hinweg
gehalten und werden bei Versiegelung, Fehler oder `close()` freigegeben.
Native Linux-Sperren sind dafür erforderlich; ohne sichere Sperre gibt es
keinen ungeschützten Ersatzpfad. Ein Task ist nicht kopierbar; ein geerbter
Task darf im Fork-Kind weder fortschreiten noch den Elternprozess entsperren.

Unter diesen Sperren prüft der vorhandene flache Betriebsdaten-Preflight vor
dem Lesen und vor der Versiegelung auf offene Transaktionen und unklare
Betriebsdaten. Auch verwaiste Ownerdateien blockieren; der Task repariert oder
entfernt sie nicht. `SnapshotCaptureError` benennt Root-ID und, soweit bekannt,
den konkreten logischen Quell- oder Betriebsdatenpfad.

Die abschließende Validierungsphase öffnet jeden deklarierten Eingang erneut
über den sicheren Ressourcenadapter. Bei unveränderter Identität, Größe,
`mtime` und `ctime` bleiben die bereits erfassten Inhaltshashes maßgeblich;
ein unveränderter Präfix wird nicht nochmals gelesen. Veränderte Merkmale
lösen genau eine erneute blockweise Hashprüfung des betroffenen Eingangs aus.
Nur erneut nachgewiesene, hashidentische Bytes dürfen die vorhandene Bindung
bestätigen. Abweichender Inhalt, Quellverlust oder ein weiterer beobachteter
Wechsel verhindert die Versiegelung. Vorher erfasste Bytes bleiben verfügbar,
werden aber nicht still gegen neue Quellen ausgetauscht. `validated_inputs`,
`revalidated_inputs` und `validation_bytes` weisen diesen Fortschritt aus.
Die notwendige letzte Prüfung sämtlicher Dateimerkmalbindungen und Roots
gehört zur Abschluss-Einheit; das Arbeitsfenster ist keine harte Zeitgrenze.

`model_root_sha256` bleibt `null`, `atomic_project_snapshot` und
`durable_checkpoint` bleiben `false`. Die Erfassung einzelner Dateien bestätigt
keine vollständige normative Modellclosure. Kooperierende Writer sind während
der Erfassung ausgeschlossen; nicht kooperierende externe Dateibearbeitung
kann die Beobachtungen weiterhin überholen. Die Erfassung behauptet deshalb
keine atomare Dateisystemmomentaufnahme. Dauerhafte Generationen folgen in 6.l
und tatsächliche Wiederaufnahme in 6.m. Eine kleine
Arbeitsmenge erzeugt hier keinerlei Work-Dateien; auch bei größeren Eingängen
wird weder Code 8 noch eine veröffentlichte Checkpointgeneration behauptet.
