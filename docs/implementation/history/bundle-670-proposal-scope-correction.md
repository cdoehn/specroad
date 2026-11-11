# Bundle 670 — Exakten Commitumfang der Review-Korrektur herstellen

11. November 2026. Native Quelle ist Fehler-Result 669 mit SHA-256
`5c24c140163c4be6016faa388f5ce91192c59c7c1e880ed45bfa48371bd60cb5`,
HEAD `5942700a4e579cf204b35fe55353e044f44e4be2` und vollständig erhaltenem
Arbeitsstand. Der Aufruf scheiterte bei der Ausbringung von 18.i.W mit
`Stage scope differs from the intended commit`. Es wurde kein Verhaltenstest
und kein neuer Commit ausgeführt. Der erfolgreiche Control-Präfix bleibt erhalten.

Der angekündigte W-Commit enthielt 41 Pfade; nach dem Ausbringen waren genau
40 Pfade gegenüber HEAD geändert. Die zusätzliche Datei war der historische
Bericht `bundle-668-correction-budget-stop.md`: Die Vorbereitung hatte seine
committeten Originalbytes wiederhergestellt, ihn aber aus dem vorherigen dirty
Zustand weiterhin in den Commitumfang übernommen. Der strenge Apply-Scopecheck
hat diesen Unterschied korrekt vor dem Testgate abgewiesen.

Das neue Result enthält bereits den vollständig ausgebrachten W-Zustand der
Korrektur 669 und die wiederhergestellten historischen Bytes. Diese bilden
unverändert die neue technische Basis. Bundle 670 bindet sämtliche Vorherbytes
und den vollständigen offenen Rest 18.i.W/R/C an dieses Result. Der erste
Commitumfang entspricht exakt dem Zielzustand gegenüber dem bestätigten HEAD;
die weiteren Umfänge jeweils dem Zielzustand gegenüber der vorherigen Stage.
Die lokale Paketvorbereitung prüft diese exakten Pfadmengen zusätzlich zur
vollständigen Byte-/Modusrekonstruktion. Der native Apply-Schutz bleibt unverändert.

Die Produkt-, Test- und Control-Dateien entsprechen in jeder Stage bytegleich
dem bereits vorbereiteten jeweiligen Zustand aus Bundle 669. Seine Schema- und
Befehlsvertragskorrekturen sowie alle W/R/C-Abnahmen bleiben enthalten. Die
vorhandenen reinen Collectionbelege werden nur nach erneutem Abgleich ihrer
vollständigen Quell-, Spezifikations- und Katalogbindungen verwendet; sie sind
keine bestandenen Verhaltenstests. Jeder Commit erhält weiterhin sein eigenes
N=3-plus-ungefilterte-Pflichtauswahl-Gate in Apply. Der Endstand wird nicht vorab
installiert. Erfolgreiche Commits werden nicht wiederholt und historische
Berichte bleiben unverändert.

Keine normative Klärung, Budgetänderung oder Dienstaktion. Die vorbereiteten
Planfortschritte gelten erst nach dem jeweiligen erfolgreichen Apply-Commit.
Lokale Konfigurationen, Zugangsdaten und Sessionkennungen sind nicht enthalten.

Vorbereiteter Stagezustand: `W`. Apply-Abnahme steht aus.
