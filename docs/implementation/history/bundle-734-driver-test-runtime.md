# Bundle 734 — native Laufzeit der Git-Treiberregressionen

Das native Result mit SHA-256
`280aa4b7874e89ee08a44cc779ac47179f7138ca3d7c280c1dd284465ce828b8`
belegt für Bundle 733 ein gestartetes C-Gate mit 9.153 bestandenen und zwölf
fehlgeschlagenen Tests. Alle zwölf Fehler betreffen die neue Datei
`tests/test_apply_uncommitted_deletions.py`: `NativeApply.install` erreicht
beim Schreiben der Testpayloads den Import von `patchharbor.models`, aber die
isolierte Testumgebung enthält keine installierte PatchHarbor-Bibliothek.
Der dreizehnte Fall ohne Schreibpayload scheitert nicht an diesem Import.
Dies ist keine erfolgreiche Abnahme der übrigen neuen Treiberfälle.

Kein neuer Commit entstand. Der bestätigte R-Commit
`eb503dfc2c6b08d95aab690d216e175cf7fbd073` und damit 788/918 Produktcommits
bleiben erhalten. Vollständig offen bleibt ausschließlich `18.n.C` mit
ursprünglicher Nachricht und Rolle `implementation`. Die Vorherbasis ist
der vollständige erhaltene Snapshot. Auch die bereits erfüllte Löschung
bleibt mit ursprünglichem Hash und vollständigen Vorherbytes gebunden.

Eine auf diese Testdatei begrenzte Fixture bindet jetzt die bereits
versionierte, hashgeprüfte PatchHarbor-1.8.0-Testlaufzeit ein. Der echte
native Payloadschreiber bleibt aktiv; weder Dateiprüfungen noch Schreib-
oder Commitpfad werden durch einen Erfolgsstub ersetzt. Die Fixture entfernt
ihre nativen Imports auch bei Fehlern und stellt zuvor vorhandene Module
sowie den Suchpfad wieder her. Es werden keine Rechnerinstallation, lokale
Konfiguration, Netzverbindung oder Betreiberregistrierung vorausgesetzt.

Alle 13 Fallidentitäten, Parameter, Testkörper und bisherigen Erwartungen
bleiben erhalten, ebenso sämtliche anderen Testdateien und stabilen
Testnummern. Produktcode, Importkorrektur und Git-Scope-Korrektur bleiben
bytegleich zum angekündigten Stand von Bundle 733. Die vollständige bisherige
Pflichtauswahl einschließlich aller fehlgeschlagenen Fälle bleibt gebunden.
Die vorhandenen nativen Transport-/Laufzeitregressionen gehören zusätzlich
zur Pflichtauswahl, um die gemeinsame Testlaufzeit weiter abzudecken.

Es gibt keine neue fachliche Detailentscheidung oder Budgetänderung.
Die Folgepositionen 18.o und 18.p behalten ihre vollständigen Work-/Review-
und Integrationsabnahmen; diese Korrektur schließt ausschließlich den
vollständigen offenen C-Rest. 789/918 und `18.o.W` als nächste Position sind
weiterhin Zielwerte, die erst nach dem eigenen erfolgreichen C-Gate und
Commit gelten. Dev führt nur Syntax, statische Prüfung, reine Collection
und native Paketvalidierung aus. Verhaltenstests bleiben Apply vorbehalten.
