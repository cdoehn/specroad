# Lesende Befehle und Prozessfortsetzung

`artifact show` (Alias `show`), `query`, `trace`, `why`, `impact` und `diff`
besitzen gemeinsame Runtime-Zeitfenster und maschinenlesbare Resultatverträge.
Alle sechs lesen das Projekt ohne Cache-, Lock- oder Modellschreibzugriff.
Die vorhandenen fachlichen Kerne und deren begrenzte Validierung bleiben
maßgeblich; ein Leseergebnis erteilt keine Modellfreigabe.

```sh
specroad query --project /path/project --type requirement --owner team-a --limit 100 --format json
specroad query --project /path/project --filter /path/filter.json --select /title --sort title:desc
specroad diff --project /path/project --against HEAD --format json
specroad diff --project /path/current --against /path/before --against-kind local --format json
specroad trace SR-REQ-00000000000000000000000001 --direction out --depth 3 --step-wall-ms 1 --metrics
```

Query wertet das gesamte aktuelle Artefaktinventar aus. Wiederholte Werte eines
Filters bilden eine Oder-Verknüpfung; verschiedene Filter und explizite
SRX-JSON-Dateien werden mit Und verknüpft. `--filter` bezeichnet eine Datei,
keinen Ausdruck als Shell-Argument. Relative Filterpfade und eine explizite
lokale Diff-Basis beziehen sich auf das Arbeitsverzeichnis des Aufrufs.
`--offset` und `--limit` bilden erst nach vollständiger Auswahl und Sortierung
die Seite. `total` bleibt die exakte Trefferzahl. Ohne explizites Limit gilt
`resource_limits.query_default_limit`, sonst 100. `query_result_count` begrenzt
die fachliche Auswahl nicht heimlich. Profilabhängige Query-Defaults,
Release-, Evaluation- und berechnete Verifikationsprovider sind noch offen;
entsprechende nicht verfügbare Abfragen scheitern ausdrücklich.

Diff verwendet standardmäßig eine fest aufgelöste Git-Objektbasis. Bei
`--against-kind local` wird eine explizite zweite lokale Quelle gebunden.
Projektkonfiguration und Artefakte werden nach den vorhandenen semantischen
Vergleichsverträgen verglichen. Unterschiedliche Projekte oder noch nicht
interpretierte normative Ressourcenänderungen erzeugen keinen scheinbar
vollständigen Vergleich. Fehlende Git-Referenzen werden nicht durch aktuelle
Dateien ersetzt. Baseline-, Bundle- und Adapterquellen bleiben offen.

Die Python-APIs `show_artifact`, `query_project`, `trace_artifact`,
`why_artifact`, `impact_artifact` und `diff_project` liefern `CommandResult`.
`query_project` akzeptiert eine `NormalizedQuery`; `diff_project` verlangt die
explizite Basis und optional `against_kind='local'`. Die Query-Seite verwendet
`artifact-query-v1`, der vorhandene semantische Diff `artifact-diff-v1`.

`ReadCommandWork(command_id, root, **arguments)` hält geladene Eingaben und die
Berechnung prozesslokal. `advance(units=1, call=None)` arbeitet die Phasen
Laden, Auswerten und abschließende Aktualitätsprüfung ab. Erst nach Abschluss
ist `result` verfügbar. `state` meldet Phase und abgeschlossene Einheiten;
`finished` sagt aus, dass der Befehlsvertrag vorliegt, nicht dass dieser
erfolgreich war. Kontextmanager oder `close()` geben den Iterator frei.
Ein optionaler aktiver `WorkConsumption`-Aufruf beobachtet jede Phase. Nach
Überschreitung eines weichen Ziels kehrt `advance` am nächsten Phasenende
zurück; der Host kann mit einem neuen Messfenster fortsetzen. Synchrone
Python- und CLI-Aufrufe treiben denselben Produzenten vollständig weiter.

Die drei Phasen sind jeweils unteilbare Einheiten. Laden, native Berechnung,
Sortierung, Projektion und abschließende Nachprüfung können ein weiches Ziel
überschreiten; Eingaben und Ausgabe werden weiterhin materialisiert. Es gibt
keine harte Zeit- oder Speichergrenze und kein Abschneiden des Fachumfangs.
`--resource-profile`, CPU-/Wall-, Memory-/Scratch- und Schrittziele werden nach
`runtime-budget-v2` geprüft; `--metrics` ergänzt ausschließlich die tatsächlich
gemessene Runtime-Zusammenfassung. Ausgabelieferung ist darin nicht enthalten.

Dies ist kein persistiertes Work-v1-Checkpoint, keine CLI-Fortsetzung mit
Exitcode 8 und kein atomarer Snapshot gegenüber unkoordinierten Schreibern.
Gebundene Projekt- und Query-Eingaben werden vor Veröffentlichung nachgeprüft.
Durable Work, externe Ergebnislieferung, feingranulare Planung, vollständige
Plattformabnahme und der gebundene 10.000-Artefakte-/2-Sekunden-Nachweis bleiben
offen. Kleine Fixture-Messfenster stellen ausdrücklich keinen Benchmark dar.

Beim Anlegen von `ReadCommandWork` werden relative Projekt-, lokale Basis- und
Query-Filter-Ursprünge absolut gebunden. Veränderbare Query-Optionslisten werden
als eigene JSON-Werte übernommen. Ein späteres Wechseln des Arbeitsverzeichnisses
oder Ändern dieser Listen verschiebt den festgelegten Umfang nicht. Dateiinhalt
und aktuelle Sicherheitsbedingungen werden weiterhin erst in der Ladephase
geprüft und vor Abschluss nachgeprüft. Ungültige Basisargumente werden durch
die Pfadbindung nicht zu einer impliziten Auswahl des aktuellen Verzeichnisses.

Während einer aktiven Phase werden erneutes `advance()` und `close()` abgelehnt.
Ein Abbruch vor Abschluss liefert kein Resultat; ein Fehler an einer Runtime-
Grenze bleibt ein fehlgeschlagener Arbeitszustand ohne veröffentlichbare
Ergebnisse. Nicht verfügbare optionale Messwerte verkürzen den Fachumfang nicht.
Änderungen von Bytes oder Inventar während einer Diff-Aufnahme werden als
Konflikt gemeldet, ohne eine teilweise Vergleichsaussage auszugeben.

Die maschinenlesbare CLI-Ausgabe bestätigt jeden angenommenen Textabschnitt und
den abschließenden Flush. Kurze Schreibvorgänge werden bis zum vollständigen
Dokument fortgesetzt. Stillstand, ungültige Zähler, Broken Pipe oder Flushfehler
führen zu Exitcode 5. Eine bereits angenommene Ausgabe kann dabei ein Präfix
enthalten; es wird kein zweites Fehlerdokument angehängt. Ein erneuter Aufruf
berechnet und liefert wieder den vollständigen aktuellen Befund. Diese Regel
betrifft die maschinenlesbare Ausgabe, nicht deren menschliche Darstellung,
und erteilt keine Schreibberechtigung für das Projekt.
