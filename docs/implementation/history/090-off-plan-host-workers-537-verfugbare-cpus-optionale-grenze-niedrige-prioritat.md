# OFF-PLAN HOST-WORKERS-537 — verfügbare CPUs, optionale Grenze, niedrige Priorität

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN HOST-WORKERS-537 — verfügbare CPUs, optionale Grenze, niedrige Priorität

Autorität: Nutzerauftrag 1. November 2026, Spezifikation 2.5.3.
C-Korrekturbundle 536 ist erfolgreich: 6.138 Apply-Tests und Commit
`a62ff18daaaba258a2d46583b7b77cdfe7c3b1a4`. Maßgebliches Result-SHA:
`827856bd05b5d0213815847490916539c78d9dc576189c6b85892c2d3bb94e00`.
Produktfortschritt bleibt 655/900; 15.n.R bleibt der nächste Produktcommit.

Ein Bundle mit drei echten Zuständen. W verbindet automatische Host-Worker,
`--worker-limit` (Standard 10), Nice +10, manuelle Starter, Apply und CI samt
gebundenen Ressourcenbelegen. R ergänzt CPU-Quoten und Fehlergrenzen sowie
echte kleine Runner-Integrationsfälle. C vereinheitlicht ausschließlich
die gemeinsame Konfiguration ohne Verhaltensänderung. Jeder Zustand hat
eine begründete Pflichtauswahl; neue/geänderte Testdateien laufen vollständig.

W-Abnahme vorbereitet: Host- und Grenzwertauswahl, Ein-CPU-Betrieb,
verschachtelte Runner, Prioritätserhaltung, CLI-Weitergabe, unterschiedliche
CI-Planer und Jobs sowie Ablehnung widersprüchlicher Ressourcenbelege.
Dev führt keine Verhaltenstests aus. Syntax, Collection und Paketprüfung
sind keine Testabnahme. Dieses Bundle wird zunächst außerhalb des überwachten
Exchange bereitgestellt; der Nutzer hat keinen vollen Apply-Lauf beauftragt.

R-Abnahme vorbereitet: Linux-cgroup v1/v2 samt Elternquoten, Teil-CPU,
Subtree-Mounts, falsche Quoten/Policies und fehlgeschlagene Priorität.
Kleine echte Runner-Projekte prüfen Nice-Vererbung, verschachtelte Läufe,
dauerhafte Phasen, dynamische Apply-Auswahlbindung v5 sowie CI-Job und
externe Aggregatprüfung. Diese Tests werden ausschließlich im Apply ausgeführt.

C vereinheitlicht die CLI-Definition der Workergrenze im gemeinsamen Helfer
und entfernt ungenutzte Importe. Verhalten, Testauswahl und Nachweisverträge
bleiben gegenüber R unverändert. Keine Verhaltenstests im Dev ausgeführt.

### Fortsetzung nach Fehler-Result 537 mit Korrekturbundle 538

Das maßgebliche Result `specroad-apply_Result_162822_1101_2359ca.zip`
(SHA-256 `877e812bbe77856a69684a00abcceb662f36660efccd065807676cc8d8a36aa5`)
beendet W mit 6.488 bestandenen und zehn fehlgeschlagenen Tests. Kein Commit
entstand; HEAD bleibt `a62ff18daaaba258a2d46583b7b77cdfe7c3b1a4`.
Der erhaltene W-Arbeitsstand bleibt Grundlage; R und C wurden nicht ausgebracht.

Ein alter Argumenttest lehnte einen zulässigen einzelnen xdist-Worker ab.
Neun Framework-Fälle scheiterten, weil die neue Policy am Installationspfad
des Backends statt an der tatsächlich geprüften Projektwurzel ausgewählt
wurde. Die Korrektur bindet die Policy an `config.rootpath`, erhält die
isolierten negativen/seriellen Framework-Fixtures und prüft zusätzlich
deren eigene explizite Hostpolicy. Die echte Argumentdatei-Regression wird
mit einem und zwei xdist-Workern vorbereitet; ungültige Werte bleiben rot.

Bundle 538 bindet exakt dieses Fehler-Result und führt alle offenen IDs
`HOST-WORKERS-537.W`, `.R`, `.C` fort. W übernimmt seinen vollständigen
erhaltenen Umfang plus Korrektur; R und C folgen erst nach ihren echten
Apply-Gates und Commits. Registrynummern und Historie bleiben erhalten.
Vorbereitung ausschließlich statisch und per Collection, ohne Dev-Tests.
Übergabe in Exchange ist ausdrücklich beauftragt; der vorhandene Watcher
übernimmt Apply. Kein Control-/CI-Start; Produktfortschritt bleibt 655/900.
