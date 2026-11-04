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

Die gemeinsamen Recovery-Einstiegspunkte erkennen das neue Journal explizit.
Voller Journalhash, Originalbackup, native Ownerbindung und RecoveryAuthority
sind Pflicht. Vollständig publizierte Targets werden quittiert, unvollständige
Präfixe vollständig auf Source zurückgeführt. Alle Intents und Workbytes werden
atomar archiviert; keine neue Transaktion wird automatisch gestartet. Reale
tote Writer benötigen weiterhin den bestehenden expliziten Owner-Takeover.
Die Sourcepolicy erteilt keine automatische Recoveryfreigabe.

Ein identischer Request liefert nur nach vollständiger historischer Receipt-
Prüfung das gespeicherte Ergebnis und behauptet keine heutige Zielgültigkeit.
Ein neuer Request am erreichten Schema endet ohne Revision oder Receipt als
not_required. Ein Requestkonflikt und eine beschädigte Historie bleiben Fehler.

Es wird weiterhin kein öffentlicher 0.1-Migrationspfad registriert. Die noch
offenen historischen Detailberichte, migrate verify, öffentliche CLI und
Restore-Integration bleiben in 16.j/k/l. Synthetische Autorität und Daten in
Tests sind keine echten Reviews oder Risikoakzeptanzen. Collection, AST- und
Bundleprüfung sind keine Verhaltenstestabnahme. Jede Phase erhält durch
Apply ihr eigenes N=3-plus-Pflichtauswahl-Gate vor dem Commit.
