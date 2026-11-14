# Bundle 693 — Supervisor-Socket bei langem TMPDIR

Quelle: natives Fehler-Result mit SHA-256
`4ca52dca1115ae9a51fb7022bd68da689d573cfe48d4f3865c6d080a7e07bfe0`,
HEAD `ada987bf1f7943cf3b2e1380c37679e0e044fb22`.
Bundle 692 scheiterte bereits beim Start des ersten Workers in MOVE.W:
`OSError: AF_UNIX path too long`; anschließend meldete execnet die geschlossene
Gateway-Verbindung. Die reine Collection sammelte 27378 Tests erfolgreich.
Es wurde kein Testkörper ausgeführt und kein MOVE-Commit erzeugt.
MOVE.W/R/C bleiben mit allen IDs, Rollen und vollständigen Abnahmen offen.

## Ursache und Korrektur

Der Supervisor erzeugte seinen Kontrollsocket mit tempfile.mkdtemp im geerbten
TMPDIR. Apply kann dafür einen tiefen privaten Arbeitsbereich vorgeben. Ein
zulässiger Dateisystempfad ist nicht notwendigerweise als Unix-Socketadresse
zulässig; der Fehler entstand vor dem Start des eigentlichen Testinterpreters.

Nur das private Socketverzeichnis wird mit dem bestehenden nativen mkdtemp
unter /tmp angelegt. Zufälliger Name, Modus 0700, Geheimnisprüfung, unabhängiger
Supervisor und Beendigungsbestätigung bleiben erhalten. R/C behalten zusätzlich
Peer-/Pfadprüfungen. TMPDIR und gewöhnliche temporäre Dateien des Workers werden
nicht umgestellt; es gibt weder öffentliche Sockets noch einen Transportfallback.
Die bestehende Aufräumfolge entfernt den Socketbereich bei normalem Ende und
bestätigtem Abbruch. Dies ist eine Implementierungskorrektur im bestätigten
MOVE-Scope, keine normative Detaillücke oder neue Klärung.

Die bestehenden nativen lokalen/Proxy-MOVE-Abnahmen starten nun ausdrücklich
mit einem langen TMPDIR. Ihre echten Worker-Fixtures prüfen dessen Erhaltung
und den privaten getrennten Socketbereich, während dieselben Tests weiterhin
frische Fixtures, bestätigtes Prozessbaumende und vollständige neue Versuche
nachweisen. Die R-Abnahmen für normale und abgekoppelte Nachkommen verwenden
ebenfalls den langen Pfad und prüfen die Entfernung des Socketverzeichnisses.
Alle bisherigen Testidentitäten, Parametervarianten und Nummern bleiben erhalten.

## Gebundene Fortsetzung und Prüfung

Die Korrektur gilt für alle drei echten Stufen. correction_of bindet den
vollständigen alten Rest an
`e965917a9b9c4f7e0978be6b477b6a1175bc374a4a5615e45fcc44bb19f6b804`.
Die erste Stage behandelt alle erhaltenen Änderungen des Fehler-Results mit
vollständigen Vorherbytes. Keine erfolgreichen START-/CONFIG-/LIVE-Commits
werden wiederholt; keine Rücksetzung und keine Budgetänderung.
Zielstand dieser Stage: **MOVE.W**; danach **MOVE.R**, jeweils erst nach
eigenem erfolgreichem Apply-Gate und Commit. Die komplette zusammenhängende
MOVE-Gruppe beendet den vorrangigen Teststeuerungsauftrag; der fachlich getrennte
Produkt-Recovery-Rückbau ab 18.s.W wird nicht in diese Infrastrukturkorrektur
vorgezogen. Der Produktstand bleibt 762/918.

Dev: Syntax, reine Collection, erhaltene Testidentitäten/Nummern, vollständige
Vorherbytes und native Paketvalidierung; keine Verhaltenstests ausgeführt.
Alle ursprünglichen START/CONFIG/LIVE/MOVE- sowie Host-/Scheduler-/History-/
Gate-/Monitor-Abnahmen bleiben je Stage Pflicht. Der geänderte gemeinsame
Testhelfer ist durch sämtliche vorhandenen MOVE-Integrationsfälle abgedeckt.
Apply führt je Stage genau die Vereinigung mit der fälligen gefilterten
N=3-Gruppe aus; keine doppelte Schlusssuite oder vorweggenommene Testfreigabe.
