# OFF-PLAN CI-CORRECTION-592 — native Commitmetadaten und Python-Testkompatibilität

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN CI-CORRECTION-592 — native Commitmetadaten und Python-Testkompatibilität

Ausdrücklicher manueller Nutzerauftrag vom 5. November 2026. CI #42 auf
1cef31a9091ae91fb032954554050326acca2562 scheiterte vor allen Tests:
Der neue Apply-Erzeuger ließ den von der CI verlangten Bundle-Final-Trailer weg.
CI #39 und #41 belegen zusätzlich dieselben fünf Testfehler unter Python
3.10/3.12. Der aktuelle Quellstand enthält deren unveränderte Ursachen.

W ergänzt den vorhandenen Commitmetadatenvertrag, einen echten lokalen
Git-Commit/CI-Auswahl-Rundweg und begrenzte maschinenlesbare Fehlerdiagnosen.
Der letzte tatsächliche Bundle-Commit ist final; vorherige sind nicht final.
Ungültige/mehrdeutige Trailer, SHA- und Herkunftsfehler bleiben abgewiesen.
Bestehende Commits und Results werden nicht verändert.
Die CSV-Testauswertung erhält NUL-Bytes ohne Versionsannahme, die SQLite-
Fehlerinjektion endet auch auf 3.10 korrekt, und der Scandir-Beobachter gilt
nur während des Produktaufrufs. Fachliche Orakel, sämtliche ursprünglichen
Fälle, Dateiunverändertheit und Zugriffsgrenzen bleiben erhalten; keine Skips.
R ergänzt Daten mit NUL/Quotes/Zeilenumbrüchen sowie Diagnostik-, Korrektur-
und historische Commit-Auswahlgrenzen. C bündelt die Berichtsausgabe ohne
Verhaltensänderung. Jede Phase erhält ihr eigenes Apply-Gate mit N=3 und
ungefilterter Pflichtauswahl. Die spezifizierte Matrix bleibt 3.10–3.14;
ein Host-Gate ersetzt keinen vollständigen CI-Nachweis. CI startet nur der Nutzer.
Dev führt keine Verhaltenstests aus. M16 und Produktplanzähler bleiben erhalten.
Spezifikation 0.2.61 und aktive Katalogbindungen bleiben unverändert.
