# Apply-Commitpläne — APPLY-ONLY-535

Der normale Dev-Auftrag endet mit einer nativ validierten PatchHarbor-ZIP.
Vorher werden keine Tests ausgeführt. Eine reine Collection darf die
Testidentitäten ermitteln. Alle Commits und Tests entstehen später im Apply.

## Vorbereitung

Ausgangspunkt ist immer das neueste nativ validierte Result mit vollständiger
repo_id, base_commit, state_fingerprint und fingerprint_algorithm. Base,
staged/unstaged Änderungen und untracked Dateien bilden zusammen den
zurückgegebenen Arbeitsstand. Bei Fehlern niemals nur base/ übernehmen.

Für jeden geplanten Commit wird ein eigener vollständiger Dateizustand
vorbereitet. `verification_support.bundle_prepare.prepare_stage` nimmt
Vorher-/Nachher-Verzeichnisse, eine ausdrücklich ausgewählte Pfadliste,
Commit-ID, Commitnachricht und den Pflicht-Testplan entgegen. Es erzeugt
keine Git-Commits und startet keine Tests. Neue/geänderte Testdateien werden
in die Pflichtauswahl aufgenommen. Testnummern aus der vollständigen Collection
werden nur hinten an die vorhandene Registry angehängt. Entfernte Nummern
bleiben reserviert. Die Registry und alle Spezifikations-/Katalogbindungen
gehören jeweils zum tatsächlichen Zwischenstand.

Der Bundleplan enthält `format_version: 1`, `bundle_number`,
`source_result_sha256`, `binding` mit den vier nativen Werten,
`apply_repository` aus der bestätigten Umgebung, `branch: dev`,
`initial_dirty` aus dem Result, `stages` und `correction_of: null`.
`render_entrypoint(plan, core_python=...)` erzeugt einen privaten Bash-
Entrypoint mit dem vollständigen eingebetteten Plan und geprüften Payloads.
Das bestätigte installierte PatchHarbor-Python ist explizit anzugeben.
Die regulären ZIP-Payloads bleiben leer: der Core-Writer installiert im
Entrypoint immer nur den gerade fälligen Zustand. Kein Endzustand vor W.

Diesen Entrypoint in einen neuen Inhaltsordner als run.sh schreiben und
mit der verifizierten Result-Runtime über `api.pack_patch` oder `pack`
gegen genau das Result paketieren. Danach native `validate_patch` und
Öffnung der tatsächlich erzeugten ZIP; Bindung, Payloads und SHA prüfen.
Genau eine ZIP atomar an den vorhandenen Watcher übergeben. Keine direkte
Änderung an specroad-apply, kein eigener Apply oder zweiter Watcher.

Vertrag v1 unterstützt reguläre nicht ausführbare Dateipayloads. Löschungen,
Symlinks und Moduswechsel dürfen nicht still in ein solches Paket übersetzt
werden; sie brauchen einen ausdrücklich passenden sicheren Payloadvertrag.
Dies ist keine Erlaubnis, geplante fachliche Arbeit wegzulassen.

## Ausführung und Nachweis

Der Entrypoint prüft zuerst die native Resultbindung und den Zielbranch.
Danach je Zustand: Vorherbytes und Scope prüfen, Core-Payloads ausbringen,
gebundenes paralleles Vereinigungs-Gate ausführen, Belege erneut prüfen,
nur vorgesehene Pfade stagen und committen, Elterncommit/Inhalt/Scope und
sauberen Abschluss prüfen. Erst dann darf der nächste Zustand beginnen.
Kein Modell, keine automatische Wiederholung, kein Reset und keine CI.

`SPECROAD_APPLY_PLAN` enthält den vollständigen öffentlichen Commitplan.
`SPECROAD_APPLY_PROGRESS` enthält plan_sha256, source_result_sha256,
phase, committed (Commit-ID, Elterncommit, tatsächlicher Commit, Gatebeleg),
active_commit_id, remaining_commit_ids, actual_head und error.
Die Records werden geflusht im Ausführungslog veröffentlicht und zusätzlich
unter einem eigenen ignorierten build-Verzeichnis dauerhaft gespeichert.
PatchHarbor übernimmt das Ausführungslog in sein Result. Erfolg wird erst
nach allen Commit-Gates und sauberem Abschluss gemeldet.

## Korrekturbundle nach einem Fehler

