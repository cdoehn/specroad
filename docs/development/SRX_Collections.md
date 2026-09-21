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

Lokal/Pixel: vollständige Verhaltenstests ausschließlich parallel, vier Worker.
Kein zusätzlicher serieller Clean-Lauf. Serielle Vollreferenz und gebundener
Parallelvergleich sind ausschließlich für die vorbereitete GitHub-CI vorgesehen.
Kleine Prozess-Regressionsfixtures bleiben Teil der parallelen Testsuite; sie sind
kein zweiter serieller Produkt-Volltest. Keine Ausgabe- oder Dokumentationstests.

Die R-Abnahme umfasst leere/Unicode-Werte, Missing-Suchwerte, strikte Operandentypen,
linksläufige Argumentauswertung, JSON-Fremdobjektabwehr, tiefe Strukturen und portable
Distributionen. Ein Typfehler in einem bereits besuchten heterogenen Arrayelement
bleibt ein SRV110-Fehler; spätere Elemente werden dann nicht mehr ausgewertet.

Die C-Bereinigung verwendet gemeinsame typisierte Größen-, Stringpaar- und
Mitgliedschaftsbausteine. Parser und Auswerter entnehmen die Stelligkeit demselben
statischen Operatorregister; es gibt keine dynamische Registrierung.
