# CI-REPAIR – OFF-PLAN-Korrektur der Testzuordnung (Bundle 011)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## CI-REPAIR – OFF-PLAN-Korrektur der Testzuordnung (Bundle 011)

Am 22. September 2026 angeforderte Korrektur des gescheiterten GitHub-Laufs:
21 Referenzen nativer pytest-Funktionen in SR-TC-0295, SR-TC-0296 und
SR-TC-0523 werden auf die wirklich gesammelten IDs berichtigt. Der vorhandene
Produktstand bleibt 150/885, nächster Schritt 4.i.W. Es wird kein Produktplan-
Commit vorgezogen und keine Anforderungsreife erhöht.

Vor lokalen Teiltests und GitHub-Volltests wird die Katalogbindung durch echte
pytest-Sammlung geprüft: keine Testkörper/Fixtures und keine vollständige
lokale Testausführung. Neue Berichte benennen alle fehlenden Verweise. Der
Katalogcheck ist kein Volltestnachweis. Einzelheiten und Abnahmegrenzen:
[`CI_Catalog_Repair.md`](../../development/CI_Catalog_Repair.md).

`CI-REPAIR.a.R` sichert den Abbruch vor Testkörpern, exakte Berichtsverträge
und vollständige Fehlerbeobachtungen auch bei direkter xdist-Ausführung ab.
`CI-REPAIR.a.C` trennt die stabilen Testidentitäten und Berichtsverträge von
Sammlung, Prozessstart und pytest-Hooks. Die damals verwendeten lokalen Gates
waren Teiltests; ihre Auswahlregel ist durch TD-002 aufgehoben.
