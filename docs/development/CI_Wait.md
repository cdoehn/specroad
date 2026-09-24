# Bundleabschluss: gh-Beobachtung, Fünferzyklus und Result-Evidence

Ab Bundle 019 gilt der Nutzerauftrag vom 24.09.2026. Der Produktzähler wird durch
CI-WAIT.a.W/R/C nicht erhöht. Lokal laufen nur neue und direkt von der Änderung
betroffene Tests, vier xdist-Worker. Keine lokale Vollsuite, kein serieller Volllauf.

`behavior.yml` prüft am gepushten Abschlusscommit die vollständige parallele
Produktsuite (CPython 3.10–3.14). Jede fünfte Bundle-Nummer, zunächst 020, dann
025 und 030, verlangt zusätzlich seriell und den vorhandenen Vergleich. Die
bisherige Viererregel ist ersetzt. Zwischencommits bleiben manuell prüfbar.

Der Entrypoint veröffentlicht nach lokalen Gates die abgeschlossenen Commits
auf dev, ohne Force/Tags/main. Danach führt er `tools/watch_bundle_ci.py` mit
exaktem HEAD und Bundle-Nummer aus. gh muss im gleichen Ubuntu/Termux-Kontext
vorhanden und für Actions-Lesezugriff auf cdoehn/specroad angemeldet sein. Das
Werkzeug installiert gh nicht, zeigt keine Tokens und verändert keine Anmeldung.

Die Beobachtung nutzt ausschließlich `gh api --method GET --hostname github.com`.
Sie wartet auf den Push-Run von dev für genau diesen Commit und behavior.yml.
Ein anderer Workflow, ein manueller Lauf oder eine andere SHA sind kein Ersatz.
Run-ID und Versuch werden gebunden. Während der Wartephase erscheinen Status,
Jobs und laufende Schritte. Laufende Tests werden von diesem Werkzeug nicht
abgebrochen; die vorhandene äußere PatchHarbor-Ausführungsfrist bleibt bestehen.
API-Aufrufe haben nur eine technische Kommunikationsfrist (90 Sekunden).
Ein noch nicht sichtbarer Run wird bis zu 60-mal mit fünf Sekunden Abstand gesucht;
Netzwerkfehler werden dreimal versucht. Danach bleibt die CI unverifiziert.

Lokaler Apply, Push, GitHub-Ergebnis, tatsächliche Vollmatrix und Evidence-
Vollständigkeit sind verschiedene Angaben. Ein grüner Auswahljob allein ist kein
Volltest. Alle fünf Python-Jobs und der zum Modus passende Volltests-/Vergleichs-
Schritt müssen erfolgreich sein. Fehlgeschlagene/abgebrochene/skipped Läufe werden
nicht als bestanden umgedeutet. CI-Ausfall löscht oder verändert keine Commits.

## Transport im automatisch erzeugten Result

Der vorhandene PatchHarbor-Core bietet hier keine bestätigte Zusatzanhangs-API.
Deshalb nutzt der Entrypoint dessen bestehendes, bytegetreu erfasstes stdout:
CI-Zusammenfassung, Run-/Jobdaten und verfügbare komplette Logs werden als ZIP
gepackt und in nummerierten Base64-Datenzeilen mit SHA-256 im execution.log
transportiert. Die JSON-Strukturen sind maschinenlesbar. Das ist kein zweites
Patch-Bundle und kein Eingriff in Registry, Replay oder Result-Veröffentlichung.

Damit ist das Archiv im anschließenden Result unter `logs/execution.log` enthalten,
auch bei sauberem Working Tree und auch wenn ignorierte build-Dateien fehlen.
`tools/extract_ci_evidence.py RESULT.zip --output ci-evidence.zip` kann es später
bytegenau wiederherstellen (neue Ausgabedatei, kein Überschreiben). Der Chat kann
es direkt aus dem hochgeladenen Result lesen. Ein fehlender Endmarker oder falscher
Hash ist unvollständige Evidence, kein Erfolg. Zusätzlich bleibt eine lokale
Komfortkopie im ignorierten build-Verzeichnis. Ein manuell später neu erzeugtes
Result ohne das Ausführungslog enthält dieses CI-Archiv nicht automatisch.

Die unveränderten GitHub-Logarchive werden nicht ausgeführt oder in beliebige
Projektpfade entpackt. Evidence ist auf 64 MiB begrenzt; Überschreitungen werden
als fehlender Nachweis ausgewiesen, nicht als fehlgeschlagene Produkttests.
Ein unabhängiger GitHub-Lauf ist in der Chat-Prüfumgebung nicht nachgewiesen.

Quellen für den verwendeten Transportvertrag:
https://cli.github.com/manual/gh_api
https://docs.github.com/en/rest/actions/workflow-runs
https://docs.github.com/en/rest/actions/workflow-jobs

## Vollständige Testergebnis-Artefakte (R)

Alle fünf versionierten behavior-Artefakte werden ebenfalls abgerufen. Der Name
bindet SHA und run_attempt, damit ein Rerun nicht alte Erfolgsberichte verwendet.
Originale JSON-Reports bleiben im ZIP erhalten. Die vorhandene Vollständigkeits-
prüfung kontrolliert Testmengen, Ergebniszustände, Python-Version und Workerzahl;
der Eingangsquellhash muss zum lokalen finalen Stand passen. Im Dualmodus werden
parallel/serial und die gespeicherte Vergleichszusammenfassung erneut geprüft.
Ein fehlendes oder defektes Artefakt kann trotz grünem GitHub-Status den separaten
Evidence-Status unvollständig machen; das wird nicht verschwiegen. Ein fehlender
abschließender unveränderter Run-/Attempt-Beleg verhindert einen Erfolgsausweis.
Es werden keine normalen CLI-Texte als Nachweis von Testvollständigkeit geparst.
