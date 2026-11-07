# Historischer Testpolicy-Nachtrag vom 21. September 2026

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Historischer Testpolicy-Nachtrag vom 21. September 2026

Die folgenden damaligen Ausführungsvorgaben sind durch TD-002 abgelöst; die
beschriebenen historischen Ergebnisse werden nicht nachträglich umgedeutet.

`TEST-POLICY.a.W` setzt den lokalen Vier-Worker-Standard und den CI-Starter um.
`TEST-POLICY.a.R` sichert Fehlerfälle und isolierte CI-Nachweise ab.
`TEST-POLICY.a.C` führt die wiederverwendbare Ausführungskonfiguration zusammen.
Die Produktfolge bleibt unverändert; danach folgt 4.d.W.

Der letzte zurückgegebene Apply-Nachweis bestätigt Bundle 005. Die früheren
Auslieferungen 003/004 wurden nicht als vollständiger Erfolg nachgetragen.

CI-Nachweise verwenden frische exklusive Verzeichnisse. Fehler, fehlende/ungültige
Berichte und nicht äquivalente Eingangsbindungen verhindern den Gesamterfolg.
Ein gemeinsamer summary.json wird nur vom Controller veröffentlicht.

CI-Referenzsteuerung und CLI-Argumente sind getrennt; lokaler Runner und CI-
Starter verwenden denselben Vier-Worker-Default. Der einzige Scheduler bleibt xdist.
