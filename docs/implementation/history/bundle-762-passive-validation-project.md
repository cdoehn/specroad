# Bundle 762 — vollständige Projektdaten für passive Validierung

19. November 2026. Maßgebliches natives Fehler-Result SHA-256:
`cba74ffe83e65f23459b45ca236ac713efa5a70b732be82b5eea1d4760dd12da`.
HEAD blieb `1eb37f579499161f67860fcc14e6c62109f0d12f`.
Der erhaltene Arbeitsstand entspricht vollständig 19.m.W aus Bundle 761.
Der öffentliche ursprüngliche Plan hat SHA-256
`073ad81c560afb991f52c80fdbbc0c1876f9687a9b79ccae942933ffe05f46f8`.
Das Result protokolliert **8739 bestandene und einen fehlgeschlagenen Test**
im W-Gate. Kein neuer Commit entstand. Bestätigt bleiben **837/918**;
der vollständige Rest **19.m.W/R/C** bleibt offen.

## Belegter Fehler und gezielte Korrektur

Die Variante `validate` von
`test_passive_commands_neither_import_dependencies_nor_initialize_model`
erwartete Exit 0, erhielt aber Exit 3 mit Modelldiagnose `SRV002`.
Die Testvorbereitung benutzte `test_analyzer_subjects.project`: Dieser Helfer
liefert Konfiguration und Artefakte für den Subject-Export, aber keine
Core-Profil- und Sprachregisterdateien für eine vollständige öffentliche
Projektvalidierung. Er ist kein vollständiger Erfolgsfall für diesen Befehl.

Der passive Befehlstest verwendet jetzt den bestehenden nativen Helfer
`support.inspection.inspection_project` mit einem eigenen minimalen Draft-
Requirement. Er liefert die reale Konfiguration, das Core-Profil, die
hashgebundenen Sprachregisterressourcen und die regulären Projektdateien.
Es gibt keinen Ersatzvalidator, keine erfundene Freigabe und keine
Umdeutung des bisherigen Fehlers in einen erwarteten Erfolg.

Die fünf Parameteridentitäten help/version/validate/show/list, die
Originalbefehle, die Assertion Exit 0, die Importfallen für NumPy und
py3langid, die Modellladefalle und die unveränderte Dateiinventur bleiben
erhalten. Alle übrigen Testfunktionen bleiben bytegleich. Die ursprünglichen
Mehrfachanalyzer-, Modell-, Offline- und Prozessabbruchfälle bleiben erhalten.
Der gemeinsam genutzte Projekthelfer selbst wird nicht verändert.

Produktcode, Workerstart, Signalbehandlung, Modellloader, Sicherheitsgrenzen
und Fehlerverträge bleiben in jeder Stage bytegleich zum entsprechenden
ursprünglichen Zustand aus Bundle 761. Dies ist eine Testdatenkorrektur,
keine normative Spezifikationslücke: Spezifikation 0.2.99 und Entwicklungs-
vertrag bleiben bytegleich. Keine Klärung und keine Budgetänderung.

## Vollständiger offener Rest und eigene Gates

19.m.W, 19.m.R und 19.m.C behalten IDs, Rollen `implementation`, exakte
Commitnachrichten, Reihenfolge und vollständigen Umfang. `correction_of`
bindet ausschließlich diesen alten Rest. Alle erhaltenen uncommitteten
W-Dateien gehören ausdrücklich zum ersten Scope; vollständige Vorherbytes
werden an das neue Fehler-Result gebunden. Kein bereits erfolgreicher Commit
wird wiederholt und kein C-Endstand vorab ausgebracht.

Die identische Testkorrektur ist in W, R und C enthalten. C erhält sämtliche
R-Testbytes und die unveränderten Funktions-/Klassen-ASTs der Auslagerung.
Jede Stage behält ihr eigenes N=3-plus-Pflichtauswahl-Gate vor dem Commit.
Alle bisher verpflichtenden Dateien bleiben ausgewählt; native Projekt-,
Profil- und Validierungsregressionen ergänzen die Auswahl. Testidentitäten,
stabile Nummern und vorhandene Katalogbindungen bleiben erhalten.

Die vorbereiteten Ziele 838, 839 und 840 von 918 gelten erst nach dem
jeweiligen erfolgreichen Apply. Dev führt nur Syntax, statische Analyse,
reine Collection und native Paket-/Übergabevalidierung aus, keine Testkörper,
Fixtures oder Test-Unterprozesse. Dieses Bundle behauptet keinen bestandenen
neuen Verhaltenstest.

Die vorausschauend geprüfte Folge 19.n bleibt vollständig offen. Ihr reales
Integrationsgate je unterstützter Zusatzruntime ist durch die vorliegende
CPython-3.14-Paketbasis nicht für 3.10–3.13 belegt. Es wird kein verkürzter
Planschritt angehängt. Klassifikation, vollständige Plattformnachweise und
spätere Release-Abnahmen bleiben offen. Nächste Position nach dem gesamten
erfolgreichen Rest ist 19.n.W. Die ursprüngliche Vorbereitung und ihre
Nachweisgrenzen stehen unverändert in [Bundle 761](bundle-761-analyzer-model-lifetime.md).

Stageziel `19.m.W`: 838/918, erst nach eigenem Gate.
