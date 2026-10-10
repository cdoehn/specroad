# Native Lifecycle-Bearbeitung

`specroad.authoring.lifecycle` veröffentlicht reine Standardübergänge und
Stilllegungen über den vorhandenen Change-Plan und Transaktionspfad. Der Host
liefert ein vollständiges `TargetModel`, eine `PublicationAuthority`, Akteur,
Zeitpunkt und Plan-/Transaktions-IDs. Die registrierte CLI, Dry-run/stdout und
allgemeine Produktions-/Historienbeladung bleiben noch offen.

`normalize_transition_input(artifact, to=..., reason=...)` bindet die ursprüngliche
Identität und den Ausgangsstatus an eine native `transition`-Operation. Der Grund
ist optional für Übergänge, deren Regel ihn nicht verlangt. Für `rejected` und
`retired` bleibt er Pflicht. Ausgang und Ziel müssen verschieden sein.

`normalize_retire_input(artifact, reason=..., expected_revision=...,
expected_sha256=...)` erzeugt eine native `retire`-Operation. Mindestens eine
Vorbedingung muss ausdrücklich vorliegen; bei zwei Vorbedingungen müssen beide
stimmen. `None` ersetzt keine ausgelassene Angabe. Ein veränderter Projektzustand
wird nicht zur Quelle neuer Vorbedingungen für einen alten Request.

`transition_artifact(model, operation, ...)` und
`retire_artifact(model, operation, ...)` erhalten die bereits normalisierte
Operation und dieselben Schreibparameter: `actor`, `planned_at`, `change_plan_id`,
`transaction_id`, `authority` sowie optional `request_id`, `gates`, `strict` und
`package_files`. Beide verwenden die bestehende Authoring-Policy für
`lifecycle transition`. Human und Tool dürfen ohne Request-ID arbeiten; CI
benötigt sie. Direkte AI-Writes bleiben ausgeschlossen.

Der Kern prüft die vollständigen Standardregeln und Pflichtangaben. Direkte
Übergänge auf Proposal, Evidence, Baseline und Relationsreview bleiben unzulässig.
Eine beantragte Freigabe erfordert weiterhin den echten Approval-Dienst; ein
Akteurstyp oder Übergangsmetadaten ersetzen ihn nicht.
Auch der Übergang eines Requirements nach `in_review` muss die vorhandene
formale Zielprüfung bestehen. Ein reines Draft-Fixture ohne erforderliche
Begründung, Herkunft und Verifikationsbeziehung genügt dafür nicht.

Die gebundene Lifecycle-Prüfung besitzt das ursprüngliche Modell und die native
Operation. Sie berechnet bei jeder Prüfung erneut den vollständigen Zielzustand
und vergleicht alle Artefakte. Sie deckt ausschließlich das Standardartefakt des
aktuellen Auftrags ab. Weitere Nicht-Draft-Artefakte und Spezialdienste benötigen
ihre echten semantischen Prüfungen. Ein ausdrücklich übergebener Lifecycle-Dienst
wird nicht durch diesen Adapter ersetzt.
Die Auswahl der übergebenen Prüfungen wird vor externen Lesezugriffen übernommen.
Eine später geleerte Aufruferliste entfernt damit keine anfängliche Host-Sperre.
Gebundene Nachweise gelten nur für den ursprünglichen vollständigen Zielzustand,
einschließlich Akteur, Zeitpunkt und unveränderter übriger Artefakte.

Writer-Lock, vollständige Zielprüfung, Live-Prüfung, Journal, Veröffentlichung
und Abschlussbelege verwenden die bestehenden nativen Dienste. Ein reiner
Übergang verändert nur den Reifegrad und abgeleitete Änderungsmetadaten; die
Fachprojektion bleibt erhalten und die Revision steigt genau einmal. Grund,
Ausgang und Ziel stehen in der ursprünglichen Operation; der Audit bindet Akteur
und Zeitpunkt. Es entstehen keine erfundenen Fachfelder für den Grund.

Ein neuer, gültig geschützter Retire-Auftrag für einen bereits stillgelegten
Zustand wird unter echter Sperre und Autorität erneut geprüft. Sein No-op erzeugt
keine weiteren Artefaktbytes, Journale oder Receipts. Ein bestätigter alter Request
wird dagegen vor neuer Planung oder Sperre als historisches Ergebnis gelesen.
Identische Operationen behalten auch bei anderem zulässigem Aufruferakteur den
ursprünglichen Audit. Der Replay bestätigt keinen heutigen Zielzustand.

Das Ergebnis enthält `format_version: 1.0.0`, `command_id: lifecycle.transition`,
`artifact_id`, die native `operation`, `no_change`, `write_state`, `replayed` und
`completion`. Ein No-op hat `completion: null` und `write_state: not_committed`.
Veröffentlichungsfehler behalten ihren tatsächlichen Schreibstatus und die
nativen Recovery-Daten; der Dienst startet weder Retry noch Rollback.

Reine Übergänge eines vorhandenen `approved`-Artefakts nach `proposed`, `retired`
oder `superseded` behalten das ausdrücklich gewählte Ziel und ändern die Revision
genau einmal. Bei `superseded` muss ein anderes Artefakt desselben Typs im
vollständigen Zielmodell eine eingehende `supersedes`-Beziehung besitzen;
eine ausgehende Beziehung oder ein Zyklus genügt nicht. Fehlende Gründe für
Ablehnung/Stilllegung, Rückkehr aus `retired` und veraltete Ausgangsstände oder
Retire-Vorbedingungen bleiben gesperrt. Auch ein frischer Retire-No-op prüft
beide ausdrücklich angegebenen Vorbedingungen und die aktuelle Host-Autorität.

Ein bestätigter Request darf weder seine ursprüngliche Operation noch deren
Ziel, Ausgang, Grund oder Vorbedingungen ändern. Ein anderer zulässiger
Retry-Akteur bleibt dagegen Teil des bereits beschriebenen historischen Replays.
Fremde Dateiänderungen und bestehende Writer-Sperren werden erhalten. Bei einem
I/O-Fehler vor oder nach tatsächlicher Dateiersetzung bleiben die wirklichen
Artefaktbytes und das native `committing`-Journal liegen; der unklare Schreibstatus
wird nicht in einen Erfolg oder einen automatischen Wiederholungsversuch umgedeutet.

SR-REQ-0218 und SR-REQ-0235 bleiben partiell. Die lokale Abnahme ist kein Nachweis
vollständiger Produktionshistorie, früherer Freigaben, registrierter CLI oder
aller unterstützten Plattformen. Die R-Fixtures mit einem strukturell gültigen
`approved`-Ausgangszustand belegen keine frühere fachliche Freigabe. Die gezielten
W-/R-Nachweise decken die beschriebenen lokalen Grenzen und unterbrochenen
Veröffentlichungen ab; die vollständige Approval-Anbindung bleibt offen.
