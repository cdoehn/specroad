# Bundle 705 — nativen Validierungsbefund im Schreibbeleg prüfen

Nutzerauftrag vom 15. November 2026: das fehlgeschlagene Bundle 704 reparieren.
Maßgebliche Quelle ist das native Fehler-Result mit SHA-256
`2568153ec079dd3e5da79b26d6d11bac903cf9588046bb0f336333225ec1a0ea`.
18.t.W ist auf `82367c4af5ff4193cb3c80af2e8f4dd9a6c25a3a` nach
8.144 bestandenen Tests erfolgreich committed und wird nicht wiederholt.
18.t.R scheiterte mit 41 Fehlern bei 8.327 ausgeführten Tests. Die übrigen
angekündigten Stufen wurden noch nicht ausgeführt. Der zurückgegebene
Arbeitsbaum entspricht exakt dem angekündigten R-Zustand.

Ursache: Die R-Prüfung des Transaktionsbelegs übergab den internen
`ValidationReport.data` an das Schema einer CLI-Validierungsbewertung.
Beide verwenden die Bezeichnung `model-validation-v1`, haben aber verschiedene
Felder. Der interne Befund enthält Prüfphasen und Quellenbindungen; die
CLI-Projektion enthält Diagnostik, Exitcode und `source_report`. Dadurch
brach ein gültiger Schreibabschluss mit `missing_field` vor den Receipts ab.
Das erklärt sowohl die fehlgeschlagenen Positivfälle als auch die nicht
erreichten späteren Sync-, Unlink- und Prozessabbruchstellen.

Die Reparatur prüft unmittelbar den vollständig gespeicherten nativen Befund:
Pflichtfelder, vollständigen Modellumfang, genaue Quellen-/ID-Bindungen,
erfolgreiche vollständige Prüfphasen und unveränderte Befugnisgrenzen.
Sie erzeugt keine ersatzweise erfolgreiche CLI-Ausgabe und führt beim
historischen Lesen keine neuen Fachprüfungen aus. Die echten Zielprüfungen,
Belegbytes, Hashbindungen und Dauerhaftigkeitsreihenfolge bleiben erhalten.
Die vorhandene positive Migration deckt weiterhin den nativen Befund mit
Legacy-/Dokumentmetadaten und echten Create-/Replace-/Delete-Wirkungen ab.

Sechzehn zusätzliche Eingabevarianten prüfen fehlende/widersprüchliche native
Befunde anhand einmalig nativ erzeugter unveränderlicher Belegbytes. Jeder
Fall dekodiert seine eigene Kopie und bindet den manipulierten Receipt-Hash
neu; eine Ablehnung darf nicht bloß an einem alten Hash scheitern. Bestehende
I/O- und Verzeichnistauschtests bestätigen zusätzlich, dass der jeweilige
Injektionspunkt tatsächlich erreicht wurde. Alte Testfälle, Varianten und
Assertions bleiben erhalten; alle im Result vorhandenen Testnummern bleiben
unverändert. Neue IDs werden je Stage ausschließlich angehängt.

Die vollständige offene Folge bleibt mit ihren ursprünglichen IDs und Rollen:
18.t.R, 18.t.C, TEST-OVERHEAD.W, TEST-OVERHEAD.R, TEST-OVERHEAD.C.
Die Reparatur gilt in allen fünf Zuständen. C behält seine reine strukturelle
Trennung. Die drei ausdrücklich beauftragten Testlaufoptimierungen bleiben
echte getrennte Folgestufen gemäß [Bundle 704](bundle-704-writer-fixtures-test-overhead.md).
Kein erfolgreicher Präfix wird wiederholt und kein Endstand vorab installiert.

Jede Stage erhält ihr eigenes gefiltertes N=3-Gate einschließlich vollständiger
Pflichtauswahl vor dem Commit. Dev führt nur Syntaxprüfung, reine Collection
und native Paketvalidierung aus; die Verhaltensabnahme ist noch offen.
Keine neue Spezifikationsklärung, Budgetänderung oder Wiederaufnahme von Control.
Die geplanten Produktzielwerte 767 beziehungsweise 768 von 918 gelten erst
nach dem jeweiligen erfolgreichen Gate; danach bleibt 18.u.W offen.
