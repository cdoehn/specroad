# Native Relationsreview-Erzeugung

`specroad.authoring.reviews.record_relation_review` ist ein Einbettungsdienst
für einen menschlichen `confirmed`-Review. Der Host liefert das vollständige
`TargetModel`, die historische `IdentityInventory`, Akteur, gebundene Zeit,
Plan-/Transaktions-ID und `PublicationAuthority`. Mindestens eine explizite
Quellrevision oder ein vollständiger Quellhash ist erforderlich. Diese Guards,
Begründung und optionaler Kommentar gehören zur Operationsbindung.

Die Review-ID entsteht unter dem nativen Writer-Lock. Der unveränderbare
Datensatz bindet Relations-ID und Relationsinhaltshash sowie `source_id`,
`target_id`, beide `*_revision`, `*_artifact_sha256` und `*_context_sha256`.
Er enthält `context_hash_algorithm=relation_context_hash-v1`, menschlichen
Reviewer, Entscheidung, `reviewed_at`, Begründung und optionalen Kommentar.
Reguläre Erzeugungsmetadaten und `reviewed_at` verwenden die gebundene Zeit;
diese wird nach vorhandenen Reviews derselben Kontextbindung angeordnet.

Vor Lock und ID-Allokation prüft der Dienst bereits das vollständige gelieferte
Artefakt-/Relationsinventar, die strukturelle Beziehung und die expliziten
Quellguards. Bekannte historische IDs müssen im Allokationsinventar enthalten
sein; reservierte und archivierte IDs bleiben ausgeschlossen. Diese frühe
Prüfung ersetzt keine Live-Prüfung: Zielvalidierung und tatsächliche Dateibytes
werden an den bestehenden Publikationsgrenzen weiterhin erneut geprüft.

Die reinen Funktionen für Kontextbindung, Zeitordnung und Record-Erzeugung
liegen in `specroad.changes.review_record`. Ihre bisherigen Importpfade
über `specroad.changes.reviews` bleiben erhalten. Dieses Modul übernimmt
weiterhin Planprüfung und gebundene Validierungs-Gates; Writer und
Publikationsabschluss bleiben im nativen Authoring-Dienst.

Der spezielle Target-Planner rekonstruiert den Datensatz auch bei gespeicherten
Plänen vollständig. Er erlaubt genau eine isolierte Reviewoperation. Er legt
Revision 1 und `recorded`/`approved` fest, ohne Endpunkte zu verändern oder
Artefakte freizugeben. Generisches Create, Update und Lifecycle bleiben für
Reviews gesperrt. Die zusätzlichen Felder sind im passiven Leseschema optional,
damit ältere lokale Feldfixtures lesbar bleiben; für neue Reviewwrites prüft
der spezielle Planner den vollständigen, exakt rekonstruierten Datensatz.

Der Dienst verwendet die vollständige Zielvalidierung und die nativen
Preflight-, Journal-, Publish-, Receipt- und Cleanup-Dienste. Der native Receipt
enthält die neue Review-ID in `created_ids`. Ein bestätigter
Request wird anhand seines vollständigen Commit-Belegs ohne erneute Allokation
wiedergegeben. Eine geänderte Begründung, Kommentar- oder Guardbindung erzeugt
einen Request-Konflikt. Ein historischer Replay behauptet keinen erneut
geprüften aktuellen Projektzustand.

Die mitgelieferten Lifecycle-/Currentness-Gates zertifizieren ausschließlich
den neu gebundenen positiven Review. Weitere Reviewhistorie oder andere
Lifecycle-/Currentness-Subjekte können sie nicht bestätigen und blockieren
den Write. Allgemeine Statusauswahl folgt in 7.h, negative Bewertungen mit
gekoppelten Freigaberücknahmen in 7.i. Der Dienst enthält keine neue CLI,
Produktionsinventur, Akteurauthentifizierung oder globale Prüf-Ausnahme.
Fehlende Dienste und fehlgeschlagene Prüfungen bleiben geschlossen; native
Recovery-Belege und tatsächliche Fehlerzustände bleiben erhalten.
