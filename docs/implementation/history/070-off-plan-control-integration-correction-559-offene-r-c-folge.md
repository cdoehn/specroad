# OFF-PLAN CONTROL-INTEGRATION-CORRECTION-559 — offene R/C-Folge

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN CONTROL-INTEGRATION-CORRECTION-559 — offene R/C-Folge

Ausdrücklicher Korrekturauftrag vom 3. November 2026. Maßgeblich ist das
nativ geprüfte Result ae8822, SHA-256
`bd5ebef162bf4e4c0304cea14ce1976a72a383dfa2b4c498e723fc850e9cdd93`,
Basiscommit `23bf49cf788e1ad337c3e432f8e651f93d9b10e4`,
Arbeitsstand-Fingerprint `5190664141ab9408`. CONTROL-INTEGRATION-556.W hat
7165 Tests bestanden und wurde mit diesem Basiscommit abgeschlossen.
Der Commit wird erhalten und nicht wiederholt. R scheiterte nach 7207
bestandenen Tests an genau einem Test; R/C bleiben vollständig offen.

Belegter Fehler: test_worker_wakes_for_due_retry_without_any_new_exchange_event
erhielt beim Warten auf retry_wait den IPC-Fehler not_running. Das Result
enthält weder den Exit-Code noch das temporäre Protokoll oder den letzten
persistierten Zustand dieses Testworkers. Eine konkrete Prozessabbruchursache
ist daher nicht belegt. Insbesondere werden weder ein Speicherproblem noch
ein bloßer Timingfehler als Tatsache behauptet.

Die Testbeobachtung unterscheidet nun Erreichbarkeit und Lebenszustand des
exakt gestarteten Prozesses. not_running wird innerhalb derselben bestehenden
Frist nur bei lebendem Prozess erneut abgefragt. Ein Prozessende, auch Exit 0,
oder die Fristüberschreitung bleibt ein Fehler mit strukturierten Angaben:
Exit-Code, letzter Live-Zustand, persistierter Stop-/Fehlergrund und begrenztes
Protokollende. Gespeicherte Zustände sind ausschließlich Diagnose, niemals
Live-Erfolg. Andere IPC-/Sicherheitsfehler werden unverändert weitergereicht.
Kein Neustart, kein übersprungener Test und keine verlängerte Retry-Frist.
Die eigentlichen Abnahmen für Timer, Pause, Budget und kontrollierten Stop
bleiben erhalten; neue Fälle sichern die Beobachtung gegen falschen Erfolg.

Die R-Abnahme ist zugleich der erforderliche neue Beleg für diesen bisher
unvollständig diagnostizierten Fehler. Sollte der Prozess tatsächlich erneut
abbrechen, bleibt das Gate rot und liefert nun seine Diagnose. Eine bereits
erfolgreiche Verhaltenserprobung dieser Änderung wird nicht behauptet.
CONTROL-INTEGRATION-556.R/C erhalten die nächsten Rotationsgruppen 1/2 und
jeweils die vollständige Control-Pflichtsuite. C übernimmt R-Tests und Nummern
bytegleich und führt nur den schon geplanten Release-Vertragsrefaktor fort.

Spezifikation 0.2.53, ihre Katalogbindungen und Produktstand 669/900
(nächster Produktcommit 16.d.W) bleiben unverändert. Dev führt keine
Verhaltenstests aus; keine Dienst-, Watcher-, Control- oder Betriebsmigration.
