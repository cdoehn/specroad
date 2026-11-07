# TD-002 – ausschließlich parallele Volltests und nutzerseitig manuelle GitHub-CI

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## TD-002 – ausschließlich parallele Volltests und nutzerseitig manuelle GitHub-CI

Die Nutzerentscheidung vom 2. Oktober 2026 ersetzt die frühere Testauswahl und
CI-Auslösung. Die jüngste ausdrückliche Nutzerentscheidung verlangt ausschließlich
parallele Volltests in Entwicklung und Apply, auch beim letzten Zustand eines
Bundles. Der zusätzliche serielle Abschlusslauf aus der Ergänzung vom 3. Oktober
2026 ist aufgehoben. GitHub-CI ist ausschließlich manuell; der Nutzer startet
sie bei Bedarf selbst, Codex löst sie nicht aus. Ihre operative Pflege erfolgt
zentral in der lokalen AGENTS.md
des Codex-Arbeitsbereichs; ausführbare Aufrufe und Infrastruktur beschreibt
[Testing.md](../../development/Testing.md), den manuellen Workflow
[Bundle_CI.md](../../development/Bundle_CI.md). Dieser Plan enthält die fachlichen
Abnahmen und die expliziten Spezifikationsausnahmen aus TD-001.

Historische Testauswahl-/CI-Angaben in den folgenden abgeschlossenen Abschnitten
dokumentieren ausschließlich den damaligen Auftrag oder Ablauf. Sie sind keine
aktuellen Apply-Regeln und verlangen weder Teiltests anstelle der verbindlichen
Volltests noch automatische oder serielle GitHub-Läufe. Die frühere Fünferregel
bleibt aufgehoben. Kein historischer Text ersetzt tatsächliche Ausführungsnachweise.
