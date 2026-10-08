# Native Writer- und Recovery-Grenzen – 5.v.W/R

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
die letzte Ein-Datei-Bestätigung. R ergänzt Zwischenbestätigungen bei
Mehrdateiwrites: Auch während des Rückwärtscursors bleibt der ursprüngliche
Vorwärtscursor über den gespeicherten Ausgangshash gebunden. Recovery prüft
das unverändert erhaltene `journal.next` vor und nach Autorisierung sowie vor
jeder Veröffentlichung und erhält es im Abschlussarchiv.

## R-Matrix

Die Mehrdateivariante ändert zwei vorhandene Artefakte, erzeugt ein weiteres
und erhält einen unveränderten Datensatz sowie die Nutzerdatei. Wiederum wird
jede tatsächlich beobachtete Writer-Grenze unterbrochen. Während einer
Teilveröffentlichung muss der schreibfreie Transaktionspreflight sperren;
nach Recovery muss das Byteinventar exakt Basis oder vollständiges Ziel sein.
Ein zurückgenommenes neues Artefakt bleibt als `.removed` im Recoveryarchiv.

Bei einem vollständigen Ziel vor dem `committed`-Marker werden fehlende
Transaktions-/Requestreceipts aus dem gebundenen Journal bytegleich ergänzt.
Ein beschädigter bestätigter Receiptbestand nach diesem Marker bleibt
unter Erhalt von Ziel und Nachweisen gesperrt und ist kein stiller Reparaturfall.

Die Recoverymatrix beginnt jeweils mit echtem gestopptem Writer im
unveröffentlichten, teilweise veröffentlichten oder vollständigen Zielzustand.
Ein Kontrolllauf erfasst alle nativen Grenzen einschließlich Ownership-Transfer,
anonymer Dateistaging-Schritte, Receipts und Archivierung. Für jede Grenze
folgt ein neuer Abbruch, danach ein weiterer Abbruch der folgenden Recovery.
Ein letzter frischer Prozess muss den gebundenen Zustand abschließen und das
Transaktionsgate freigeben. Dynamische Auditkennungen und anonyme Inoden werden
ausschließlich in den Testbeobachtungen als Pfadrollen abgebildet; sämtliche
echten Dateisystemoperationen und Produktbindungen bleiben aktiv.

Die Nachweise betreffen reale Prozessabbrüche auf dem aktuell geprüften
Linux-Dateisystem. Sie simulieren keinen Stromverlust und belegen keine
Dateisystem- oder Plattformmatrix.
Die übergreifende Kunden-/Restore-Matrix bleibt den weiteren Planpunkten
zugeordnet; `SR-REQ-0261` erhält einen partiellen Verhaltensnachweis.
