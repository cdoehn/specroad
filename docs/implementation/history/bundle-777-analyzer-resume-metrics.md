# Bundle 777 — Testuhr im Resume-Aufruf ausdrücklich aktivieren

Das native Fehler-Result von [Bundle 776](bundle-776-analyzer-resume-budget.md),
SHA-256 `774ffaa20a39c1f5cc8b8257836d687bde00f75511a968b4702daca1b0c54fc7`,
belegt 9.052 bestandene Tests und denselben fehlgeschlagenen Modelllebensdauer-
Test: `work.resume` meldete erneut Code 8 mit unvollständigem Ergebnis.
Kein Implementierungscommit entstand. Alle sechs offenen IDs und Rollen aus
19.w.W/R/C und 19.x.W/R/C werden vollständig mit eigenen Gates fortgeführt.

Dieser Nachweis korrigiert die Aussage aus Bundle 776, der übergebene feste
Testzähler halte bereits das Resume-Zeitfenster offen: `application.execute`
beginnt den übergebenen `WorkConsumption`-Zähler erst bei ausdrücklichen
Ressourcenoptionen oder `--metrics`. Ohne diese Aktivierung erhielt der
Analyzer-Handler weiterhin keinen Aufrufzähler und erzeugte seine native Uhr.
Die reine Übergabe des Samplers war deshalb wirkungslos.

Die Testaktion `finish` fordert jetzt `--metrics` an. Der bestehende Test
prüft zusätzlich die tatsächlichen CPU-/Wall-Quellen und Nullintervalle,
das nicht überschrittene Budget sowie beobachtete Work-Grenzen im nativen
Ergebnis. Damit kann eine unbenutzte Testuhr nicht mehr unbemerkt bleiben.
Die bisherigen Abnahmen für vollständige Coverage, genau ein Modell und
genau eine Berechnung je Subject bleiben erhalten. Andere Testaktionen,
echte Worker, neue Prozesse, Checkpoints, Fehlerfälle und Test-IDs bleiben.

Alle Produktbytes, Budgets und die drei buildgebundenen realen Messserien
bleiben pro Stage bytegleich. Die Testzähler sind ausdrücklich synthetisch
und kein Ressourcenmessbeleg. Die Pflichtauswahl umfasst sämtliche Aufrufer
des Helfers und zusätzlich die vorhandenen Runtime-Consumption-Regressionen.
Keine neue normative Entscheidung oder vorweggenommene Abnahme; menschliche
Reviews und 19.t bleiben vor 19.y offen. Jeder Commit braucht sein eigenes
erfolgreiches Apply-Gate.
