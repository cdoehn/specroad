# OFF-PLAN MIGRATION-BACKUP-561 — Quellsicherung und vollständiges 16.d

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN MIGRATION-BACKUP-561 — Quellsicherung und vollständiges 16.d

Gebundene Basis ist das erfolgreiche saubere Result 59223b,
SHA-256 `b9c3b129c4fbf9451df5acb3b4573f5394c38fb4156dc4cb3db8a073ac4fad1d`.
Die normale Detaillücke zwischen E.1.1 (0.2) und unveränderter 0.1-Sicherung
wird gemäß SPECROAD-DECISION-1/2.4.3.1 unter erteiltem Vertrag 4 in Q.5.1
begründet geschlossen. Alternativen und Grenzen stehen dort normativ.
Ein Klärungscommit zuerst, danach vollständiges 16.d.W/R/C; je ein echter
Zwischenstand mit eigenem N=3-plus-Pflichttests-Gate vor dem Commit.
Keine Verhaltenstests in Dev; vorbereitete Abnahmen sind keine Testerfolge.
Die Pflichtauswahl enthält alle neuen/geänderten Tests und die betroffenen
M15-/Quellleser-/Migrationsplan-/sicheren I/O-Regressionen.

W: kanonische Quellsicherung, vollständiger Dateibytebestand einschließlich
Legacy-/generierter/unreferenzierter Originale, externe atomare create-only
Veröffentlichung und gebundener Bericht. Unabhängige ZIP-Inventar-/Byte-
Orakel, Vollrekonstruktion, Wiederholbarkeit und unverändertes Quellschema.
R: externe Hash-/Bestandsbindung bei erneutem Öffnen, streng geschlossener
Quellmanifestvertrag, manipulierte/fehlende Bytes und historische Closure,
aktive/ungeklärte Betriebsdaten, Quellwechsel und No-space verhindern Erfolg.
C: Quellinventur und Quellcontainer strukturell trennen, gemeinsame M15-
Archiv-/Publikationsprimitiven weiterverwenden; alle R-Tests unverändert.
16.e behandelt anschließend explizite Sprach-/Verbindlichkeitsmigration;
diese separate Fachentscheidung wird nicht mit dem Sicherungsschritt vermischt.
16.i und spätere CLI-/Restoreintegration bleiben vollständig offen.

### Ausdrückliche Ergänzung CONTROL-PLAN-LIMIT-561

Der Nutzer ergänzt im laufenden, noch nicht übergebenen Bundle die Zulassung
entpackter Commitpläne bis 64 MiB. Diese zusätzliche technische Änderung
wird innerhalb derselben tatsächlichen W/R/C-Zustände von Bundle 561 geführt;
die Produktpositionen zählen weiterhin ausschließlich 16.d. Keine zusätzliche
Klärungsstage und kein Scope-/Budgetwechsel aus eigener Befugnis.
W ergänzt die eigene 64-MiB-Planobergrenze und echte komprimierte Planfälle
oberhalb 32 MiB, exakt 64 MiB und einen Byte darüber. R prüft kleinere Grenzen,
ungültige Grenzwerte und unvollständige/angehängte Streams, ohne fachliche
Planprüfungen zu lockern. C vereinheitlicht die bisher doppelte 64-MiB-Konstante
mit der vorhandenen Blocked-Recovery-Prüfung; R-Tests bleiben bytegleich.
Alle neuen Testdateien und die betroffenen Control-/Mixed-/Reconciliation-/
Recovery-Tests sind ungefiltert Pflicht. Dev führt weiterhin nur Collection,
Syntax und native Paketprüfung aus. Die Übergabe selbst bleibt unter der
bisher installierten 32-MiB-Grenze; die Codeänderung wirkt erst in einer
später tatsächlich installierten, erfolgreich geprüften Control-Version.
Kein Dienststart, keine Installation und kein Eingriff in Betriebsdaten.
