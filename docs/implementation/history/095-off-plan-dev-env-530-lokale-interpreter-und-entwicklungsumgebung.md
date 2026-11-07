# OFF-PLAN DEV-ENV-530 — lokale Interpreter und Entwicklungsumgebung

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN DEV-ENV-530 — lokale Interpreter und Entwicklungsumgebung

Ausdrücklicher Nutzerauftrag vom 31. Oktober 2026: `.python-versions`,
einen zusätzlichen lokalen Aufbaubefehl und die Anleitung in README.md
gemeinsam als ein Bundle bereitstellen. Python 3.10 bis 3.14 stehen Dev-Chats
bei Bedarf zur Verfügung; die normale lokale `.venv` und Testausführung
bleiben auf 3.14. Git und uv sind externe Voraussetzungen. Der Aufbau
installiert SpecRoad editierbar und die bestehende Dev-Gruppe, ohne Tests
oder eine lokale Versionsmatrix zu starten. Keine Änderung von Produktcore,
Produktspezifikation, CI, Control, Watcher oder systemweitem Python-Standard.

Drei echte Zwischenstände in einer ZIP, Produktstand unverändert 654/900:
W: vollständiger Aufbau und Wiederverwendung mit README und gezielter Abnahme.
R: fehlende Werkzeuge, ungültige Eingaben, bestehende Umgebungen und
fehlgeschlagene Unterprozesse mit isolierten Verhaltensfällen absichern.
C: die gemeinsame Umgebungsprüfung zusammenführen; Verhalten unverändert.
Dev prüft jeden Stand gezielt mit vier worksteal-Workern; Tests laden keine
Interpreter oder Pakete aus dem Netz. Apply prüft vor jedem Commit die
fällige N=3-Gruppe mit vorhandener Laufzeitpolicy. Alle bisherigen
Testnummern bleiben erhalten, neue Identitäten werden hinten angehängt.
15.n.W bleibt offen; dies behebt keine PatchHarbor-Transportvoraussetzung.
Eine tatsächliche Einrichtung des Laptops wird durch das Bundle nicht gestartet.
Lokale Dev-Abnahme DEV-ENV-530.W: 5 gezielte Tests bestanden, vier worksteal-Worker, vollständige Collection 22629 gültig. Kein Vollsuite- oder Apply-Nachweis.
Lokale Dev-Abnahme DEV-ENV-530.R: 27 gezielte Tests bestanden, vier worksteal-Worker, vollständige Collection 22651 gültig. Kein Vollsuite- oder Apply-Nachweis.
Lokale Dev-Abnahme DEV-ENV-530.C: 27 gezielte Tests bestanden, vier worksteal-Worker, vollständige Collection 22651 gültig. Kein Vollsuite- oder Apply-Nachweis.
Apply-Abschluss DEV-ENV-530: W/R/C-Gates erfolgreich; Bundle 530 abgeschlossen.
