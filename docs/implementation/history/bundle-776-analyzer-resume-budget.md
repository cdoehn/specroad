# Bundle 776 — hostunabhängige Resume-Abnahme

Das native Fehler-Result von [Bundle 775](bundle-775-analyzer-correction-measurements.md),
SHA-256 `1b368fcef7cce901c9e7ff5e58444f1f62b8a84a6e92983c35a668168a9a1a6e`,
belegt 9.076 bestandene und einen fehlgeschlagenen Test in 19.w.W.
Kein Implementierungscommit entstand. Der erfolgreiche Klärungscommit bleibt
erhalten; der gesamte offene Rest 19.w.W/R/C und 19.x.W/R/C folgt mit denselben
IDs, Rollen, Commitnachrichten und getrennten Apply-Gates.

Der Modelllebensdauer-Test erwartete einen vollständigen einzelnen Resume-Aufruf,
nutzte dafür aber die echte CPU-/Wall-Clock. Der native Lauf lieferte Code 8;
die Call-Phase dauerte 21,702569850 Sekunden. Der Produktionspfad darf nach
Überschreiten des weichen Schrittziels (standardmäßig 10 Sekunden Wall-Clock)
an einer sicheren Grenze einen Checkpoint und Code 8 liefern (O.1/O.4).
Dieser Test ist keine Laufzeitabnahme und darf nicht von der Hostgeschwindigkeit
abhängen. Die Vorbereitungsdiagnose verbindet den belegten Exitcode mit dem
statisch geprüften einzigen Fortsetzungspfad; sie ersetzt keinen Apply-Test.

Nur die Testaktion `finish` erhält jetzt über den bereits vorhandenen typisierten
`WorkConsumption`-Eingang einen explizit als Testzähler gekennzeichneten festen
CPU-/Wall-/RSS-Sample. Damit beschreibt der Test ein noch offenes Zeitfenster.
Er ersetzt weder Parser, Modell, Workerkanal, Validierung, native Checkpoints
noch das fachliche Ergebnis. Die ursprünglichen Assertions und Test-IDs bleiben:
vollständige Coverage, genau ein Modell pro Resume und genau eine Berechnung
je Subject. Eine Assertion zeigt bei erneutem Fehler zusätzlich das Resultobjekt.
Der erzwungene Pausenstart, echte neue Prozesse an jeder dauerhaften Grenze,
fünf CPython-Versionen, Wiederaufruf sowie sämtliche Hostfehler bleiben erhalten.

Alle produktiven Quellbytes und Budgets bleiben pro Stage unverändert gegenüber
der entsprechenden Vorbereitung aus Bundle 775. Daher bleiben auch die drei
nativen Buildkennungen und sämtliche echten Messbelege bytegleich gültig.
Die Ressourcenprüfung verwendet weiterhin reale Messungen; Testzähler sind
keine Ressourcenmessung. Keine neue normative Entscheidung, kein neues Review
und keine vorweggenommene Abnahme. 19.t und menschliche Korpusreviews bleiben
vor 19.y offen. Erst das eigene erfolgreiche Apply-Gate erlaubt jeden Commit.
