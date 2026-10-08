# Native Writer-Grenzen – 5.v.W

`tests/support/writer_boundaries.py` führt den vorhandenen nativen Writer in
einem eigenen Interpreter aus. Ein Testadapter beobachtet echte erfolgreiche
`fsync`, `mkdir`, `replace`, `rename`, `link`, `unlink` und `rmdir` innerhalb
der Journal-, Staging-, Veröffentlichungs-, Receipt- und Cleanup-Phasen.
Die Produkt-APIs erhalten keinen Fehlerschalter; Projektkonfiguration und
Umgebungsvariablen können diese Testhilfe nicht einschalten.

Ein vollständiger Kontrolllauf ermittelt alle tatsächlich erreichten Grenzen.
Jeder dieser Punkte wird in einem frischen temporären Projekt wiederholt und
unmittelbar nach dem nativen Aufruf mit `os._exit(23)` beendet. Damit laufen
keine Python-Finalizer oder Lock-Cleanup-Routinen des gestoppten Writers.
Der Folgeprozess erhält ausschließlich den Rootpfad. Er liest Journal,
Ownership-Record, Images und Receipts neu und verwendet die vorhandenen
gebundenen Recovery-APIs mit ausdrücklich erteilter Testhost-Autorität.

Der W-Ausschnitt ändert ein vorhandenes Artefakt und erhält ein zweites sowie
eine fremde Nutzerdatei. Nach jedem Stopp werden das vollständige normative
Byteinventar und die unabhängig neu berechnete Modellwurzel gegen die vor dem
Write gebundene Basis beziehungsweise das vollständige Ziel verglichen.
Recoveryfähige Journale müssen mit einem freien Transaktionsgate abschließen.
Ein früher Abbruch vor dem ersten vollständigen Journal bleibt bewusst gesperrt:
Die exakte Basis und alle Betriebsnachweise bleiben erhalten, und der
Preflight darf keine erfolgreiche Recovery oder neue Schreibfreigabe behaupten.
Ein solcher Fall zählt nicht als abgeschlossene Recovery.

Die Matrix erfasst auch das bereits synchronisierte `journal.next` vor dessen
Ersetzung des aktiven Journals. Recovery prüft diese Datei als vollständigen
oder begonnenen, exakt ableitbaren Writer-Nachfolger. Sie übernimmt daraus
keinen Fortschrittszähler: Der tatsächliche Modellstand entscheidet weiterhin
über Discard, Rollback oder Zielabschluss. Das gebundene Derivat bleibt mit
seinen Originalbytes im Recoveryarchiv. Unpassende Bytes, ein anderer Cursor,
Überlänge, Symlinks, Hardlinks oder Änderungen während der Autorisierung
verhindern den Abschluss. Dieser W-Stand bindet den initialen Nachfolger und
die letzte Ein-Datei-Bestätigung; Zwischenbestätigungen bei Mehrdateiwrites
gehören zur R-Erweiterung.

Die Nachweise betreffen reale Prozessabbrüche auf dem aktuell geprüften
Linux-Dateisystem. Sie simulieren keinen Stromverlust und belegen keine
Dateisystem- oder Plattformmatrix. Mehrdateiwrites, verlorene Receipts und
wiederholt unterbrochene Recovery gehören zum anschließenden R-Zustand.
Die übergreifende Kunden-/Restore-Matrix bleibt den weiteren Planpunkten
zugeordnet; `SR-REQ-0261` erhält einen partiellen Verhaltensnachweis.
