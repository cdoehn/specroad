# SRX: Strings, Mitgliedschaft und Anzahlen

Plan 4.d ergänzt `in`, `contains`, `starts_with`, `ends_with`, `length` und `count`.
Binäre Operatoren besitzen `args` mit genau zwei Ausdrücken; `length` und `count`
verwenden `arg`. Die ganze AST-Struktur wird vor Auswertung geprüft.

`length` zählt String-Codepoints, Arrayelemente oder Objektschlüssel. `count`
akzeptiert ausschließlich Arrays und entfernt keine Duplikate. Strings werden
weder normalisiert noch mit Locale-Regeln verglichen. Array-Mitgliedschaft folgt
der bereits festgelegten strikten `eq`-Semantik: Typfehler werden nicht als
Nichttreffer verschluckt. Eine gleiche JSON-Struktur darf unterschiedliche
Objektschlüsselreihenfolge besitzen; Arrayreihenfolge bleibt Teil des Werts.

Missing als Suchwert ergibt gemäß eq keinen Treffer; Missing als Container oder
String-Operand ist ein Typfehler. Die Operationen lesen ausschließlich den expliziten
Kontext und haben keine Dateiseiteneffekte. Noch keine Quantoren, Arithmetik,
Graphoperatoren oder vollständige Regel-/Profilintegration.

## Entwicklung und CI

Für die Testausführung gilt die lokale `AGENTS.md`; die technische Anleitung
steht in [Testing.md](Testing.md). Kleine Prozess-Regressionsfixtures bleiben
Teil der Testsuite und ersetzen keinen vollständigen Testlauf.

Die R-Abnahme umfasst leere/Unicode-Werte, Missing-Suchwerte, strikte Operandentypen,
linksläufige Argumentauswertung, JSON-Fremdobjektabwehr, tiefe Strukturen und portable
Distributionen. Ein Typfehler in einem bereits besuchten heterogenen Arrayelement
bleibt ein SRV110-Fehler; spätere Elemente werden dann nicht mehr ausgewertet.

Die C-Bereinigung verwendet gemeinsame typisierte Größen-, Stringpaar- und
Mitgliedschaftsbausteine. Parser und Auswerter entnehmen die Stelligkeit demselben
statischen Operatorregister; es gibt keine dynamische Registrierung.
