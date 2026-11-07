# CI-EVIDENCE-RETRY – OFF-PLAN-Korrektur (Bundle 022)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## CI-EVIDENCE-RETRY – OFF-PLAN-Korrektur (Bundle 022)

Der Result-Nachweis von Bundle 021 zeigt einen grünen Run 36022249397 für
`2f269d1831afa2f852b72439c6bba99b8833e072`, jedoch einen einzelnen fehlgeschlagenen
Artefaktabruf für Python 3.10 (`gh_api_exit_1`). Die Jobs und das Logarchiv sind
erfolgreich; der maschinenlesbare Bericht bleibt zu Recht unvollständig.
Der genaue externe Netzwerk-/API-Grund ist nicht aus diesem Fehlercode beweisbar.

- [x] `CI-EVIDENCE-RETRY`: Die vorhandene begrenzte Wiederholungslogik des
  Beobachters gilt auch für Artefaktliste und einzelne, identitätsgebundene
  ZIP-Downloads. Integritäts-/Reportfehler werden nicht durch Wiederholen
  verdeckt. Kein CI-Rerun und keine Ersetzung durch einen anderen Versuch.

Der Produktzähler blieb durch diesen Zwischencommit bei 174/885. Die damalige
Vorgabe sah nur neue und unmittelbar betroffene Beobachtertests vor. Details:
[`CI_Evidence_Retry.md`](../../development/CI_Evidence_Retry.md).
