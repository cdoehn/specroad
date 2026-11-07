# OFF-PLAN RESTORE-TEST-FLOW-539 — wiederholte Capture-Durchläufe begrenzen

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN RESTORE-TEST-FLOW-539 — wiederholte Capture-Durchläufe begrenzen

Autorität: ausdrücklicher Nutzerauftrag vom 1. November 2026, die analysierten
Optimierungen 1 und 2 umzusetzen; die Produktoptimierung 3 bleibt ausgenommen.
Ein technischer Testcommit, keine neue Produkt-W/R/C-Folge. Produktfortschritt
bleibt 655/900; 15.n.R ist weiterhin der nächste Produktcommit.

Maßgebliche Basis ist das vollständig nativ geprüfte, saubere Result
`specroad-apply_Result_165052_1101_1d8464.zip`, SHA-256
`bbacba19ede77b6697c0e9687658037019ff049a3b35eba8b3e828e4a9ff587b`.
Es bestätigt Bundle 538 mit den echten HOST-WORKERS-537-Commits W
`c7a725a0afb1c38f36f5586ac6c45f0601fd8805` (6.415 Tests), R
`c7bac979ce41f2add795119e4c7b394491061b2d` (6.600 Tests) und C
`2a5ce805f397a0f76661f101c5aa6555de5f37c7` (6.447 Tests), jeweils erfolgreich.

Entscheidung vor Umsetzung: Ein gemeinsamer Testhelfer erfasst nach dem
öffentlichen Start die verbleibenden Originalbytes mit dem nativen Capture-
Adapter und publiziert sie gemeinsam über den unveränderten Manifest- und
Checkpoint-Store. Er darf ausschließlich Capture-Einheiten abschließen;
Qualifikation und Lieferung bleiben echte öffentliche Resume-Aufrufe.
Die Alternative, beide Baselinevarianten weiterhin durch jeden öffentlichen
Capture-Resume zu führen, verdoppelt dort dieselbe teure Kettenprüfung.
Produktseitiges Caching, kürzere Prüftiefen und Änderungen am Store bleiben
ausgeschlossen; ebenfalls keine künstlichen Erfolgsbelege oder gemockten
Quelldaten. Vorhandene Testidentitäten und dauerhafte Messhistorie bleiben.

Abnahme 1: Die beiden Schemafehlerfälle für Artefakt und Attachment behalten
öffentlichen Start und öffentliche Qualifikation, echte beschädigte Originale,
unveränderte Projekt-/Quellbestände sowie fehlende Planlieferung. Zusätzlich
prüfen sie den exakten Fehlergrund, Pfad und Schema-Pointer. Nur die Capture-
Schleife dazwischen wird durch eine native Sammelpublikation ersetzt.

Abnahme 2: `argv-baseline` bleibt als vollständige Referenz mit jedem einzelnen
Resume und Fortschrittswert unverändert. `mapping-baseline` behält öffentlichen
Start, ersten Capture-Resume, Qualifikation, Lieferung, Bytegleichheit zum
unabhängigen Plan und passiven Replay ohne Quelle. Nur die übrigen Capture-
Zwischenschritte werden gebündelt. Beide project_bundle-Varianten bleiben
vollständig. Ein zusätzlicher I/O-freier Baselinefall prüft die Gleichheit von
argv, Mapping und CommandRequest einschließlich der operativen Optionen.

Pflichtauswahl für RESTORE-TEST-FLOW-539: alle Tests der drei geänderten
Testdateien sowie `test_restore_planning_recovery.py`, `test_restore_capture.py`,
`test_restore_legacy_history.py` und `test_restore_invocation.py` für
Checkpoint-/Crashgrenzen, Capture-Originale, unterstützte/abgewiesene Formate
und öffentliche Aufrufbindung. Apply vereinigt diese ungefiltert mit seiner
fälligen N=3-Gruppe, führt genau ein hostabhängiges worksteal-Gate aus und
committet erst bei Erfolg. Die neue Testnummer wird ausschließlich angehängt.

Dev führt keine Verhaltenstests aus. Syntax, reine Collection und native
Paketprüfung sind keine Verhaltensabnahme. Die tatsächliche Laufzeitverbesserung
bleibt bis zu neuen Apply-Messungen offen. Keine Spezifikations-, Produkt-,
Control-, CI- oder Runneränderung. Übergabe als ein gebundenes Bundle an den
vorhandenen Watcher; keine automatische Result-/Korrekturschleife.

Commit: `OFF-PLAN RESTORE-TEST-FLOW-539 perf(tests): redundante Restore-Capture-Resumes begrenzen`.
