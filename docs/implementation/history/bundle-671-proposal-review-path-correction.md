# Bundle 671 — Arbeitsverzeichnis und Projektbindung des Proposal-Reviews

11. November 2026. Native Quelle ist Fehler-Result 670 mit SHA-256
`228c5ef7471ca96ad4a0b6eded316ba199f70142e61edecd52cf333a3f3760b8`,
HEAD `5942700a4e579cf204b35fe55353e044f44e4be2` und vollständig erhaltenem
Arbeitsstand. Der exakte Commitumfang wurde akzeptiert; das Apply-Testgate
scheiterte anschließend vor dem Commit von 18.i.W. Kein neuer Commit entstand.
Der erfolgreiche Control-Präfix aus Bundle 668 bleibt vollständig erhalten.

Zwei Fehler sind im Ausführungslog und im maschinellen Gatebericht belegt:

- `test_argv_and_structured_review_share_real_host_context_and_dry_run_contract`
  erhält beim relativen Proposal-Dateipfad `CORE_ENVIRONMENT` statt Erfolg.
  Die Optionsauflösung übergibt das angegebene Arbeitsverzeichnis bereits für
  `proposal.review.start`, jedoch noch nicht für `proposal.review`. Deshalb
  sucht der Review-Eingang im Prozessverzeichnis statt im Aufrufverzeichnis.
  Die bestehende explizite Befehlsauswahl wird um den Reviewbefehl ergänzt.
- Der Unterfall `proposal.review` von `test_each_published_example_runs_the_actual_command`
  läuft erfolgreich, prüft aber den temporären Elternordner als Projektwurzel.
  Sein nativer Beispielaufbau wählt ausdrücklich das Unterprojekt `review-project`.
  Die Erwartung bindet jetzt den tatsächlich angeforderten Projektpfad; die
  übrigen Erfolgs-, Befehls- und Projekteigenschaften bleiben geprüft.

Der bestehende öffentliche Integrationstest behält seine Identität und prüft
argv sowie strukturierten Aufruf mit echter Hostkonfiguration in zwei Fällen:
automatische Projektsuche im Aufrufverzeichnis und ausdrückliche Projektauswahl
bei davon verschiedenem Aufrufverzeichnis. Relative Proposal-Dateien beziehen
sich jeweils auf dieses Aufrufverzeichnis. Beide Eingänge müssen gleiche
schema-gültige Dry-run-Ergebnisse liefern, ohne Proposalrevision, Projektdateien,
Journal oder Receipt zu verändern. Native Validatoren und Services bleiben aktiv.

Die Korrektur enthält den vollständigen offenen Rest 18.i.W/R/C mit denselben
IDs, Rollen und Commitnachrichten. Alle historischen Berichte bleiben bytegleich
zum Quell-Result. Die exakten Commitumfänge werden weiterhin gegen den jeweiligen
nativen Commit-Elternstand geprüft. Keine normative Klärung, Budgetänderung,
Dienstaktion oder Wiederholung bereits erfolgreicher Commits.

Dev prüft Syntax, stabile Testidentitäten, reine Collection und das native Paket;
es führt keine Testkörper oder Fixtures aus. Die gesamten geänderten Testdateien
und die betroffenen Options-, Bootstrap-, Request-, Proposal-, Writer-, Schema-
und Beispielregressionen gehören ungefiltert zum jeweiligen Apply-Gate zusätzlich
zur fälligen N=3-Gruppe. W, R und C bleiben echte getrennte Zustände, jeweils mit
Testgate vor dem Commit. Planfortschritte sind vorbereitete Zielwerte und gelten
erst nach erfolgreicher Apply-Abnahme. Lokale Konfigurationen, Zugangsdaten und
Sessionkennungen gehören nicht zur Payload.

Vorbereiteter Stagezustand: `R`. Apply-Abnahme steht aus.
