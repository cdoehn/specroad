# Bundle 789 — native Validierungsfälle der Pythonmatrix

22. November 2026. Das native Result mit SHA-256
`c009efc9075093ff4b3afa0ee877e8b29a74e389e5869c0ac36c7db5c7a0dfe8`
bestätigt **20.g.C** mit 8.733 bestandenen Tests und Commit
`62d396372e0baaa21372c5f84a108ebbed25f3cc`. Damit sind 885/918
Produktpositionen tatsächlich committed. Der folgende Zustand 20.h.W blieb
uncommitted: 12.144 Tests bestanden, alle zehn Rundlaufvarianten scheiterten
an derselben Erwartung für `validate` (Exitcode 5 statt 0). R/C liefen nicht.
Die vorherige Fixture-Diagnosekorrektur bleibt Teil des bestätigten Präfixes;
der damalige innere Fehler wird dadurch nicht nachträglich erklärt.

Das Rundlaufprojekt enthält Dokument, Goal und Configuration. Der öffentliche
Validator liefert dafür ohne zusätzliche Semantikdienste die vorhandenen
`document_model`-/`configuration`-Gates als nicht verfügbar. Das ist der
bestehende Vertrag aus `validation.core`, `validation.production` und
`validation._model_checks`; die Regressionen in `test_project_inspection.py`
und `test_document_structure_right.py` verlangen ausdrücklich, daraus keinen
vollständigen Erfolg zu machen. Die Matrix hatte diesen Fall falsch als
vollständige Validierung erwartet. Produktvalidator und Sicherheitsgrenzen
werden nicht an den Test angepasst.

Jede der zehn tatsächlichen Python-/Distributionskombinationen prüft nun beide
Fälle: Ein separates, nativ erzeugtes Goal-Projekt behält die erfolgreiche
vollständige Validierung samt exakter Subjectidentität und unveränderten
Dateibytes. Das unveränderte Rundlaufprojekt muss Exitcode 5, unvollständigen
Status und genau die beiden fehlenden Gates einschließlich Subjects und
Diagnosen liefern. Keine fehlende Prüfung wird als Erfolg gezählt. Der
Readerinput erhält vor seinem Dateizeugen ein leeres optionales Cacheverzeichnis
wie die bestehenden Matrix-Readerfixtures; keine Cache-Evidence oder Normdaten
werden erzeugt. Query und Rendering, Rückpaket, Hostempfang, getrenntes
synthetisches Review, echter Dry-Run/Apply und unabhängiger Zielhash bleiben
vollständig erhalten. Die strukturierte Matrix-Evidence unterscheidet die
erfolgreiche Minimalvalidierung vom verweigerten Vollständigkeitsanspruch.

Fortgeführt wird ausschließlich der vollständige Rest **20.h.W/R/C**, jeweils
mit ursprünglicher Rolle `implementation`, Nachricht und eigenem Apply-Gate.
`correction_of` bindet den öffentlichen Plan von 788 mit SHA-256
`aeec96c8c2b3578b87198fe3eaec3bdd7496c2a48e85bf6b95c9c31b40532ddf`
und genau diese drei IDs. 20.g.C und ältere erfolgreiche Commits werden nicht
wiederholt. Alle abhängigen Zielstände erhalten dieselbe Korrektur;
C behält die Funktions-/Decorator-AST von R. Die bisherigen Pflichtauswahlen
bleiben erhalten, ergänzt um die bestehenden Validierungs-/Dokumentregressionen.

Spezifikation und Entwicklungsvertrag bleiben unverändert; es wird keine
normative Detailentscheidung erfunden. Die aktive Fixture-/Katalogbindung
beschreibt die beiden Validierungsfälle und hält die fehlenden Semantikdienste
sichtbar offen. Die Berichte [787](bundle-787-python-matrix.md) und
[788](bundle-788-nested-run-diagnostics.md) bleiben historische Evidenz;
die frühere positive Vollvalidierungserwartung des Rundlaufprojekts ist ersetzt.

Dev führt nur statische Prüfung, reine Collection und native Stage-/Paket-
validierung aus: **tests_run=0**. Jeder Zielzähler gilt erst nach seinem Gate.
Nach drei erfolgreichen Stages sind 888/918 erreicht. Danach folgt 20.i.W mit
echten Referenzmessungen nach §14; der parallele Testpool ersetzt diesen
Nachweis nicht. Menschliche Reviews, vollständige Releaseabnahme und fehlende
Plattform-/Leistungsnachweise bleiben offen.
