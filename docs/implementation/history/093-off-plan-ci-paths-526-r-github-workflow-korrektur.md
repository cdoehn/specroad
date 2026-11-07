# OFF-PLAN CI-PATHS-526.R — GitHub-Workflow-Korrektur

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN CI-PATHS-526.R — GitHub-Workflow-Korrektur

Nutzerauftrag vom 31. Oktober 2026: den Startup-Fehler aus Bundle 525
korrigieren. Der manuelle GitHub-Lauf 41215674922 endete vor jedem Testjob
mit `startup_failure`. Sechs `runner.temp`-Ausdrücke standen unzulässig im
Job-`env`; die lokalen Python-/Apply-Nachweise prüften diesen Kontext nicht.

Ein einzelner Korrekturcommit setzt die sechs Pfade in den drei betroffenen
Jobs durch einen ersten Bash-Schritt aus `RUNNER_TEMP` und schreibt sie nach
`GITHUB_ENV`. Run, Attempt, Python-Version und Paketnummer bleiben in den
Pfaden gebunden. Der vollständige Umfang aus Spezifikation 2.5.1 bleibt
unverändert; es gibt keine neue Fachregel und keinen Produktplanfortschritt.
Der nächste Produktcommit bleibt 15.m.C bei 653/900.

Die kleinere gezielte Testauswahl deckte zusätzlich zwei Import-Nebenwirkungen
in den neuen Pakettests auf: Der erst während eines Tests geladene gemeinsame
Fixture-Helfer änderte `sys.path`. Beide Tests importieren den Helfer jetzt
während der Collection. Testidentitäten und der Isolationswächter bleiben
unverändert; ein späterer fremder Zustandswechsel wird weiterhin abgelehnt.

Vor Übergabe: actionlint 1.7.12 reproduziert alle sechs alten Fehler und
akzeptiert die korrigierte Datei ohne Fehler. Die tatsächlichen Startskripte
bestehen 40 parallele Fälle über fünf Python-Versionen, zwei Attempts,
Paketgrenzen 0/50 und einen Temp-Pfad mit Leerzeichen und Dollarzeichen.
Gezielte parallele CI-Regressionsprüfung und die fällige N=3-Apply-Gruppe
bleiben erforderlich. Der Entrypoint committet erst nach bestandenem Apply
und pusht ausschließlich den gebundenen dev-Stand ohne Force-Push.
Lokale CI-Regression: 160 Tests parallel bestanden.
Apply-Abschluss CI-PATHS-526: fällige Gruppe bestanden; Bundle 526 abgeschlossen.
GitHub-Vollsuite bleibt ausdrücklich manuell und durch Codex ungestartet.
