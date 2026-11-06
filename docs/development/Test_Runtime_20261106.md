# Laufzeitbereinigung der Merge-Tests

Manueller OFF-PLAN-Auftrag vom 6. November 2026. Die Produktpositionen,
Spezifikation, Testidentitäten und Testnummern bleiben unverändert.

Die sechs längsten vollständig gemessenen Tests im vorausgehenden R-Gate
benötigten jeweils rund 18 bis 21 Minuten. Der gemessene Aufwand lag fast
vollständig im Testkörper. Dort erzeugte das synthetische Projekt mehrfach
das vollständige Sprachregister, das anschließend in Quellabbildern,
Change Plans und Journalen wiederholt verarbeitet wurde.

Die Bereinigung verändert zwei interne Kostenstellen:

- Die Publikationsmatrix verwendet ausdrücklich das vorhandene, nativ
  geparste synthetische Register für de-DE und en-GB. Der allgemeine
  Merge-Fixture behält das vollständige Register als Standard. Der kombinierte
  Publikationsfall sowie die Recoveryfälle `effect:1` und `archived` verwenden
  weiterhin das vollständige mitgelieferte Register. Damit bleiben sowohl
  erfolgreiche Publikation als auch Rollback und Abschluss in Originalgröße
  abgedeckt. Sämtliche 13 Fehlerpunkte, die drei tatsächlichen Dateiänderungen,
  Autoritäts-, Manipulations-, Replay- und Nachweisprüfungen bleiben bestehen.
- `TransitionJournal.plan` gibt den bereits im Konstruktor geprüften
  unveränderlichen `ChangePlan` zurück. Jede neue Journalaufnahme und jeder
  Nachfolger validieren weiterhin ihre eigenen Originalbytes. Es gibt keinen
  globalen Cache und keinen Cache für Live-Dateien, Berechtigungen oder
  Validierungsergebnisse. Alle bisherigen Dateizustands- und Backupprüfungen
  sowie Writer-/Recoverygrenzen bleiben unverändert.

Die bestehenden positiven Merge- und Migrationstests prüfen zusätzlich,
dass veränderte exportierte Dictionaries den gebundenen Plan nicht verändern,
dass seine Originalbytes unveränderlich sind und ein neu aufgenommenes
Journal mit falscher Planbindung abgewiesen wird. Die Prüfung verlangt keine
bestimmte Anzahl interner Parseraufrufe und keinen künstlichen Zeitgrenzwert.

Dies ist eine vollständige Bereinigung ohne neues Produktverhalten und ohne
zusätzlichen Produktplanfortschritt. Ein eigener OFF-PLAN-C-Commit erhält das
normale Apply-Gate: fällige gefilterte N=3-Gruppe plus vollständige Pflichtauswahl
der betroffenen Tests und Regressionen. Keine Tests werden entfernt, übersprungen
oder durch Erfolgsmocks ersetzt. Testmessungen bleiben in der bestehenden
Laufzeithistorie; ein Geschwindigkeitsgewinn wird erst aus den neuen tatsächlich
vollständig gemessenen Apply-Versuchen abgeleitet. Dev führt keine Verhaltenstests
aus. Collection und Paketprüfung sind keine Testabnahme.
