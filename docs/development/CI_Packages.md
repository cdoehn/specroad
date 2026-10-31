# Laufzeitgewichtete manuelle CI

CI-PACKAGES-525 setzt Spezifikation 2.5.1 um. Normale Dev-, Apply-, CI- und
Messläufe verwenden `worksteal`. Vier Worker sind Prozesse; bei privaten
GitHub-Ubuntu-Runnern stehen derzeit nur zwei CPUs zur Verfügung. Das
Drei-Stunden-Ziel ist daher eine Schätzung mit Reserve, keine Garantie.

## Ablauf

Der Benutzer startet weiterhin `behavior.yml` auf `dev` manuell. Der vorhandene
Selektor bindet Testcommit und Workflowcommit und wählt den Runner. Danach:

1. Jede Python-Version sammelt ihren vollständigen aktuellen Testbestand,
   liest `verification/ci_runtime_estimates.json` und erzeugt ihren eigenen Plan.
2. Die Matrixprüfung verlangt alle fünf konsistent gebundenen Pläne. Sie
   erzeugt automatisch die benötigten Kombinationen aus Python und Paket.
3. Jeder Paketjob prüft die vollständige Collection erneut, führt ausschließlich
   seine exakten Testidentitäten mit vier Worksteal-Workern aus und schreibt
   einen Teilbericht. Kein N=3 und kein Langsamtest-Ausschluss in CI.
4. Je Python-Version werden alle Pakete geprüft und zusammengeführt. Die
   ursprünglichen Belege und der Plan bleiben im vollständigen Artefakt.
   Fehlende, doppelte, anders gebundene oder nicht bestandene Tests sind Fehler.
5. Der bestehende CI-Beobachter akzeptiert vollständige neue Nachweise erst
   nach erneuter Prüfung dieser Zusammenführung. Alte Reports bleiben lesbar.

Paketanzahl und Zuordnung werden für jeden Lauf neu berechnet. Anfangswerte:
180 Minuten Ziel, davon 15 Minuten Vorbereitung/Abschluss, Faktor 1,5 auf
gemessene Einzelzeiten und 300 Sekunden Ersatzwert vor Faktor für unbekannte
oder ungültige aktuelle Werte. Die längsten Tests werden zuerst verteilt.
Zusätzlich wird die anfängliche Aufteilung von xdist 3.8.0 in gleich große
Warteschlangen berücksichtigt. Die eigentliche Ausführung und spätere
Umverteilung erledigt ausschließlich xdist. Gruppen mit gemeinsamen Fixtures
können zusätzliche Vorbereitungszeit verursachen; diese steckt in den
beobachteten Phasen und der Reserve. Es gibt keine Testabhängigkeit auf
eine frühere Ausführung eines anderen Tests.

Maximal 51 Pakete je Python-Version, insgesamt höchstens 256 Testjobs und
maximal 20 gleichzeitig. Überlauf oder ein zu langer unteilbarer Einzeltest
erzeugt eine konkrete Fehlermeldung vor den Tests. Keine stille Vergrößerung
des Ziels, keine ausgelassenen Tests. Ziel- und Faktorwerte sind Parameter des
Planers; die versionierten Workflow-Aufrufe benutzen die genannten Defaults.
Testschritt-Timeout 300 Minuten, Job-Timeout 330 Minuten. Die verbleibende Zeit
dient der Artefaktsicherung. Warteschlangen verlängern die Gesamtdauer.

## Vorhandene Laufzeiten verwenden

Jeder normale Dev-/Apply-Test schreibt bereits beim ersten Lauf die nativen
Phasen dauerhaft in die gemeinsame Exchange-Datenbank. Hierfür braucht es
keinen zusätzlichen Messlauf. Der Planer verwendet einen transportablen Export,
weil GitHub auf diese lokale Datenbank nicht zugreifen kann. Ein neuer Export
ist Teil einer bewusst geprüften Repositoryänderung, kein Seiteneffekt von
Testläufen. Bereits gemessene Tests werden zum Export nicht erneut ausgeführt.

Mit einem aktuellen reinen Collection-Bericht und einem neuen Ausgabepfad:

```sh
.venv/bin/python -I -B tools/ci_packages.py export \
  --database ../exchange/specroad-test-runtime-history.sqlite3 \
  --catalog build/current-catalog.json --output build/ci-runtime-estimates.json
```

Den geprüften Export bei einer Bundle-Erstellung als
`verification/ci_runtime_estimates.json` übernehmen. Das Werkzeug überschreibt
keine vorhandene Datei. Es liest SQLite konsistent und ohne Schreibzugriff.
Ein jüngerer fehlgeschlagener oder unvollständiger Versuch erzeugt einen
unbekannten Wert, niemals einen Rückgriff auf alten Erfolg. Veraltete Exporte
verhindern keine neuen Tests: diese werden vorsichtig geschätzt und können
automatisch zusätzliche Pakete erzeugen. Exportalter und Anzahl unbekannter
Werte sind aus Plan und Export prüfbar.

Die CI speichert je Paket `runtime-history.sqlite3`, auch mit unvollständigen
Versuchen, und die vorhandenen JSON-Berichte als Artefakt. Die Historie wird
während der Tests phasenweise gespeichert; nach dem Testschritt entsteht per
SQLite-Backup eine konsistente Kopie. Bei komplettem Runnerverlust kann kein
Upload garantiert werden. Artefakte bleiben 14 Tage verfügbar. Sie verändern
die lokale Datenbank und den versionierten Export nicht automatisch.
Vergleiche zur Kalibrierung müssen Python-Version, Workerzahl, Plattform und
Testidentität berücksichtigen; lokale und GitHub-Zeiten sind nicht identisch.

## Validierung und Betrieb

Paketplan und jeder Teilbericht binden Test-/Workflow-SHA, Python-Version,
Run-ID, Attempt, Quell-, Spezifikations- und Kataloghash. Der Planhash bindet
Regeln, Messbasis und exakte Zuordnung. Ein Hash authentifiziert keinen fremden
Ersteller; dies sind lokale Entwicklungsnachweise aus dem vertrauten Workflow.
Ein fehlgeschlagenes Paket wird nicht automatisch wiederholt. Für eine neue
Ausführung ist ein vollständiger manueller Workflow-Lauf nötig: einzelne Jobs
eines neuen Attempts dürfen keine alten Paketpläne oder Erfolge übernehmen.

Der vollständige Matrixerfolg ist keine Produkt-Releasefreigabe. Weder
Paketplanung noch Apply startet GitHub-CI, Control oder einen Dienst.
