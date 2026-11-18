# Bundle 736 — Vollständiger Proposal-Workrest nach Capability-Korrektur

Das native Fehler-Result mit SHA-256
`d64dae44f5f33805bb78427a706d7811d316f4ddf45942b984fa2a787e6f965f`
bestätigt den Klärungscommit `PROPOSAL-WORK-735` als
`b78b21644214fbc419aa29a0d9fb28691ecfd4c2`. Sein eigenes Gate bestand
7.221 Tests einschließlich 147 Pflichtfällen. Die Spezifikation 0.2.93 ist
damit übernommen; der Produktfortschritt bleibt bestätigt bei 789/918.

Das anschließende W-Gate meldet 2 fehlgeschlagene und 11.240 bestandene Fälle.
Beide Fehler betreffen bestehende Capability-Abnahmen: Nach dem Entfernen von
Work-, Migrations- und Merge-Kommandos erwarteten sie keine Workunterstützung.
Der nun tatsächlich registrierte `proposal.check` bleibt jedoch verfügbar.
Seine passive Fortsetzung gehört gemäß dem übernommenen Vertrag zur Engine.

Die Korrektur prüft ausdrücklich die Verfügbarkeit bei allein verbleibendem
Proposal-Adapter. Erst nach dessen Entfernung gilt die unveränderte negative
Erwartung: keine Engine, keine Checkpointalgorithmen, keine Budgetpolicy.
Alle bisherigen Format-, Versions-, Budget- und übrigen Verhaltensassertionen
bleiben erhalten. Testidentitäten und stabile Nummern ändern sich nicht.
Produktcode, Spezifikation, Review-/Autoritätsgrenzen und native Writer bleiben
gegenüber den bereits angekündigten jeweiligen Stages bytegleich.

Die vollständige offene Folge lautet weiterhin `18.o.W`, `18.o.R`, `18.o.C`,
jeweils mit Rolle `implementation` und eigenem Apply-Gate vor dem Commit.
Die Korrektur wird in allen drei Zielständen fortgeführt; C erhält exakt die
R-Testbytes. Sämtliche bisherigen Pflichtdateien bleiben Pflicht. Die beiden
geänderten Testdateien werden vollständig und ungefiltert mit ausgewählt.
Der erfolgreiche Klärungscommit wird nicht wiederholt; es gibt weder eine
neue Klärung noch einen Budgetreset. Die Vorherbytes der ersten Stage enthalten
den vollständigen erhaltenen W-Arbeitsstand aus dem neuen Result.

Dev prüft Syntax, statische Konsistenz, reine Collection und native Paket- und
Fortsetzungsbindung. Kein Testkörper oder Fixture wurde in Dev ausgeführt;
die Korrektur ist noch kein erfolgreicher Apply-Nachweis. Die weitere geplante
Gruppe 18.p bleibt vollständig offen. Ihre erforderliche native Veröffentlichung
überarbeiteter Inhalte und die vollständigen Dialogabnahmen werden nicht durch
eine verkürzte oder nur nominelle Stage an diese Reparatur angehängt.

Ziel erst nach dem eigenen erfolgreichen Gate dieser Stage: **18.o.R**, **791/918**, danach **18.o.C**.
