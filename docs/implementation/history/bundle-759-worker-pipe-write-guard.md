# Bundle 759 — Worker-Pipes und vollständiger offener Rest

19. November 2026. Maßgebliches natives Fehler-Result SHA-256:
`b59f5b0579b41ed603dbe8d4d8276d94db805079e567b7bee244a0c7f461b2a3`.
HEAD `3975512044566bb7e8b2c830e044e83a2a63b7a0` blieb unverändert.
Der vollständige zurückgegebene Arbeitsstand entspricht 19.l.W aus Bundle 758.
Der ursprüngliche öffentliche Plan ist an SHA-256
`02143ec747b3a53278f628cc12476e046c327fe696cdeaa1a322846d3c603485` gebunden.

Die Korrektur der Hostprofilgröße aus [Bundle 758](bundle-758-host-forecast-storage.md)
erlaubte diesmal den Teststart. Das native Result protokolliert **22081
bestandene und fünf fehlgeschlagene Tests** in 19.l.W. Kein neuer Commit
entstand. Bestätigt bleiben **834/918**; 19.l.W/R/C sind vollständig offen.
Die alten Zielwerte in den ausgebrachten Dateien sind keine Apply-Abnahme.

## Diagnose und begrenzte Korrektur

Alle fünf protokollierten Fehler kommen aus `no_write_attempts` bei erlaubtem
Workerstart: beide öffentlichen Aufrufwege in `test_analyzer_cli_binding`,
beide Requestvarianten in `test_analyzer_cli` und der Run-Fall in
`test_analyzer_work_checkpoints`. Die vorhandenen Assertions und Test-IDs
bleiben unverändert. Der Testhelfer erkennt einen versuchten Schreibzugriff,
auch wenn der öffentliche Fehlerpfad dessen Ausnahme abgefangen hat.

Statisch ist die Ursache im vollständigen Aufrufpfad sichtbar: Der bekannte
Worker erhält seinen Request über `subprocess.run(input=...)`. Python öffnet
den bereits erzeugten stdin-Pipe-Deskriptor in `Popen` mit `io.open(fd, 'wb')`.
Der Testhelfer sperrt bislang jedes schreibende `io.open`, obwohl
`allow_subprocess=True` die Prozesskommunikation ausdrücklich zulässt. Die
Fehlerlogs enthalten keine Liste der abgefangenen Argumente; die Zuordnung
zum Pipe-Öffnen ist die statische Diagnose, kein nachträglich ausgeführter Test.

Nur bei expliziter Prozessfreigabe und einem ganzzahligen, aktuell per
`fstat` als Pipe erkannten offenen Deskriptor lässt der Helfer dieses Öffnen
zu. Ein Pfad, regulärer Dateideskriptor oder ungültiger Deskriptor erhält keine
Ausnahme. Standardmäßig bleiben auch Prozesse und Pipe-Schreiböffnungen
gesperrt. Dateierzeugung, Änderungen, Löschungen, Umbenennungen und neue
Sockets bleiben in beiden Modi verboten. Verschluckte verbotene Versuche
werden weiterhin am Kontextende gemeldet. Die Inventur der Projektdateien
bleibt zusätzlich Teil der ursprünglichen Analyzer-Abnahmen.

Neue schnelle Regressionen prüfen echte binäre und textuelle stdin/stdout-
Kommunikation, Pfade und reguläre Deskriptoren über beide Open-Funktionen,
Dateisystem- und Netzwerksperren, den gesperrten Standardmodus, ungültige
Deskriptoren und einen verschluckten Dateischreibversuch nach erfolgreichem
Prozessende. Keine Struktur-, Dokumentations- oder Konsolentexttests.
Der Testhelfer ist keine Sandbox für Kindprozesse; der bekannte Worker,
isolierte Importpfad und unveränderte Produktgrenzen bleiben erforderlich.

## Fortsetzung und Nachweise

Der vollständige offene Präfix **19.l.W, 19.l.R, 19.l.C** behält seine IDs,
Rollen `implementation`, Commitnachrichten, Fachumfänge und eigenen Gates.
Die Helferkorrektur und ihre Tests gelten bereits in W und bleiben in R/C
bytegleich. Produktbytes und Hostprofilkorrektur entsprechen jeweils den
ursprünglichen drei Phasen. Erfolgreiches 19.k wird nicht wiederholt;
`correction_of` bindet genau den belegten offenen Rest des Plans aus Bundle 758.
Danach bleibt **19.m.W** die nächste Produktposition. Seine Modell-Lazy-
Loading- und Lebensdauerabnahmen werden nicht durch diese Helferreparatur
als erfüllt ausgegeben.

Alle bisher verpflichtenden Dateien bleiben ausgewählt; sämtliche direkten
Aufrufer des gemeinsamen Schreibschutzhelfers und die neuen Regressionen
gehören vollständig zu jedem Apply-Gate. Die stabile Nummerierung erhält
alle bereits ausgebrachten Identitäten. W, R und C bleiben echte getrennte
Zustände; C ändert keine Testbytes oder öffentlichen Funktions-ASTs.

Dev führt nur statische Prüfung, reine Collection und native Paket- und
Übergabevalidierung aus. Keine Testkörper, Fixtures oder Test-Unterprozesse.
Spezifikation, Entwicklungsvertrag und Budgets bleiben unverändert; es ist
keine normative Klärung nötig. Alte Berichte bleiben erhalten. Die offenen
Plattform-, Klassifikations- und Releasebelege aus Bundle 757 bleiben offen.
Zielwerte werden erst nach dem jeweiligen erfolgreichen Apply-Gate bestätigt.

Stageziel `19.l.W`: 835/918, erst nach eigenem Gate.
