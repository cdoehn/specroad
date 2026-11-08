# Test-Monitor

`test-monitor` fasst Apply-Status und Testlaufzeiten in einer nur lesenden
Terminalübersicht zusammen. Er liegt versioniert unter `tools/test-monitor`
und wird ohne Installation mit Python ab 3.10 aufgerufen:

```sh
python3 tools/test-monitor --all
python3 tools/test-monitor --apply-dir ../specroad-apply --apply-dir ../specroad-apply2
python3 tools/test-monitor --all --once --json
python3 tools/test-monitor --once --view runtimes --sort call --match merge --min-seconds 600
python3 tools/test-monitor --help
```

Die interaktive Ansicht benötigt ein Terminal mit Python-`curses`, unter Linux
Teil der Standardbibliothek. `--once` und `--once --json` importieren curses
nicht. Die bestehenden Helfer `apply_status.py` und `test_time.py` bleiben
verfügbar und behalten ihre bisherigen Schnittstellen.

## Ziele und Datenquellen

Ohne Pfadoption bestimmt die aufgerufene Repository-Kopie ihre Apply-Linie,
unabhängig vom aktuellen Arbeitsverzeichnis. `--all` zeigt die beiden bekannten
Linien und weitere benachbarte Verzeichnisse `specroad-apply*`. Fehlende oder
noch nicht eingerichtete Ziele erscheinen ausdrücklich als solche. Für andere
Verzeichnisnamen `--apply-dir` wiederholen; registrierte Ziele bestimmen ihren
Exchange aus ihrer eigenen nativen Konfiguration. Maximal 16 Ziele gleichzeitig.

`--database DATEI` überschreibt ausschließlich für ein einzelnes Ziel die
lesende Laufzeitquelle. Eine Datenbank kann nicht still beiden Linien zugeordnet
werden. Explizite Quellen müssen existieren. Die Anzeige installiert oder
ändert weder Laufzeitschreiber noch deren Policy; eine ausstehende Umstellung
wird angezeigt. [Belegungsregeln und Pfadbindung](Status_Helpers.md) gelten weiter.

## Terminalbedienung

Oben stehen Apply-Belegung, Bundle, Phase und Testfortschritt aller Ziele.
Darunter folgen die Details des ausgewählten Ziels und eine Testliste.

| Taste | Wirkung |
|---|---|
| Tab | Fokus zwischen Apply-Übersicht und Testliste |
| Pfeile / j / k | Ziel oder Test wählen |
| PgUp / PgDn, Home / End | Testliste blättern |
| 1 / 2 / 3 / 4 | Status, offene Tests, Laufzeithistorie, Fehler/Quellen |
| / | Suche in Testname und Node-ID; Enter übernimmt, Esc verwirft |
| t | Gesamtzeit, drei Phasen oder beides |
| [ / ] | Sortierfeld Gesamt / Setup / Call / Teardown / Seit Start |
| d | Dauersortierung oder deren Richtung umkehren |
| n | Namenssortierung oder deren Richtung umkehren |
| r | Quellen aktualisieren |
| ? | Hilfe |
| q / Strg-C | Nur den Monitor beenden |

Die Suche ignoriert Groß-/Kleinschreibung; eine leere Suche hebt den Filter auf.
Sortierung und Suche berücksichtigen den gesamten gelesenen Testbestand vor
der Zeilengrenze (`--limit`, Standard 200; 0 zeigt alle). Fehlende Zeiten stehen
immer hinten. Gleichstände sind nach Testidentität stabil. Die gewählte
Testidentität und Scrollposition bleiben je Ziel/Ansicht über Aktualisierungen
erhalten, solange der Test noch zu den Filtern passt. Die volle Node-ID des
ausgewählten Tests steht unter der Liste.

`--view`, `--time-view`, `--sort`, `--ascending`, `--match` und `--min-seconds`
setzen Startansicht und Filter. Farben: `--color auto|always|never`, `--no-color`;
`NO_COLOR` wirkt bei auto. `--plain` unterdrückt Farben und grafische Zeichen
in der Einmalausgabe. JSON enthält keine Terminalsteuerung.

## Was Zeiten bedeuten

