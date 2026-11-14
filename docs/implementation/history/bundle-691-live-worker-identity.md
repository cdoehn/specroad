# Bundle 691 — Worker-Identität und Monitor-Testumgebung

Quelle: natives Fehler-Result mit SHA-256
`50d9a89771d058d222c37ba1c83fc41e6c218e64f394b132cd6341e5097d8dbe`,
HEAD `6108db301ee1085a32410fb6f176dcf0fb07b06a`.
Bundle 690 hat keinen Commit erzeugt. LIVE.W scheiterte mit zwölf Fehlern
bei 7593 bestandenen Tests; LIVE.R/C wurden noch nicht ausgebracht. Der
vollständige erhaltene W-Arbeitsbaum ist die Basis dieser Korrektur.

## Ursachen und Korrekturen

Die drei nativen Pause-/Wiederanlauftests erreichen beim zusätzlichen Worker
einen fehlenden Gateway-Eintrag. xdist 3.8.0 normalisiert einen XSpec ohne
main_thread_only durch erneutes Parsen seines ursprünglichen Texts. Eine
zuvor als Attribut zugeteilte ID geht dabei verloren; execnet vergibt eine
weitere ID, die nicht in der geprüften Hostzuordnung steht. Die Live-Steuerung
setzt deshalb den von xdist verlangten Ausführungsmodus vor der nativen
ID-Zuteilung. Der ursprüngliche lokale/Proxy-Transport bleibt erhalten;
Host-, Ressourcen-, History- und Berechtigungszuordnung verwenden dieselbe ID.
Kein Ersatzhost, kein Retry und kein Umgehen der Host-/Nachweisprüfung.

Neun Monitor-Abnahmen scheitern in ihrer isolierten CLI-Kopie: Die bisherige
Vorbereitung kopierte nur Statusmodule, während der Monitor jetzt zusätzlich
den echten test-control-Leser importiert. Die Vorbereitung enthält nun dessen
kleine vollständige Modulabhängigkeit. Ihr Steuerdatenpfad wird ausdrücklich
auf den privaten Testbereich gebunden. Bestehende Assertions für zwei Linien,
Phase/History, defekte Quellen und unveränderte Datenbanken bleiben erhalten;
zusätzlich bleibt eine fehlende Steuerdatenquelle None und wird nicht erzeugt.
Produktfehler werden nicht durch einen abgefangenen Importfehler verdeckt.

Die vorhandenen nativen lokalen/Proxy-Abnahmen prüfen zusätzlich die frischen
Gateway-IDs und die Zuordnung aller nach Pause gestarteten Testkörper. Der
Null-Override-Fall verlangt genau einen neu gebundenen ausführenden Worker.
Alle Testidentitäten und dauerhaften Nummern bleiben erhalten.

Die Korrekturen gelten für W, R und C. R behält seine vollständige Konkurrenz-,
Mehr-Apply-, Dateisicherheits-, Umgebungs-, Ausfall- und Nachweisabnahme; C seine
reine Modulaufteilung. correction_of bindet den exakten alten Rest an
`9ce398e4e439a2e335478944ed0aef9f5a16bf5055c8e81054da96af1425481c`.
Stage-Zielstand: **LIVE.C**; danach **MOVE.W**, jeweils erst nach eigenem
erfolgreichem Apply-Gate und Commit. Keine neue Klärung oder Budgetänderung,
keine Wiederholung erfolgreicher START-/CONFIG-Commits. Produktstand 762/918;
MOVE bleibt die nächste vollständige geplante Gruppe vor 18.s.W.

## Prüfung

Dev: Syntax, reine vollständige Collection, erhaltene IDs/Nummern, exakte
Vorherbytes und native Result-/Bundlevalidierung. Keine ausgeführten Tests.
Alle zwölf fehlgeschlagenen Tests und sämtliche bisherigen LIVE-/Host-/
Scheduler-/History-/Gate-/Monitorabnahmen bleiben in jeder Stage verpflichtend.
Apply führt pro Stage die Vereinigung mit der fälligen gefilterten N=3-Gruppe
aus. Es gibt keinen vorweggenommenen Verhaltenserfolg und keine Schlusssuite.
