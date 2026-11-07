# OFF-PLAN RESTORE-TEST-FLOW-540 — Baseline-Inventur und Mapping-Bundle kürzen

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN RESTORE-TEST-FLOW-540 — Baseline-Inventur und Mapping-Bundle kürzen

Autorität: ausdrücklicher Nutzerauftrag vom 1. November 2026, beide zuletzt
analysierten Änderungen gemeinsam in einem Bundle umzusetzen. Ein technischer
Testcommit; Produktfortschritt bleibt 655/900 und 15.n.R der nächste Produktcommit.
Diese Freigabe ersetzt für die beiden betroffenen Varianten die vollständigen
Capture-Schleifen aus RESTORE-TEST-FLOW-539. Dessen erfolgreiche Nachweise bleiben
historisch erhalten; Produkt-, Store- und Runneroptimierungen bleiben außerhalb
dieses Auftrags.

Maßgebliche Basis ist das vollständig nativ geprüfte, saubere Result
`specroad-apply_Result_172045_1101_130a3a.zip`, SHA-256
`a2e0ba07c6d31b6c9d967193bdf6ca4cd473eb59f5958a1e743541eae7bd2b38`.
Es bestätigt Bundle 539 mit 6.313 bestandenen Apply-Tests und Abschlusscommit
`ea1a18c8408d5202d488b25e1676b5394130747a`. Die nächste Rotationsgruppe ist 1.
Die letzten Messungen aus Lauf 67 betragen 668,623 s für argv-baseline und
433,177 s für mapping-project_bundle. Der bereits gebündelte mapping-baseline-
Fall benötigte 49,006 s. Diese Werte stammen aus zehn parallelen Workern und
sind keine garantierten Laufzeiten für den neuen Zustand.

Entscheidung vor Umsetzung: Der native Capture-Testhelfer erhält einen engen
Inventurmodus. Er darf ausschließlich mittlere verbleibende Inventur-Captures
publizieren und muss den letzten Inventur-Capture, Qualifikation und Lieferung
offen lassen. Die Originalbytes werden weiterhin mit dem nativen Capture-
Adapter gelesen und durch den unveränderten Checkpoint-Store veröffentlicht.
Der bisherige Standardmodus behält sein Verhalten für mapping-baseline und
die beiden Schemafehlerfälle. Keine künstlichen Erfolgsdaten oder gemockten
Capture-/Store-/Qualifikationsprüfungen.

Abnahme 1: argv-baseline führt alle Baseline-Quell-Captures weiterhin einzeln
über öffentliche Aufrufe mit exaktem Fortschritt aus. Die Quellanzahl wird aus
den tatsächlich gespeicherten Aufgaben gelesen. Erster und letzter Inventur-
Capture bleiben ebenfalls öffentliche Resumes; ausschließlich die mittleren
Inventur-Captures werden gemeinsam publiziert. Bei der bestehenden Fixture
sinkt die vorgesehene Checkpointzahl dadurch von 29 auf 15. Die vollständige
Inventur-Resume-Kette bleibt in argv-project_bundle erhalten. Nur die doppelte
Kombination jedes mittleren Inventurschritts mit Baseline wird aufgegeben.

Abnahme 2: mapping-project_bundle übernimmt denselben Ablauf wie die bereits
beschleunigte mapping-baseline: öffentlicher Start, erster Capture-Resume,
native gemeinsame Erfassung des Rests, öffentliche Qualifikation und Lieferung.
Für die bestehende Fixture sind sieben statt 22 Checkpoints vorgesehen.
argv-project_bundle bleibt unverändert vollständig. Alle vier Varianten
behalten den unabhängigen Planvergleich, exakte Ausgabebytes, unveränderten
Projektbestand und passiven schreibfreien Replay nach Entfernen der Quelle.
Alle Testidentitäten und ihre dauerhaften Nummern bleiben unverändert.

Pflichtauswahl: vollständige test_restore_work_public.py sowie beide bisherigen
Schema-Nutzer des Helfers in test_restore_schema_boundary_public.py. Dazu
test_restore_invocation_options.py, test_restore_invocation.py und
test_restore_legacy_history.py für Aufrufparität und native Quell-/Formatgrenzen;
test_restore_capture.py, test_restore_planning_recovery.py und die beiden
test_work_checkpoints-Dateien für Originalbytes, Teilpublikation, Wiederöffnung,
Fremdänderungen und Crash-/I/O-Grenzen. Apply vereinigt diese ungefiltert mit
seiner fälligen N=3-Gruppe und committet erst nach dem einen erfolgreichen Gate.

Dev führt keine Verhaltenstests aus. Statische Prüfung, reine Collection und
native Paketvalidierung sind keine Verhaltensabnahme; tatsächliche neue Zeiten
bleiben bis zu Apply offen. Ein Bundle an den vorhandenen Watcher, kein eigener
Apply-, Control- oder CI-Start und keine automatische Result-/Korrekturschleife.

Commit: `OFF-PLAN RESTORE-TEST-FLOW-540 perf(tests): Baseline-Inventur und Mapping-Bundle bündeln`.
