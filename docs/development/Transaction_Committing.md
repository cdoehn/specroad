# Committing und atomare Dateiveröffentlichung (5.m)

`publish_prepared_journal(preflight, prepared, held_lock=..., authority=...)`
setzt den überprüften Prepared-Zustand unter dem weiterhin gehaltenen nativen
Writer-Lock auf `committing`. Der exklusive Journalnachfolger wird vollständig
geschrieben, synchronisiert, atomar ersetzt und im Elternverzeichnis synchronisiert,
bevor irgendeine normative Datei veröffentlicht wird.

Die geänderten Artefakte werden in kanonischer Pfadreihenfolge veröffentlicht.
Jede Stagingdatei wird nach erneuter Hash-/Identitätsprüfung atomar ins zugehörige
Zielverzeichnis umbenannt. Bestehende einfache Unixmodi bleiben erhalten; neue
Dateien erhalten 0644, neue Elternverzeichnisse 0700. Geräte, Links und gefährliche
Modi werden nicht übernommen. Datei und beide beteiligten Verzeichnisse werden
synchronisiert. Kein Kopieren-und-Löschen-Fallback über Dateisystemgrenzen.

Erst nach erfolgreicher Zurückprüfung wird genau dieser Index mit seinem
bereits gebundenen Zielhash im Journal quittiert und synchronisiert. Eine
Folgedatei darf nicht vor diesem Abschluss veröffentlicht werden. Die
unveränderten Quellen/Ressourcen und bereits publizierten Dateien werden erneut
geprüft, ebenso Journal, Images, Eltern, Konfiguration, Root und Lock.

Am Ende werden sämtliche Zielartefakte tatsächlich zurückgelesen, die vollständige
Zielmodellwurzel erneut berechnet und die vorhandenen Fachprüfer ausgeführt.
Änderungen während dieser Prüfungen machen das Ergebnis ungültig. Autorisierung
ist ausdrücklich vertrauenswürdig registrierter Hostcode, kein Plandatenfeld.

**Anhang C.2 setzt Receipts vor `committed`.** Daher endet diese Schicht bewusst
bei `state=committing`, `published_count=len(files)` und nachgewiesener Zielwurzel.
`PublishedFiles` erklärt `receipt_written=false`, `commit_completed=false` und
`finalization_required=true`. Erst der folgende Receipt-Schritt darf die
Transaktion abschließen. Ein voll publizierter Bestand bleibt bis dahin für
normale Projektvalidierung/Schreibbefehle durch das aktive Journal gesperrt.
Diese Sperre ist keine Behinderung der späteren finalen Transaktion, sondern
verhindert Scheinerfolg während des Aufbaus ihrer noch fehlenden Infrastruktur.

Bei I/O-Fehlern, verlorenen Rename-Rückgaben oder Prozessabbruch bleiben Journale,
Before Images und verbleibende Stagingdateien erhalten. `publication_possible`
kennzeichnet möglicherweise schon wirksame normative Mutationen. Quittierungen
können dem tatsächlichen Dateistand bei Abbruch um eine Veröffentlichung
hinterherliegen. Kein Retry, Reset, Cleanup oder vorgetäuschter Rollback.
Die spätere Recovery muss anhand der tatsächlichen Hashes entscheiden.

Noch kein neuer CLI-Befehl, nativer vollständiger ChangeBackend, Anhangs- oder
Kontrollworkflow. Die Sperre gilt für kooperierende Schreiber auf dem lokalen
Linux-Dateisystem, nicht als OS-Sandbox oder Mehrdatei-Atomizität gegen fremde
Editoren. Stromausfallsicherheit wird nicht stärker als die darunterliegenden
fsync-/Rename-Garantien behauptet. Native ACL-/Eigentümerübernahme ist nicht
Bestandteil dieser Mode-Bindung.

Für die Testausführung gilt die lokale `AGENTS.md`; die technische Anleitung
steht in [Testing.md](Testing.md). Die Publikations- und Unterbrechungsfälle
bleiben fachliche Verhaltenstests innerhalb der Testsuite.

## Read-only inspection and failure evidence

`read_committing_journal(ProjectSource(root), transaction_id, expected_sha256=...,
preflight=...)` observes the acknowledgement prefix, all before images, remaining
staging images and the corresponding old/new target bytes. It rechecks the exact
namespaces, original journal bytes and file identities. It never acquires a writer
lock, makes a receipt, resumes a move, deletes a pending journal or upgrades a
state. With a preflight it also independently checks the full original inventory.

An unacknowledged move is **not** guessed into an acknowledgement: the reader
rejects that inconsistent observation and leaves recovery to the later workflow.
Even an entirely published, hash-correct target remains blocked by the active
`committing` journal. Receipt persistence must precede `committed` (C.2).

The regression corpus injects failures at every file/journal fsync boundary of a
two-target publication, lost rename/acknowledgement returns, short writes, replaced
images and changed unrelated sources. A real child exits immediately after the
first target rename: the mixed files and before images remain, and normal project
loading remains blocked. These are observed process/failure tests, not a simulation
of power loss or an assertion about remote/distributed filesystem durability.

## State ownership

The pure `_committing_state` successor table determines the next canonical target
from the current acknowledged prefix. The native publisher cannot advance to the
next target until its newly persisted journal has advanced that prefix. Receipt
and committed successors remain absent rather than fabricating finalization.
