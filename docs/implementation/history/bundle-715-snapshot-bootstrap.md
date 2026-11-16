# Bundle 715 — gemeinsame Snapshot- und Bootstrap-Abbruchsperre

## Bindung und bestätigter Ausgangspunkt

Result 714, SHA-256 `549822fd1a4ae371d1c5049bae982265062f05bd9759209915ccd9d9818f9921`,
bestätigt 18.u.C nach 15.532 bestandenen Tests. Ausgangscommit ist
`6d11762a3df0b6a8435178eff2d26af270c286f8`, sauberer Stand 771/918.
Es gibt keinen offenen Korrekturrest und keine wiederholten erfolgreichen Commits.
Die konkrete Nutzerentscheidung und normative Präzisierung stehen in
[BOOTSTRAP-SNAPSHOT-715](../decisions/bootstrap-snapshot-715.md).

## Vollständige Zustände

1. `BOOTSTRAP-SNAPSHOT-715`, role clarification: SR-REQ-0003 und die konsistente
   Root-Freigabegrenze, vollständige Snapshot-/Backup-Receiptbindung sowie
   zwei zielgebundene Elternmarker. Keine Produktwirkung in diesem Präfix.
2. `18.v.W`, role implementation: Migration/Merge benutzen den gemeinsamen
   dauerhaften Writer und normale v2-Receipts mit vollständiger Qualifikation.
   Init, Bundleextraktion und Sandbox schützen schon die erste Rootwirkung.
   Nach Fehlern bleiben tatsächlicher Teilbestand und Sperrbelege erhalten;
   normale vollständige Erzeugung, passive Erfolgswiederholung und ein neues
   unabhängiges Ziel bleiben möglich. Echte native Prozessabbrüche und alle
   dreizehn Migrationsdateiwirkungen erhalten eigene Verhaltenstests.
3. `18.v.R`, role implementation: frische Backup-/Original-/Autoritätsprüfung,
   veränderte Marker/Owner/Inputs, Receiptfälschung, Parent-/Rootwechsel und
   Sandbox-Innerroot-Sperre. Normale Completion-/Historyleser werden aus den
   Recoverymodulen gelöst; die alten Spezial-Reparatureinstiege sind gesperrt.
4. `18.v.C`, role implementation: ausschließlich Struktur; obsolete ausführbare
   Spezialjournal-/Rollback-/Bootstrap-Replayzweige werden entfernt. Gemeinsame
   Writer- und passive Abschlussprimitiven bleiben erhalten. Alle Testdateien
   und stabilen Testnummern sind gegenüber R bytegleich.

Dieser Snapshot beschreibt `18.v.W`. Ziel nach dessen Gate: 772/918;
nächster Plancommit `18.v.R`.
18.v wird vollständig geliefert. Die nächste eigenständige Gruppe 18.w
(öffentliche Recovery-/Restore-Work-Entfernung) bleibt unverändert offen;
es wird kein vorsorglich verkürzter Teil dieser Gruppe angekündigt.

## Abnahme und Grenzen

Dev führt keine Testkörper oder Fixtures aus. AST-/Importprüfung, reine
Collection, Katalogbindung und native Paketvalidierung sind keine
Verhaltensabnahme. Jede Stage erhält ihre eigene vollständige Pflichtauswahl
plus die fällige gefilterte N=3-Gruppe, bevor Apply ihren Commit erzeugt.
Alle neuen/geänderten Testdateien und deren transitive Fixtureverbraucher
sowie positive Migration/Merge, Verify, Init, Bundle, Sandbox, Work,
Original-/Backup-/Receipt-/Lock-/Pfadsicherheitsregressionen sind Pflicht.
Historische Wiederherstellungstests bleiben über ihre unveränderten Nummern
reserviert; aktive Zuordnungen binden die neuen Sperroracles. Unveränderte
positive Fach- und Sicherheitsoracles werden nicht abgeschwächt.
Kein neuer Vollsuite-, Release-, Human-Review- oder Plattformnachweis entsteht
durch diese vorbereiteten Zustände. Originale, Historien und fremde Dateien
bleiben geschützt; keine Dienste, Apply-Instanzen oder lokale Konfigurationen
werden durch die Vorbereitung geändert.