1. Das neueste Fehler-Result nativ vollständig prüfen, einschließlich
   tatsächlichem HEAD, dirty Zustand und vollständigen Dateideltas.
2. Den zu diesem Result gehörenden Plan und letzten Fortschrittsrecord
   aus seinem Ausführungslog lesen; Quell-Result und ursprüngliches Paket
   anhand ihrer vollständigen Bindungen zuordnen. Einzelne JSON-Zeilen aus
   fremden Logs oder Erfolgsbehauptungen sind keine Grundlage.
3. `remaining_commits(plan, progress, result_head=context.base_commit)`
   prüft den gebundenen Commitpräfix und gibt den vollständigen Rest zurück.
   Stimmen HEAD oder Commitkette nicht, Diagnose statt Wiederholung.
4. Den ersten offenen Zustand auf dem erhaltenen Arbeitsstand reparieren.
   Alle weiteren offenen Commit-IDs behalten Reihenfolge und Umfang;
   ihre Payloads/Preimages und Quellbindungen bei Bedarf korrekt neu bilden.
   Bereits erfolgreiche Commits entfallen. Bei dirty Basis gehören alle
   vorhandenen Änderungen in den ausdrücklich geprüften ersten Commit-Scope.
5. Neues Bundle an die vier Werte und den SHA des FEHLER-Results binden;
   `correction_of` enthält den alten plan_sha256 und genau die verbleibenden
   Commit-IDs. Keine Wiederverwendung der alten Resultbindung, kein Reset.

Beispiel: W committed, R-Test rot. Das neue Bundle enthält R (mit Korrektur)
und C. Die fällige Gruppe bleibt für R unverändert, weil der gescheiterte
Versuch keinen Commit erzeugt hat. Die aktuellen Zeiten werden beim neuen
Versuch frisch gelesen. Es werden keine früheren Gate-Erfolge als Nachweis
für den reparierten Code wiederverwendet.

## Ressourcen des ausführenden Hosts

Ab HOST-WORKERS-537 verwendet der gemeinsame Apply-Runner automatisch
`min(verfügbare CPUs, 10)` Worker, Worksteal und mindestens Nice +10.
`run_apply_tests.py --worker-limit N` erlaubt eine positive andere Grenze;
der Standard-Entrypoint verwendet 10. Jeder Commit erhält weiterhin genau
ein Gate. Auswahlbindung v5 und Beobachtungen binden die tatsächlichen
Ressourcen. Details: [Testing.md](Testing.md).

## Optionale Klärung und typisierte Stages (Vertrag 4)

Neue V4-Bundles verwenden `format_version: 2` mit `handoff_kind` und
`role` je Stage. Ohne Klärung: `patch_ready`, nur `implementation`/`correction`.
Mit notwendiger zulässiger Klärung: `patch_ready_with_clarification`, genau
eine `clarification` zuerst, danach mindestens eine `implementation`.
`prepare_stage(..., role=...)` ergänzt die Rolle; ohne Argument bleibt v1.
Die normative Regel und Markerstruktur stehen in Spezifikation 2.4.3.1.
Der Klärungscommit ist niemals Pflicht und besitzt keinen Produktplanzähler.
Er ändert Spec, Plan und aktive Katalogbindungen; jede Stage behält ihr Gate.
`remaining_commits` liefert nach einem Fehler auch die unveränderten Rollen
zurück. Eine Fortsetzung nach abgeschlossenem Klärungscommit ist `patch_ready`;
ein noch offener Klärungspräfix bleibt ein gebundener Rest, keine neue Klärung.
Alte v1-Pakete, ihre Hashes, Stages und Logs werden nicht nachträglich ergänzt.

## Commitmetadaten und manuelle CI

Jeder neue native Apply-Commit schreibt SpecRoad-Bundle und
SpecRoad-Bundle-Final sowie SpecRoad-Commit-ID und Apply-Selection-SHA256.
Nur der letzte tatsächlich angekündigte Commit der jeweiligen ZIP erhält
Bundle-Final true; eine Korrektur mit einem Restcommit ebenfalls. Die
Metadaten starten keine CI. Eine manuelle Auswahl prüft weiterhin exakten
Commit und dev-Herkunft. Ungültige Metadaten führen zum Fehler und nach
Möglichkeit zu einem begrenzten Auswahlfehlerbericht ohne Zugangsdaten.
