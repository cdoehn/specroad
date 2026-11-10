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

Bei laufenden Tests reicht der Hintergrund jeder Apply-Zeile über die gesamte
Terminalbreite, einschließlich der Leerfläche rechts vom Text: Der Anteil
abgeschlossener Tests ist grün, der Rest gelb. Grundlage ist der vorhandene
Zähler `beendet / ausgewählt`; daneben steht der Prozentwert. Ein Test zählt
erst nach seiner Teardown-Phase als beendet. Der Balken gehört zum aktuellen
Testgate, nicht zur gesamten W/R/C-Folge, und ist keine Restzeitprognose.
Grün bezeichnet abgearbeitete Tests, nicht bestandene Tests; Fehler werden
zusätzlich als roter Hinweis `FEHLER` mit ihrer Anzahl angezeigt. Ein
fehlgeschlagenes Gate bleibt auch ohne lesbare Testanzahl als Fehler markiert.

Freie Applies behalten den normalen Terminalhintergrund. Die Zielauswahl
wird durch einen Pfeil und bei Fokus auf der Übersicht durch Fettschrift
gekennzeichnet, ohne die ganze Zeile zu invertieren. Auch außerhalb der
Testphase, bei fehlenden oder ungültigen Zählern und bei veralteten Statusdaten
wird kein Fortschrittsbalken gezeichnet. Eine ausschließlich veraltete
Laufzeithistorie (`VERALTET: history`) verhindert den Balken eines frisch
gelesenen Testlaufs nicht. Ohne Farben bleiben Zustand, Zähler und Prozentwert
lesbar; es wird kein Hintergrundbalken erzeugt.

Die Balkenbreite passt sich an die aktuelle Fensterbreite an. Text wird nach
Terminalzellen gekürzt, ohne breite Zeichen zu zerschneiden; kombinierende
Zeichen bleiben bei ihrem Grundzeichen. Der Füllstand verwendet nur plausible
ganzzahlige Zähler mit positiver Gesamtzahl. Erst bei vollständigem Abschluss
steht `100.0 %` in der Anzeige. Unterstützt das Terminal die benötigten
Farbpaare nicht, bleibt die Übersicht mit Zählern und normalem Hintergrund
benutzbar. Diese Darstellung ändert weder Datenquellen noch Aktualisierungsrate,
Testauswahl, Laufzeitmessung oder das Format von `--once --json`.

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
setzen Startansicht und Filter. Bei Namenssortierung bezieht sich die Mindestdauer
auf die Gesamtzeit. Farben: `--color auto|always|never`, `--no-color`;
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
(`--query-timeout`, Standard 5 Sekunden) geöffnet.
Das Budget darf zwischen 0,1 und 30 Sekunden liegen. Native Statusdateien
werden begrenzt und ohne blockierende Sonderdateizugriffe gelesen; fehlerhafte
Phasen, ausgetauschte Datenbanken und widersprüchliche Lauf-/Testbindungen
erzeugen keine scheinbar gültige Messung. Pro Abfrage sind maximal 300.000
Phasen-/Seedzeilen zugelassen; eine Überschreitung wird als Fehler gemeldet.
Es erfolgt keine Schreibkonfiguration, Migration, Registrierung, Reservierung
oder Änderung an Apply/Tests.

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

## Wartung

Gemeinsamer Code liegt unter `tools/dev/status/`: `monitor.py` stellt die CLI
und den JSON-Vertrag bereit, `monitor_data.py` bindet vorhandene Apply-Berichte
und Datenbanken, `monitor_times.py` bündelt Phasenwerte und Filterregeln,
`monitor_refresh.py` kapselt die unabhängigen Abfragen, `monitor_view.py`
zeichnet die Terminalansicht und `monitor_overview.py` bündelt die Darstellung
der Apply-Zeilen samt Fortschrittsbalken. `runtime_read.py` begrenzt lesende SQLite-
Transaktionen. Die vorhandenen Statushelfer und die native Sperrabfrage werden
wiederverwendet. Es gibt keine zusätzliche Laufzeitdatenbank des Monitors.

Neue Funktionen müssen die lesende Rolle, die Trennung der Apply-Linien,
den Unterschied zwischen Messung und verstrichener Zeit sowie eindeutige
Fehler-/Veraltungszustände erhalten. Regressionen prüfen die Datenverträge,
Laufbindung und Dateierhaltung; Terminalfarben, Layout und Dokumentation
werden gemäß den gemeinsamen Entwicklungsregeln nicht als Verhalten getestet.
