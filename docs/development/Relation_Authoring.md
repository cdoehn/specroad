# Native Relationsbearbeitung

`specroad.authoring.relations` verbindet Hinzufügen und Entfernen mit den
vorhandenen `relation_add`-/`relation_remove`-Operationen des gemeinsamen
Change-Plans. Der Dienst veröffentlicht echte Projektdateien. Er verlangt ein
ausdrücklich geladenes vollständiges `TargetModel` und eine
`PublicationAuthority`; CLI, Dry-run/stdout und allgemeine Modell-/Historien-
beladung sind noch nicht angebunden.

`add_relation(model, source_id, relation_type, target_id, inventory=..., ...)`
verlangt ein `RelationInventory` mit aktuellen, archivierten und reservierten
Relations-IDs. Die aktuellen IDs müssen mit dem gesamten Modell übereinstimmen;
dessen reservierte IDs müssen enthalten sein. Die Vollständigkeit der Historie
verantwortet der Host. Unter dem echten Writer-Lock vergibt der vorhandene
Allocator eine neue zufällige 128-Bit-Identität. Optional sind `rationale` und
`position`; Positionen gelten ausschließlich für `contains`. Neue Relationen
erhalten Akteur und Zeitpunkt sowie leere External-Identity-/Extension-Felder.
Typmatrix, Ziele, kanonische Richtung und weitere Graphregeln prüft der Kern.

`remove_relation(model, source_id, relation_id, expected_sha256=..., reason=..., ...)`
entfernt ausschließlich die bezeichnete Beziehung. Der ausdrücklich übergebene
Hash bindet das vollständige kanonische Relationsobjekt, nicht das Quellartefakt.
Andere Beziehungen bleiben erhalten. Für eine Wiederholung müssen ursprüngliche
ID, Hash und Grund erhalten bleiben; der Hash wird nicht aus einem späteren
Projektzustand neu abgeleitet.

Beide Funktionen erhalten dieselben ausdrücklichen Schreibparameter: `actor`,
`planned_at`, `change_plan_id`, `transaction_id`, `authority`, optional
`request_id`, `gates`, `strict` und `package_files`. Human und Tool dürfen ohne
Request-ID arbeiten; CI benötigt sie, direkte AI-Writes sind ausgeschlossen.

Vollständige Zielprüfung, Live-Prüfung, Journal, Staging, Veröffentlichung,
Abschlussbelege und Cleanup laufen durch die vorhandenen nativen Dienste.
Eine erfolgreiche Änderung erhöht die Quellrevision genau einmal und aktualisiert
deren Änderungsmetadaten. Die ursprüngliche Operation bleibt im Transaktionsbeleg
erhalten, beim Entfernen einschließlich Grund; dessen Journal bindet den Akteur.
Andere vorhandene Dateien und der Modus der Quelldatei bleiben erhalten.

Ein bestätigter Request wird vor neuer Planung oder ID-Vergabe anhand seines
vollständigen nativen Abschlussnachweises geprüft. Unter der Schreibsperre wird
die Prüfung wiederholt. Derselbe Auftrag liefert die ursprüngliche Relation-ID
und Transaktion zurück; abweichende Operationen dürfen denselben Request nicht
umdeuten. Der Replay-Beleg bestätigt keinen heutigen Zielzustand.

Das Ergebnis trägt `format_version: 1.0.0`, `command_id: relation.add` oder
`relation.remove`, `source_id`, `relation_id`, `write_state: committed`, `replayed`
und die native `completion`. Quellrevision oder aktueller Zielzustand werden aus
historischen Belegen nicht erfunden. Fehler erhalten tatsächlichen Schreibstatus
und Recovery-Journal; es gibt keinen automatischen Retry oder Rollback.

Die W-Abnahme verwendet echte lokale Draft-Modelle. Fehlende Lifecycle- und
Spezialdienste verhindern weiterhin eine Veröffentlichung, auch bei Proposed-
Quellen. Sie werden nicht durch Erfolgsstubs ersetzt. Vollständige Produktions-
und Historienbeladung, CLI/Dry-run/stdout, weitere Zustands- und Plattformnachweise
bleiben offen; SR-REQ-0233 und SR-REQ-0234 bleiben partiell.
