# Bundle 669 — Proposal-Review-Schemas und Befehlsverträge korrigieren

11. November 2026. Native Quelle ist Fehler-Result 668 mit SHA-256
`e7aba33f3ac767d02953b75f35b07c7a6e805fe965adf5ba2109b31b3b8d5aa8`,
HEAD `5942700a4e579cf204b35fe55353e044f44e4be2` und vollständig erhaltenem
Arbeitsstand. Die drei Control-Commits CONTROL-DEFAULTS-666.W/R/C sind
bereits erfolgreich übernommen: `436efd12d615ecfc4834d7208b31d13e1262f712`,
`5b698da14ecc25f90f354a12a6bb02938ed25e2e` und
`5942700a4e579cf204b35fe55353e044f44e4be2`. Sie werden nicht wiederholt.

18.i.W scheiterte anschließend. Die native pytest-Zusammenfassung nennt
64 Fehler einschließlich drei unittest-Unterfallfehlern, acht Setupfehler
und 10470 erfolgreiche Meldungen; dies ist kein erfolgreiches Stagegate.
Die neue nullable Kommentarform verwendete in ChangePlan und Review-Ergebnis
JSON-Schema-Typlisten, die der bewusst eingeschränkte interne Validator nicht
unterstützt. Dadurch scheiterten auch Schema-Katalog, Review-start, Restore
und historische Proposal-Validierung bereits vor ihrer eigentlichen Prüfung.

Beide Kommentarverträge verwenden jetzt die vorhandene anyOf-Darstellung
für String oder null. Der Schema-Interpreter und seine Sicherheitsgrenzen
bleiben unverändert. Die vollständigen Befehls-/Schemainventare und Writer-
Deskriptorabnahmen nehmen proposal.review ausdrücklich auf; unbekannte
Befehle, unzulässige Optionen und fehlende Fachautorisierung bleiben gesperrt.
Der vorhandene native Dry-run-Fall prüft zusätzlich den Nullkommentar und
weist Zahlen, Boolesche Werte, Arrays und Objekte im Ergebnisvertrag zurück.
Der bestehende Quorumfall erhält seine Prüfung des Stringkommentars.
Keine Testidentität, Parametervariante oder vorhandene Assertion entfällt.

Die drei offenen IDs und Rollen 18.i.W/R/C bleiben vollständig erhalten.
Jeder echte Zustand wird erst nach seinem eigenen N=3-plus-Pflichtauswahl-Gate
committed; der Endstand wird nicht vorab installiert. Alle betroffenen
Proposal-, ChangePlan-, Writer-, Recovery/Restore-, CLI-, Description- und
Schema-Regressionsdateien gehören ungefiltert in die Pflichtauswahl.
Die Korrektur bindet an das neue Result und sämtliche tatsächlichen Vorherbytes.
Historische Berichte der erfolgreichen Präfixcommits bleiben bytegleich.

Keine neue normative Klärung, Budgetänderung oder Dienstaktion. Dev führt
nur Syntaxprüfung, reine Collection und native Paket-/Quellprüfung aus;
Verhaltenstests und die Abnahme der vorbereiteten Fortschrittswerte stehen
bis zum jeweiligen erfolgreichen Apply noch aus. Lokale Konfigurationen,
Zugangsdaten und Sessionkennungen sind nicht Bestandteil des Bundles.

Vorbereiteter Stagezustand: `W`. Apply-Abnahme steht aus.
