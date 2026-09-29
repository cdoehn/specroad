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

Lokal werden nur neue und unmittelbar betroffene Verhaltenstests parallel mit
vier Workern ausgeführt. Volltests bleiben in GitHub, jedes fünfte Bundle
zusätzlich seriell mit Vergleich. Keine Darstellungstests, keine neuen Timeouts.
