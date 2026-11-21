# Bundle 781 – aktuelle negative Laufnachweise

Das native Fehler-Result mit SHA-256
`db3f581922ae0d83f299f6e67df971ba6be05c8113bb9b9b40b156bf36c2d1bc`
bestätigt 20.a.W mit 7.646 bestandenen ausgewählten Tests und Commit
`451a1b237560dd2f7a67e175957c5a8e41818a04`. In 20.a.R scheiterte
`test_real_nonpassing_run_keeps_exact_outcome_without_promoting_inventory[failed]`;
7.608 weitere Tests bestanden. 20.a.R wurde nicht committed, 20.a.C nicht
installiert. Der erhaltene vollständige Arbeitsstand ist die Korrekturbasis.

Die statische Ursachenanalyse zeigt eine Abweichung zum vorhandenen nativen
Runner: `pytest_testnodedown` erfasst jeden Worker-Exit ungleich null als
`worker_nonzero_exit`, auch Exit 1 nach einem tatsächlichen Testfehler.
Das neue Abnahmeinventar lehnte bisher jeden Eintrag in `observation.errors`
ab. Dadurch wurde der echte aktuelle Fehlnachweis als ungültig eingestuft.

Die Korrektur akzeptiert ausschließlich den einzelnen bekannten Marker zusammen
mit pytest-Exit 1 und mindestens einem tatsächlichen Outcome `failed`, `error`
oder `unexpected_success`. Der Suite-Status bleibt false, die betroffene
Requirement-Evidence failed. Alle übrigen Vollständigkeits-, Identitäts-,
Hash-, Case- und Zählerprüfungen bleiben bestehen. Zusätzliche oder unbekannte
Fehler, doppelte Marker, falsche Exitcodes und gefälschte Erfolgskennzeichen
bleiben ungültig. Ein Marker ohne tatsächlichen Fehler ist ebenfalls ungültig,
auch bei ausschließlich bestandenen, übersprungenen oder XFail-Tests.
Die vorhandenen Runner-, Apply-Gate- und Commitregeln werden nicht geändert.

Die reale kleine native Fehler-Fixture bleibt erhalten und wird innerhalb eines
Workers nur einmal pro Modul vorbereitet; alle Varianten erhalten eigene
unveränderliche Ausgangsdaten. Elf zusätzliche negative Varianten prüfen den
engen Marker-Vertrag. Die bisherige fehlgeschlagene Testidentität, sämtliche
W/R-Abnahmen, bestehenden Pflichtauswahlen und historischen Testnummern bleiben
erhalten. Die vier aktiven Requirementbindungen erhalten die zusätzlichen IDs.
C übernimmt identische Testbytes und dieselbe Validatorfunktion; ausschließlich
die bereits angekündigte Strukturbereinigung trennt R und C.

Bundle 781 führt genau die noch offenen IDs 20.a.R und 20.a.C mit ihren Rollen
implementation, ihren exakten Commitnachrichten und jeweils eigenem Apply-Gate
fort. Das native correction_of bindet diesen vollständigen Rest; der erfolgreiche
W-Commit wird nicht wiederholt. Spec und Entwicklungsvertrag bleiben unverändert;
keine zusätzliche Klärung oder Budgetänderung.

Der in [Bundle 780](bundle-780-acceptance-inventory.md) belegte offene R-36-Pfad
verhindert weiterhin einen vollständigen Abschluss von 20.c. Deshalb wird keine
unvollständige Folgestage angehängt. 20.c.W bleibt der nächste Planschritt nach
erfolgreichem C. Menschliche Reviews, Originalnachweise und Releasefreigabe
bleiben offen. Dev führt nur statische Prüfungen, reine Collection und native
Paketprüfung aus; Verhaltenstests laufen ausschließlich in Apply.

Aktueller Commitzielstand: `20.a.R`. Erst das erfolgreiche eigene
Apply-Gate und der Commit bestätigen seine Planmarkierung.
