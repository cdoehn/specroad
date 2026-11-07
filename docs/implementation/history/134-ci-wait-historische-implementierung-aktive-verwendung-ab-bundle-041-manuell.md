# CI-WAIT – historische Implementierung, aktive Verwendung ab Bundle 041 manuell

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## CI-WAIT – historische Implementierung, aktive Verwendung ab Bundle 041 manuell

- [x] `CI-WAIT.a.W` – damaliger Fünferzyklus, exakte CI-Beobachtung und Result-Logtransport.
- [x] `CI-WAIT.a.R` – vollständige Evidence-Artefakte, Wiederholungen und Ausfälle absichern.
- [x] `CI-WAIT.a.C` – GitHub-Transport, Beobachtung und Evidence-Kodierung trennen.

Die damals automatischen Aufrufe und der Fünferzyklus sind durch die neue TD-002
abgelöst. Bestehende read-only Observer bleiben für ausdrücklich angeforderte
manuelle Full-Runs und historische Recovery erhalten. Sie binden Ereignis,
Test-/Workflow-SHA, Repository, Branch, Run-ID und Attempt. Alte Push-Nachweise
verlangen einen explizit aus ihrem Result übernommenen Modus; die Bundle-Nummer
entscheidet auch beim Nachlesen nicht mehr darüber.

Manuelle CI und lokale Anwendung bleiben getrennt. Ein eigenständiger Observer
behauptet keinen erfolgreichen Pixel-Apply. Logs, Reports, Dateihashes und
Capture-/Nachweis-Vollständigkeit bleiben erhalten. Keine Rollbacks, keine
rekursiven Bundle-Aufrufe und keine erfundene Core-Anhangs-API.
Details: [CI-Nachweise](../../development/CI_Wait.md).
