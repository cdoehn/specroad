# Bundle 794 — Registry-Erwartung und vollständiger 21.a-Rest

22. November 2026. Quelle ist das native Result mit SHA-256
`6fbe6806bae9ff8756e7ac8c839f19d9dc5e500057392ae31348b9820fb8886d`.
Es bestätigt **21.a.W** mit **25.062 bestandenen Tests** und Commit
`a7a99aa1ff7f7973ac4bc1049a0cb26abfaf4e9f`. Damit sind **889/996**
Produktpositionen bestätigt. Das folgende R-Gate scheiterte mit **einem
fehlgeschlagenen und 25.035 bestandenen Tests**; R und C sind offen.

Die exakte Registry-Erwartung in `tests/test_registry.py` enthielt noch nicht
den bereits in W implementierten Befehl `config.show`. Die unabhängige
geschlossene Sollmenge wird um diesen einen Befehl ergänzt. Duplikate,
unverfügbare Befehle und unzulässige Aliase bleiben geprüft; die Erwartung
wird nicht aus der Implementierung abgeleitet. Die entsprechende feste
Request-Sollmenge enthält den Befehl bereits. Weitere Katalogverbraucher
bleiben in der Pflichtauswahl. Keine neue Produktregel oder Klärung.

Diese Stage **21.a.C** setzt den vollständigen ursprünglichen R/C-Rest fort.
IDs, Rollen `implementation`, Reihenfolge und sämtliche alten Pflichtauswahlen
bleiben erhalten. W wird weder erneut ausgeliefert noch committed. Die
Korrekturbindung verweist genau auf **21.a.R, 21.a.C** des fehlgeschlagenen
Plans. Vorherbytes stammen aus dessen tatsächlichem erhaltenen Arbeitsstand;
der erste Commitumfang enthält den vollständigen Unterschied zum bestätigten W.

R enthält weiterhin die vollständigen Kollisions-, Legacy-, No-plan-,
Baseline-/Evidence-, Distributions- und Bootstrap-Originalprüfungen aus
[Bundle 792](bundle-792-plan-model.md) und
[Bundle 793](bundle-793-plan-model-correction.md).
C übernimmt diese Tests bytegleich und behält die bereits geplante reine
Strukturbereinigung. Beide Stufen erhalten ihr eigenes N=3-plus-Pflicht-Gate
vor dem jeweiligen Commit. Der Endstand wird nicht vorab installiert.

Dev führt keine Verhaltenstests, Fixtures oder Test-Unterprozesse aus:
**tests_run=0**. Syntax, reine Collection, vollständige Stage-Rekonstruktion
und native Paket-/Fortsetzungsvalidierung ersetzen keine Apply-Abnahme.
Spezifikation, Entwicklungsvertrag, Testnummern und Apply-Testpolicy bleiben
unverändert. Bestehende Belege werden nicht umgeschrieben. Erst nach
erfolgreichem C wären **891/996** Positionen abgeschlossen; danach folgt
unverändert **21.b.W** mit seinem vollständigen Markdownparserumfang.
Die menschlichen Schlussabnahmen bleiben offen.