Gemessene Gesamtzeit ist Setup + Call + Teardown **desselben Versuchs**. Fehlt
eine Phase, bleibt Gesamt unbekannt. Fehlende Werte erscheinen als `—`, im JSON
als `null`; eine gemessene Null bleibt 0. Importierte Baselines haben nur eine
bekannte Gesamtzeit, keine erfundenen Komponenten. Herkunft ist gekennzeichnet.

Seit Start zeigt verstrichene Wandzeit eines offenen Versuchs im gebundenen
aktuellen Apply-Lauf. Diese Zeit ist keine gemessene Call-Dauer. Ein offener
Datensatz allein beweist keinen laufenden Prozess. Ein beendeter Messlauf
begrenzt die verstrichene Zeit; alte offene Versuche in der Historie erhalten
keinen weiterlaufenden Zähler. Eine Restlaufzeit wird nicht geschätzt.

Die Historie zeigt den neuesten gestarteten Versuch pro Test. Ein neuer Fehler
oder unvollständiger Versuch verdrängt ältere Erfolge. Seine vorhandenen
Phasendauern bleiben sichtbar, gelten aber nicht als gültige Erfolgsmessung.
Der aktuelle Apply-Lauf wird unabhängig davon über Quellstand, Stage-Zeit und
native Testauswahl gebunden; ein fremder neuerer Lauf ersetzt ihn nicht.

## Aktualisierung und Einmalausgabe

Status wird standardmäßig alle 5 Sekunden, die teurere Historie alle 60 Sekunden
gelesen (`--interval`, `--history-interval`). Ziel und Quelle haben jeweils
höchstens eine laufende Abfrage. Abfragen laufen außerhalb des Bildschirmthreads;
SQLite wird mit kurzen lesenden Transaktionen, Sperrwartezeit und Abfragebudget
(`--query-timeout`, Standard 5 Sekunden) geöffnet. Keine Schreibkonfiguration,
Migration, Registrierung, Reservierung oder Änderung an Apply/Tests erfolgt.

Bei einem Lesefehler bleibt der letzte lesbare Stand mit **VERALTET** sichtbar.
Eine alte Freimeldung wird nicht als aktuelle Freigabe dargestellt. Die anderen
Ziele werden weiter gelesen. `q` wartet höchstens noch auf bereits laufende,
zeitlich begrenzte Leseabfragen; Tests und Dienste bleiben unberührt.

`--once --json` liest jede Ziel-/Quellenkombination genau einmal und beendet
den Prozess. Stdout enthält genau ein JSON-Objekt, auch bei Eingabefehlern.
Exit 0 bedeutet lesbare Momentaufnahme, Exit 2 einen Eingabe-/Quellenfehler,
Exit 130 einen Abbruch. Ein beobachteter Testfehler ist ein Datenwert, kein
Fehler der Anzeige. Es wird kein Apply-Erfolg allein aus dem Exit-Code abgeleitet.

Format 1 (`kind: specroad-test-monitor`) enthält `repositories` in Zielreihenfolge.
Jedes Ziel hat `repository` sowie `status` und `history`, jeweils mit `data`,
`stale`, `refreshing` und `error`. `status.data.report` enthält den bisherigen
Apply-Bericht; `status.data.tests` die Versuche des zugeordneten Laufs und
`history.data.tests` die neuesten Messungen. Zeitfelder je Test sind immer:

```json
{
  "setup_seconds": 0.25,
  "call_seconds": null,
  "teardown_seconds": null,
  "total_seconds": null,
  "elapsed_seconds": 12.0,
  "completed": false,
  "measurement_complete": false,
  "valid_measurement": false,
  "phase": "call"
}
```

Diese Felder sind unabhängig von `--time-view`. `phase_outcomes`, Herkunft,
Testidentität, Node-ID und Worker bleiben nachvollziehbar. `matching_tests`
und `truncated` kennzeichnen die Filter-/Zeilengrenze; das JSON kann mit
`--limit 0` vollständig ausgegeben werden. Ein Baseline-Eintrag hat
`completed: null`, weil daraus kein nativer Versuch nachgewiesen werden kann.

Der Monitor ist OFF-PLAN-Entwicklungswerkzeug. Sein Bundle 632 enthält echte
W/R/C-Zustände; Verhaltenstests und Regressionen laufen ausschließlich in
ihren jeweiligen Apply-Gates. Collection/Paketvalidierung in Dev belegen
keinen erfolgreichen Verhaltenstest. Produktposition 17.l.R bleibt offen.
