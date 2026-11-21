# Bundle 772 — gemessene Analyzer-Ressourcenabnahme

21. November 2026. Das native erfolgreiche Result mit SHA-256
`205230f60334a182e33deac32bb162efd9096e733be311f0b44268903a9a70af`
bestätigt 19.u.W/R/C, zuletzt `c79d58b01f49a89805fcb4f373e614b12f1e35ab`,
861/918 erledigte Produktpositionen. Kein offener Korrekturrest.

Der ausdrücklich beauftragte reale Referenzlauf vom 21. November verwendet
1000 vollständige synthetische Texte (166–440 Codepoints), einen Warm-up und
fünf kalte Parent-/Workerstarts. CPython 3.14.7, unverändertes Offlinepaket,
py3langid 0.4.0, NumPy 2.3.5, genau eine echte Modellladung pro Lauf.
Maximal 6,92 CPU-Sekunden einschließlich Kindprozess, Wallmedian 6,889543664 s,
beobachteter gleichzeitiger Parent-/Worker-RSS 236.290.048 Bytes;
konservative Obergrenze aus Lebenszeitmaxima 381.419.520 Bytes. Damit liegen
beide Ressourcen unter 120 s / 512 MiB. Die Obergrenze wird ausdrücklich
nicht als gleichzeitig gemessener RSS ausgegeben. Der unabhängige Beobachter
gehört nicht zur gemessenen Prozessmenge; GNU-time-Wrapper sind gekennzeichnet.

Die [Messmethode und Wiederverwendung](../../development/Analyzer_Resources.md)
beschreiben den Umfang. Alle 1000 Volltexte, vollständigen Berichte,
CPU-Rohwerte, komprimierten RSS-Zeitreihen, PIDs mit Startticks und
Umgebungsbeobachtungen werden gespeichert. Das Exportmanifest bindet
Original- und Exporthashes. Nur private Plattformidentität und die
Kommandozeilenpräfixe der GNU-time-Dateien werden nachvollziehbar entfernt.
Es werden weder Zahlenwerte noch Testergebnisse erfunden oder ersetzt.
Das Originalsummary bleibt unverändert und behauptet ausdrücklich keinen
Apply-Erfolg, Release oder menschliches Korpusreview.

## Getrennte Zustände

- **19.v.W:** echte Referenzdaten und unveränderte Messskripte, aktueller nativer
  Corebuild, alle vollständigen Requests/Reports, Gesamt-CPU und RSS prüfen.
- **19.v.R:** unbekannte/zu kleine Plattform, fehlende/mutierte Messdaten,
  falsche Runtime/Modelle, Parent-only-CPU, falsche Einheiten, fehlende oder
  zusätzliche Prozesse und unzureichende Speicherobergrenze verhindern Erfolg.
- **19.v.C:** Byte-/Hash-/Messdateileser vom Ressourcenorakel trennen;
  identische Funktions-ASTs, Messskripte, Referenzdaten und W/R-Testbytes.

Jede Stage erhält ihr eigenes Apply-Gate aus gefilterter fälliger N=3-Gruppe
und vollständiger Pflichtauswahl. Dev prüft nur statisch, Syntax, Collection,
Stagerekonstruktion und die native ZIP. Planwerte 862/863/864 sind Zielzustände,
die erst nach dem jeweiligen Gate und Commit bestätigt sind. Im Erfolgsfall
folgt 19.w.W. Kein Korrekturbezug und keine neue Detailklärung nötig.

Die Messung betrifft die reale `analyze_language`-API über den nativen isolierten
Transport mit dokumentiertem Messbootstrap. Sie behauptet keine Integration
des noch unvollständigen dauerhaften Dispatchers. Corestartbudgets,
Wiederaufnahme, Matrix-/Releaseabnahmen und 19.t-Korpusreviews bleiben getrennt
und offen; 19.t bleibt vor 19.y erforderlich. Keine Produktquelländerung,
Host-/Dienstkonfiguration oder Zugangsdaten in diesem Bundle.
