# SRX 1.0: Diagnosen und ausfuehrbarer Vektorkorpus

## 4.i.W – Datenvertrag statt Ausgabe-Golden

`tests/fixtures/srx_conformance_v1.json` ist ein versionierter, rein passiver
Verhaltenskorpus: Format 1, Sprache `srx`, Sprachversion `1.0`, Korpusrevision 1.
Jeder Fall hat eine stabile ID, ausdruecklichen Kontext und genau eine Erwartung:
JSON-Wert, internes Missing oder Fehler mit Code, Grund und genauem Pointer.
Alle 29 vorhandenen Operatoren besitzen Positiv-, Negativ-, Grenz- und Fehlerfaelle.
Die neun konkreten Rechenentscheidungen von Anhang U.3 sind ebenfalls enthalten.

Der Testharness unter `tests/support/srx_vectors.py` ruft die echten APIs
`SrxProgram`, `EvaluationContext`, `parse_program` und `evaluate` auf. Graphfaelle
uebergeben echte `LoadedGraph`-Objekte ueber die bereits vorhandenen Datengrenzen.
Ein unerwarteter interner Fehler ist ein Testfehler, keine erwartete Diagnose.
Der Vergleich verwendet ein unabhaengiges typgerechtes JSON-Oracle: `true` ist
nicht `1`, Missing nicht `null`, Arrayreihenfolge bleibt bedeutsam. Erwartungen
werden nie aus beobachteten Ergebnissen neu erzeugt. Tests manipulieren auch
Erwartungen, um die Ablehnung falscher Werte und Fehlerpointer nachzuweisen.

SRX-Fehler liefern zusaetzlich `diagnostic_version=1` und eine maschinenlesbare
`repair_action`. Die Empfehlung ist statisch: keine Originalwerte im Fehler,
keine ausgefuehrten Reparaturen, keine automatische Lockerung einer Policy.
Numerische Gruende bleiben disjunkt. Diagnoseversion und Korpusrevision aendern
nicht die SRX-Sprachsemantik; inkompatible freigegebene Semantik braucht weiterhin
eine neue Sprachmajorversion.

## Nachweisgrenze

Dieser Schritt fuehrt keine CLI-Fachbefehle, Profilkomposition, Schreibaktionen
oder Testabhaengigkeiten in den Produkt-Core ein. Der Korpus ist Testmaterial,
kein beim Produktstart geladener Datensatz. Die Empfehlungen sind menschliche
Darstellung; Tests fixieren ihre Formulierung nicht. Automatisiert geprueft
werden Datentypen, Fehlerfelder und Reparaturkategorien.

Lokal laufen ausschliesslich ausgewaehlte Testdateien parallel mit vier Workern.
Vollsuite und serielle Referenz gehoeren in die GitHub-CI. Eine neue lokale
Vorpruefung ersetzt weder einen Pixel-Apply noch einen vollstaendigen CI-Lauf.
