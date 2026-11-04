# Migrationstransaktion

apply_migration_plan nimmt exakte native Planbytes, erwartete Plan-/Input-/
Zielbindung, eine explizite Transaktions-ID und die tatsächliche externe
Quellsicherung entgegen. Der Host registriert PublicationAuthority und echte
zusätzliche ModelGates. Fehlende Fachprüfungen ergeben keinen Erfolg. Die
Bibliothek qualifiziert die vollständigen Sourcebytes, berechnet den Plan
nativ erneut und prüft alle Zielartefakte über den gemeinsamen Validator.
Unveränderbare qualifizierte Legacy-Originale behalten ihre Bytes, Source-
Schemas und Hashdomänen; sie erteilen keine aktuelle Reviewfreigabe.

Der bestehende Writerlock und derselbe aktive Transaktionsnamensraum schützen
den geschlossenen schema-transition-journal-v1-Zweig. Vor prepared liegen
Original-ZIP, alle Beforeimages und alle geänderten Targetimages dauerhaft
vor. Erst dann werden die tatsächlichen Dateieffekte einzeln atomar und mit
fsync veröffentlicht. Die Konfiguration wird nicht vorab installiert. Die
normalen Leser bleiben bei jedem offenen Journal gesperrt. Neue Archive
verwenden dieselbe descriptorgebundene Bildprüfung mit atomarem No-Replace;
alte v1-Transaktionen behalten ihr bisheriges Protokoll.

Mode-, Datei-, Eltern-, Plan-, Sicherungs- und Autoritätswechsel brechen ab.
Unbestätigte Publikation wird niemals als sicher unveröffentlicht gemeldet.
Der Writer startet keine automatische Wiederholung oder Rückführung.
Die echte externe Sicherung muss bis zum vollständigen Abschluss erhalten
bleiben; der historische Receipt bewahrt zusätzlich seine eigenen Originale.

Die vollständige Wiederaufnahme über die gemeinsamen Recovery-Einstiegspunkte
und der dauerhaft geprüfte Request-Replay folgen in 16.i.R. Offene Journale
bleiben bis zur ausdrücklichen Recovery blockierend.

Es wird weiterhin kein öffentlicher 0.1-Migrationspfad registriert. Die noch
offenen historischen Detailberichte, migrate verify, öffentliche CLI und
Restore-Integration bleiben in 16.j/k/l. Synthetische Autorität und Daten in
Tests sind keine echten Reviews oder Risikoakzeptanzen. Collection, AST- und
Bundleprüfung sind keine Verhaltenstestabnahme. Jede Phase erhält durch
Apply ihr eigenes N=3-plus-Pflichtauswahl-Gate vor dem Commit.
