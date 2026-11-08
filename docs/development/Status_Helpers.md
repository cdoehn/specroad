# Status und Testlaufzeiten

Die gemeinsame interaktive Übersicht bietet der [Test-Monitor](Test_Monitor.md):
`python3 tools/test-monitor --all`; eine maschinenlesbare Momentaufnahme liefert
`python3 tools/test-monitor --all --once --json`.

Die versionierten Einstiegspunkte liegen in `tools/apply_status.py` und
`tools/test_time.py`. Sie benötigen nur Python ab 3.10 und die Standardbibliothek.
Im Root der gewünschten Repository-Kopie:

```sh
python3 tools/apply_status.py
python3 tools/apply_status.py --all
python3 tools/test_time.py -n 10 --match merge --min-seconds 600
```

Die aufgerufene Repository-Kopie bestimmt standardmäßig das Ziel, unabhängig
vom aktuellen Arbeitsverzeichnis. `specroad-dev` / `specroad-codex` verwenden
das benachbarte `specroad-apply` und `exchange`; `specroad-dev2` verwendet
`specroad-apply2` und `exchange2`. In einer Apply-Kopie werden deren eigene
Berichte gelesen. Anders benannte registrierte Apply-Kopien verwenden ihren
konfigurierten Exchange. Fehlende oder mehrdeutige Zuordnungen werden angezeigt.

## Belegung beider Apply-Kopien

`apply_status.py --all` zeigt pro Kopie Belegung, letzten Bundle-/Phasenstand
und vorhandenen Testfortschritt. `--details` ergänzt Datenquellen und Gründe;
`--json` liefert die getrennten Berichte in `repositories`.

- `free`: Die vorhandene native Repository-Sperre wurde als frei beobachtet;
  kein zugehöriger aktiver Prozess und kein offener Fortschrittsbericht widersprechen.
- `busy`: Ein Apply-/Testprozess ist sichtbar oder die native Sperre ist belegt.
  Die Sperre allein beweist keinen laufenden Testkörper.
- `unknown`: Die Belegung ist nicht sicher feststellbar, etwa wegen fehlender
  Sperrdatei, unlesbarer Registrierung oder eines unvollständigen Berichts.
- `unregistered`: Die lokale ID oder ihre native Registrierung fehlt.
- `missing`: Das Apply-Verzeichnis fehlt; dies erscheint in der Übersicht.

Belegung und Ergebnis des letzten Laufs sind getrennte Angaben. Ein belegtes
Apply kann noch einen älteren erfolgreichen Bericht zeigen. Prozesslisten in
Containern können unvollständig sein; fehlende PIDs begründen keine Freimeldung.

Auf POSIX prüft die Anzeige kurz die vorhandene PatchHarbor-`flock`-Sperre mit
einem nur lesend geöffneten Deskriptor und einer sofort wieder freigegebenen
gemeinsamen Sperre. Sie erzeugt oder ersetzt keine Sperrdatei. Die native
Readiness-API kann Sperrdateien anlegen und wird deshalb für diese reine
Bestandsanzeige nicht aufgerufen. Andere Plattformen liefern ohne sicheren
Sperrnachweis `unknown`. Die Anzeige reserviert nichts; der Zustand kann sich
sofort ändern. Nur ein späterer nativer Apply-Aufruf prüft seine tatsächlichen
Zustandsbindungen und erwirbt die Ausführungssperre.

## Pfade und Filter

```sh
python3 tools/apply_status.py --apply-dir ../specroad-apply2
python3 tools/test_time.py --database ../exchange/archiv.sqlite3
python3 tools/test_time.py --match recovery --min-seconds 600 -n 6 --json
```

`--apply-dir PFAD` wählt die Apply-Berichte, `--database DATEI` ausdrücklich
eine vorhandene Laufzeitdatenbank. Relative Pfade beziehen sich auf das
aktuelle Arbeitsverzeichnis. Fehlende Quellen werden nicht angelegt oder
durch andere Quellen ersetzt. Die Optionen ändern keine Konfiguration und
keinen Testschreiber. `--all` kann nicht mit diesen Einzelquellen kombiniert
werden: Jede Apply-Kopie behält ihre eigene Datenquelle.

`--match TEXT` filtert Testidentitäten als Teiltext ohne Beachtung der
Groß-/Kleinschreibung; `--min-seconds` nimmt eine endliche Mindestdauer ab null.
Beide Filter wirken vor `-n` / `--count`. Gemessen wird Setup + Call + Teardown.
Nur der neueste gestartete Versuch eines Tests zählt: Laufende, fehlerhafte
oder unvollständige Versuche sperren ältere Zeiten. Importierte Baselines
gelten nur ohne neueren Versuch und werden gekennzeichnet. Der Testbestand
stammt aus der letzten gültigen Apply-Collection, ersatzweise aus der Historie.
Die Anzeige löst selbst keine Collection aus.

## Darstellung

```sh
watch -c -n 10 python3 tools/apply_status.py --all --color always
python3 tools/apply_status.py --details --width 90
python3 tools/test_time.py --plain
python3 tools/test_time.py --help
```

Farben sind im Terminal automatisch aktiv. `--color auto|always|never`,
`--no-color`, `--plain`, `--width 40..240` und `--json` steuern die Ausgabe.
`NO_COLOR` unterbindet automatische Farben, explizites `always` hat Vorrang.
JSON und Plain bleiben ohne ANSI-Farben. Lange Testnamen werden umgebrochen.
Grün zeigt bestätigte Erfolge/Freimeldungen, Gelb Hinweise, Rot Fehler und
Laufzeiten ab zehn Minuten. Balken zählen Tests/Commits oder vergleichen
gemessene Zeiten; sie schätzen keine Restlaufzeit.

Die Helfer starten weder Tests noch Apply, Watcher oder Control. Sie verändern
keine Datenbanken, Registrierung, lokalen Einstellungen oder Git-Zustände.
Gemeinsamer Code liegt in `tools/dev/status/`; die Laufzeit-Schreiber bleiben
separat konfiguriert. Eine angepasste Anzeige installiert keine neue Policy.

Die Einstiegspunkte importieren `apply_status.py` beziehungsweise `test_time.py`
aus diesem Bereich. `cli.py` bündelt Zielwahl und Terminaldarstellung;
`availability.py` kapselt die begrenzte native Registrierungs-/Sperrabfrage.
Diese Trennung ändert keine JSON-Felder oder Belegungsregeln. Die Tests prüfen
ausschließlich Datenzuordnung, native Sperrzustände, Messregeln und erhaltene
Dateien; Farben und Konsolendarstellung gehören nicht zur Verhaltensabnahme.
