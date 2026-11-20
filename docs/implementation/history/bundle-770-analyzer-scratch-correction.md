# Bundle 770 — vollständige Korrektur der Adapterabnahme

20. November 2026. Das native Fehler-Result mit SHA-256
`8ba81eee71d38701e9762d614895e567455cb089fb505b11483c819fe2d1984c`
belegt für Bundle 769 **14 fehlgeschlagene und 8320 bestandene Tests** im
ersten Gate. Es entstand kein Commit; HEAD bleibt
`bac8455b09c077cfa3dc97041bdb4c479070483d`. Alle drei Rollen `implementation`
und IDs **19.u.W/R/C** bleiben offen. Die im erhaltenen W-Arbeitsstand
vorbereiteten Häkchen sind kein Erfolg; bestätigt bleiben 858/918.

## Diagnose und begrenzte Korrektur

Die 14 Fehler betreffen alle fünf echten Runtimefälle und die neun Fälle mit
fehlerhaften Scores. Sie enden mit `analyzer_worker_failed`; die 13 kaputten
Transportantworten passieren ihre vorgesehenen Fehlerorakel. Die ursprünglichen
Logs enthalten kein Child-stderr und belegen daher nicht dessen genaue Exception.
Die statische Prüfung des gebundenen Originalwheels zeigt jedoch einen sicheren
Konflikt: `py3langid.modelio.load_model` verwendet `tempfile.TemporaryFile`,
während der neue Testbootstrap jeden Dateischreib-/Erzeugungszugriff verbietet.

Der Bootstrap bereitet vor dem Audit-Hook genau eine reguläre anonyme, bereits
entlinkte temporäre Datei vor. Nur der unveränderte Originaldecoder erhält sie
während der hashgeprüften Modellladung über seine testseitige Ressourcenfabrik;
Argumente und einmalige Entnahme werden geprüft. Die Fabrik wird zurückgesetzt,
der echte Dateihandle auch bei Fehlern geschlossen. Die vollständige LZMA-/NPZ-
Dekompression und Modellkonstruktion bleiben real. Keine globale Tempverzeichnis-
Freigabe, kein später aktivierter Schreibschutz und kein vorab geladenes Modell:
der bestehende Audit-Hook bleibt während Import, Laden und Klassifizieren aktiv.
Netzwerk-/Prozesssperren, Projektinventare, Marker und alle bisherigen Assertions
bleiben erhalten. Unerwartetes Child-stderr wird begrenzt im Testlog angezeigt,
ohne Rückgabewert, Fehlerklasse oder Produktionscode zu verändern.

Die Korrektur wird in W und allen abhängigen R/C-Zielständen berücksichtigt.
C trennt weiterhin nur Helfer: unveränderte Testbytes, Workerbytes und
Funktions-AST gegenüber dem korrigierten R. Kein Test, Parameter oder stabile
Nummer entfällt. Alle vollständigen ursprünglichen 19.u-Abnahmen bleiben gemäß
[Bundle 769](bundle-769-analyzer-acceptance.md) erhalten. Die Vorherbytes der
ersten Stage sind vollständig an den erhaltenen schmutzigen Snapshot gebunden;
der Korrekturbezug umfasst genau den alten Rest, keine wiederholten Commits.

## Nachweisgrenzen und nächste Position

Dev prüft statisch, per Syntax, reiner Collection und nativer passiver
Stagerekonstruktion/Paketvalidierung. Es führt keine Testkörper, Fixtures oder
Testprozesse aus. W, R und C behalten je ein eigenes Apply-Gate aus gefilterter
fälliger N=3-Gruppe plus ungefilterter Pflichtauswahl vor dem jeweiligen Commit.
Die vollständige ursprüngliche Runtime-Matrix bleibt in jeder Pflichtauswahl.
Zielwerte 859/860/861 gelten erst nach dem jeweiligen erfolgreichen Gate.

Nächste Position nach vollständigem 19.u bleibt **19.v.W**. Die vorgeschriebene
Referenzplattform ohne konkurrierende Last ist weiterhin nicht nachgewiesen;
die Ressourcenabnahme wird nicht simuliert, übersprungen oder als Erfolg gezählt.
19.t und menschliche Korpus-/Herkunftsreviews bleiben offen, Reviewdaten erhalten.
Es gibt keine normative Detaillücke, keinen Klärungspräfix und keinen Budgetreset.
Dieser Bericht ergänzt den historischen Vorbereitungsbericht 769 um dessen
tatsächlich fehlgeschlagenen Ausgang; er schreibt ihn nicht rückwirkend um.
