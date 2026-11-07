# Korrekturbundle 576 — vollständiger Rest 16.i.W/R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 576 — vollständiger Rest 16.i.W/R/C

Das maßgebliche native Fehler-Result hat SHA-256
`75415bcd0a94e111604994a422dc416829dd0019acf1494db441b3a923da5b1f`,
HEAD `eb91b55282e7a2ff9528412cfa60fd684a1d46bb` und den erhaltenen
Dirty-Fingerprint `b77867cc9d0554c5`. Bundle 575 übernahm den Klärungscommit
MIGRATION-TRANSACTION-575 nach 6800 erfolgreichen Tests. Er bleibt erhalten.
16.i.W scheiterte danach an genau einem Regressionstest; 8651 Tests bestanden.
Der Produktstand bleibt tatsächlich 684/900. Der vollständige Arbeitsstand
entspricht der angekündigten W-Stage; R und C wurden noch nicht ausgebracht.

Ursache: validate_model importierte den neuen Legacy-Helfer bedingungslos
während jedes Aufrufs. Der bestehende Test
ModelValidationRightTests.test_validating_does_not_read_files_or_import_adapters
verbietet solche Imports und Datei-I/O im gewöhnlichen geladenen Modellpfad.
Die Korrektur führt den Legacy-Import und die Qualifikation ausschließlich
bei einem ausdrücklich übergebenen Legacy-Manifest aus. Ohne Manifest bleibt
die Legacy-Zuordnung leer; aktuelle Schema-, Profil- und Graphprüfungen werden
unverändert ausgeführt. Mit Manifest bleiben die vollständige native Prüfung,
Originalbindungen, Scope-Grenzen und Fehlerverträge erhalten. Das entspricht
der vorhandenen Trennung expliziter Zusatzkontexte im gemeinsamen Validator.

Keine neue Detailentscheidung und kein Klärungspräfix: Spezifikation 0.2.59,
Quellvertrag, alle Testbytes, Katalogbindungen und stabilen Testnummern bleiben
je angekündigter Stage unverändert. Der bestehende fehlgeschlagene Test wird
nicht abgeschwächt oder ausgeblendet. Alle neuen Migrationsabnahmen und die
vollständigen relevanten Regressionen bleiben Pflichtauswahl. Die identische
technische Korrektur wird in W, R und C fortgeführt; C behält seine echte
Strukturänderung mit unveränderten Funktionskörpern und R-Tests.

Alle offenen IDs und Rollen bleiben erhalten: 16.i.W, 16.i.R, 16.i.C mit
role=implementation. correction_of bindet den ursprünglichen Planhash
`32179489cee8116649728c445045bce288196a158e8e25a54fdc753e324e8707`
und genau diesen Rest. Vollständige Vorherbytes und Dirty-Scope binden das
Fehler-Result; erfolgreiche Commits werden weder wiederholt noch zurückgesetzt.
Jede Stage erhält erneut ihre fällige N=3-Gruppe (0/1/2) plus ungefilterte
Pflichtauswahl vor ihrem Commit. Dev führt ausschließlich statische Prüfung,
reine Collection und native Paketprüfung aus, keine Verhaltenstests.
Keine Änderung an Control, Budget oder Betriebsdaten; keine eigene Schleife.
Vorbereiteter Zwischenstand: C; Häkchen und Zähler gelten erst nach
jeweiligem erfolgreichen Apply-Gate und echtem Commit. Nach vollständigem
Abschluss wäre 687/900 erreicht; 16.j.W bleibt der nächste offene Schritt.
