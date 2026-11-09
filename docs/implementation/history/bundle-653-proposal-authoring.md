# Bundle 653 — Proposal-Authoring und Endzustandsgrenzen

9. November 2026. Quelle ist das vollständig geprüfte erfolgreiche Result
`70edad2f97c6a352525492aae2e05f42bf7c64da01112e307ac8c620a8228d28`, Base-Commit `3953ebd1277fbec14feee08b681eeb5efdca9841`.
Bundle 652 schloss 18.d.R mit 7.959 und 18.d.C mit 7.988 bestandenen ausgewählten
Tests sauber ab. Es verbleiben keine offenen Stages dieses Bundles. Bestätigt
sind 741/900 Positionen; diese Commits werden nicht wiederholt.

Die vorhandenen Abschnitte 10.3 und 11.10 bestimmen Authoring, offene Zustände,
No-op und Endzustände bereits. Keine neue Detailklärung und keine Änderung von
Spezifikation, Projektbefugnis oder Klärungsbudget. 18.e.W/R/C setzt die
vollständige fachliche Bearbeitung der vier geordneten Änderungsoperationen um.

## Umsetzung und Abnahme

`prepare_proposal_change` verbindet add/update/remove/move mit dem gemeinsamen
normative_write-Authoringvertrag und der nativen ProposalRevision. Ein kompletter
ChangePlan samt Ergebnissen und Zielhash ist erforderlich; Identitäten bleiben
stabil. Ein Inhaltswechsel setzt offene Proposals atomar im Kandidaten auf
status/maturity draft und erhöht physische und Inhaltsrevision jeweils einmal.
Erstellungsaudit, Basis, vorhandene Reviews und Kontrollhistorie bleiben erhalten.
Die erwartete Revision bezeichnet die physische Revision, nicht content_revision.

Der Native-Model-Adapter rekonstruiert die tatsächlichen geordneten Operationen,
Lifecycle und Metadaten gegen die vollständige Basis und vergleicht die erklärten
Artefakte und den Zielroot. Kleine vollständige Projekte belegen alle vier
Operationen in Folge, einschließlich der Reihenfolge zweier Updates desselben
Ziels. Ein Integrationsfall qualifiziert eine echte native Reviewhistorie mit
explizit synthetischen menschlichen Entscheidungen vor und nach Inhaltsänderung:
die Historie bleibt gültig, ihre alte Freigabebindung wird unwirksam. Ein zweiter
Integrationsfall erhält die aktuelle Freigabewirkung bei einem echten No-op.

R lehnt terminale und unvollständige Reviewzustände, stale Revision und untypisierte
Auditwerte vor der Identitätsziehung ab. Zusätzliche oder fehlende Aktionsparameter
werden nicht still ignoriert. Unveränderte Updates/Moves erhalten Originalbytes,
Status, beide Revisionen und Audit ohne neue CHG-ID. Ein neues Vorhaben nach
rejected/stale/applied wird mit einer separat zugeteilten Proposal-ID begonnen.
Die gemeinsame Policy verlangt bei AI/CI einen stabilen Request-ID für normative
Schreibaufrufe; ein Dry-run bleibt Preview ohne Receipt- oder Schreibbefugnis.

C verwendet gemeinsame Eingangswachen für Authoring und Revisionsbildung und
führt die physische Auditfortschreibung mit der vorhandenen Change-Plan-/Writer-
Metadatenpolicy zusammen. Die bestehenden Lifecycle- und Zeitregeln bleiben
unverändert. Kein neues Fachverhalten; W-/R-Testbytes bleiben in C bytegleich.

Diese APIs bereiten owned Vorher-/Nachherwerte vor. Sie sind weder ein Writer
noch ein Authentifizierungs-, Idempotenz- oder Publikationsnachweis. Die tatsächlichen
Quellbytes müssen vom späteren publizierenden Host unter Sperre erneut geprüft
werden. Öffentliche Befehlsregistrierung, Kontrollprüfungen, Review-/Apply-Writer
und der komplette öffentliche Ablauf behalten ihre folgenden M18-Gates. Aktive
Requirements bleiben deshalb partial; keine Behauptung eines vollständigen
CLI-/Transaktionsabschlusses. Bereits bestehende Katalogabnahmen bleiben erhalten.

## Übergabe

Vorbereiteter W-Zustand: Die Fortschrittswerte gelten erst nach dem
erfolgreichen eigenen Apply-Gate und Commit. R und C bleiben bis zu ihren eigenen Gates offen.

Dev hat keine Verhaltenstests ausgeführt. Syntax und reine Collection sind
keine bestandene Verhaltensabnahme. Die drei echten Zwischenstände besitzen je
einen eigenen Apply-Testplan: gefilterte fällige N=3-Gruppe plus ungefilterte
Pflichtunion vor ihrem Commit. Alle neuen/geänderten Testdateien, Proposal-,
Restore-, Authoring-, Plan-/Fold-/Lifecycle-/Metadaten- und die übrigen betroffenen
Regressionen sind Pflicht. Alte Testnummern und historische Berichte bleiben
unverändert; neue Testnummern werden angehängt. Nach atomarer Übergabe endet
der Auftrag ohne eigene Apply-, Status- oder Warteschleife.
