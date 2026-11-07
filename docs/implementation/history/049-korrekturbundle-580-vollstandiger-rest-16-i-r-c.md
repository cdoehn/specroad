# Korrekturbundle 580 — vollständiger Rest 16.i.R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 580 — vollständiger Rest 16.i.R/C

Das maßgebliche native Fehler-Result hat SHA-256
`6ee245cc91dbae7490e1e7041e264dc65b8aee7e9af98f1fa0c658d68600f253`,
HEAD `b3e452022899f419b0a427017bb68abfc4ac3173` und den erhaltenen
Dirty-Fingerprint `70697cdb5a178057`. Bundle 579 sammelte 24763 Tests
und führte die fällige Gruppe 1 mit der ungefilterten Pflichtauswahl aus:
9045 bestanden, ein Test fehlgeschlagen. Kein Commit entstand; der erhaltene
Arbeitsstand entspricht exakt der angekündigten R-Stage. Der erfolgreiche
W-Commit bleibt erhalten, tatsächlicher Produktstand weiterhin 685/900.

Die einzige fehlgeschlagene Prüfung war die letzte Fehlererwartung in
test_recovery_reentry_after_lost_rollback_effect. Die echte Unterbrechung,
fortgesetzter Rollback, exakte Wiederherstellung der normativen Quelle und
schreibfreie wiederholte Recovery hatten ihre Prüfungen bestanden. Der
anschließende Apply-Aufruf verwendete aber den ursprünglichen Migrationsplan
und die ursprüngliche Sicherung. Beide binden das neue passive Rollback-Audit
noch nicht. Daher lehnt der Writer zuerst mit transition_source_changed ab,
bevor er die verbrauchte Transaktions-ID prüfen kann. Diese Reihenfolge ist
mit der vollständigen Quellbindung einschließlich passiver Daten vereinbar;
Produktcode oder Spezifikation werden für den Test nicht gelockert.

Die technische Korrektur ergänzt den tatsächlichen Testaufbau: Der alte
Plan mit alter Sicherung muss weiterhin mit transition_source_changed und
Exit 6 ohne Änderung der vollständigen Quelle abgelehnt werden. Anschließend
entstehen aus allen aktuellen Dateien ein neuer nativer Plan und eine echte
externe Sicherung. Der Test prüft deren vollständige Dateibindung, die
geschützten Auditpfade und die tatsächlich wieder geöffneten Backupbytes.
Mit diesen gültigen Eingaben muss dieselbe bereits verbrauchte Transaktions-ID
mit transition_id_collision und Exit 6 scheitern, ohne Journal, Quelldateien
oder Backup zu ändern. Als positive Gegenprobe muss eine neue Transaktions-ID
denselben frisch gebundenen Plan veröffentlichen, das exakte normative Ziel
erreichen und alle vorherigen passiven Auditbytes sowie die Sicherung erhalten.
Kein Audit wird entfernt, kein Produktgate ersetzt und kein Fehler pauschal
akzeptiert. Die ursprüngliche Crash-/Recoveryprüfung bleibt vollständig.

Die aktive Testfallbeschreibung SR-TC-0270 dokumentiert diese bereits aus
12.20.4 folgenden Nachweise. Testidentitäten, Nummern, Registry, Normspec
0.2.59 und alle Produkt-/Runnerdateien bleiben je Stage bytegleich zu 579.
Keine neue normative Detaillücke, Klärung oder Budgetänderung. Die bestehenden
Recovery- und Nummernkorrekturen bleiben erhalten. Der gesamte geänderte Test
und die bisherigen Writer-, Recovery-, Backup-, Validierungs-, Nummern- und
Apply-Regressionen gehören weiterhin ungefiltert zur Pflichtauswahl.

Die vollständigen offenen IDs 16.i.R und 16.i.C behalten role=implementation.
correction_of bindet Planhash
`b6cf009528173ffeead068b9d73688d5e6910a97b169c47b6ed0ebbee83aaed1`
und genau diesen Rest. Erste Stage und Vorherbytes umfassen den gesamten
erhaltenen Dirty-Stand. R erhält Gruppe 1, C anschließend Gruppe 2; jede
Stage wird erst nach eigenem N=3-plus-Pflichtauswahl-Gate committed. C bleibt
die angekündigte reine Extraktion der Beweisfunktionen; Funktions-ASTs sind
zu R identisch, Tests und Kataloge bytegleich. Kein erfolgreicher Präfix
wird wiederholt und kein Endstand vorab installiert.

Dev führt keine Verhaltenstests aus. Vorbereiteter Zwischenstand: C;
Häkchen und Zähler gelten erst nach erfolgreichem Apply-Gate und echtem
Commit. Vollständiger Abschluss ergäbe 687/900; danach bleibt 16.j.W offen.
Kein CI-, Watcher-, Control- oder Dienststart, keine lokale Konfiguration
in der Payload und keine eigene Warte-/Apply-Schleife.
