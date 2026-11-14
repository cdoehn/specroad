# Control vom aktuellen Stand starten

`control start --from-current` ist eine ausdrückliche neue Arbeitsfolge.
Der native Checkpoint erhält HEAD, Index und Arbeitsbaum; ein dirty Ausgang
ist kein Testnachweis. Neue Budgets stammen aus der lokalen Policy.
Ein gewöhnliches `start`, `resume` oder Dienstneustart behält den aktuellen
Zyklus und seine verbrauchten Budgets.

Vorgemerkte Neustarts warten auf den freien Dev-Thread, den nativen Apply-Lock
und ausstehende fremde Pakete. Sie ersetzen keine laufenden Tests.
Wiederholung einer Vormerkung verwendet dieselbe ID. Ein nach Unterbrechung
wiederverwendeter Checkpoint wird vor Aktivierung nativ erneut geprüft.
Ein inzwischen veränderter Arbeitsstand benötigt eine neue Momentaufnahme;
die alte bleibt im privaten Auftragsverzeichnis erhalten.

Der aktive Datenbankzeiger wird atomar veröffentlicht. Frühere Datenbanken
bleiben für vorhandene Leser erhalten. Verdrängte Threadwechsel-Vormerkungen
und der abgeschlossene Startauftrag werden vor Entfernung bytegleich unter
`state/start-requests/<ID>/superseded/` gesichert. Diese lokalen Daten gehören
nicht ins Repository. Ein Abbruch nach Veröffentlichung füllt kein Budget
erneut auf. `control status` zeigt `current_cycle` mit Vormerkung, Zyklus und
Quellhash; der lesende Status ist kein Auftrag und kein Apply-Erfolgsbeleg.

Ein Pfad-/Linienwechsel braucht eine passende lokale Konfiguration und einen
eigenen expliziten Start. Alte Aufträge werden nicht auf ein anderes Ziel
umgebunden. Installation, Entwicklung und Status starten keine Automatik.

## Lokale Budgeteinstellungen

`control config` liest nur die konfigurierten und effektiven Werte.
`control config --clarification-limit 30 --correction-limit 40` speichert
lokale Vorgaben; `--no-clarification` schaltet neue optionale Klärung ab,
`--clarification` wieder an. Standard beider Budgets ist zwanzig. Positive
Ganzzahlen bis zur technischen SQLite-Grenze 9223372036854775807 sind gültig;
zwanzig ist keine fachliche Höchstgrenze. Es erfolgt kein Budgetreset.

`control start --from-current --clarification-limit 35` überschreibt nur
für den ausdrücklich neuen Zyklus die Dateivorgabe. Weitere explizite
Overrides sind `--correction-limit` und `--[no-]clarification`. Sie werden
atomar mit dem Zykluszeiger gespeichert und bleiben bei gewöhnlichem
Start/Resume erhalten. Der nächste ausdrücklich neue Zyklus ohne Overrides
verwendet wieder die Datei. Priorität: Aufruf vor Datei vor Standard.

Die CLI benachrichtigt einen bereits laufenden Worker, startet oder resumed
aber keinen Dienst. Der Worker übernimmt lokale Policy zwischen Aufgaben.
Bereits gebundene Verträge, laufende Turns und vorhandene Restzähler werden
nicht verändert. Neue Folgeaufträge erhalten die neue Klärungswahl;
volle konfigurierte Budgets entstehen erst am regulären belegten
Erneuerungspunkt oder durch den ausdrücklich neuen Zyklus. Ein erschöpfter
Rest bleibt erschöpft. Alte Projektmarker mit drei/fünf Plätzen behalten
ihre historischen Grenzen. Workerzahlen gehören zur geplanten separaten
`test-control`-Bedienung und sind kein Control-Budget.

Konkurrierende CLI-Schreibzugriffe verwenden den gemeinsamen Bedienlock;
ein belegter Lock führt zur klaren Ablehnung, ohne Einstellungen zu verlieren.
Erkennbare externe Dateirennen werden mit `configuration_changed` abgewiesen.
Die Speicherung erfolgt atomar. Fehlende, beschädigte oder unsichere lokale
Dateien werden nicht durch geratenen Standard ersetzt. Ihre Reparatur benötigt
die tatsächliche Betreiberkonfiguration. Ein abgeschalteter Worker verhindert
nicht das Speichern; die Antwort trennt `saved` und `worker_notification`.
Der Status nennt zusätzlich den SHA-256 der gelesenen Konfigurationsbytes.
Ein laufender Auftrag behält seinen Vertrag auch dann, wenn diese Anzeige
bereits die für künftige Arbeit wirksamen Einstellungen zeigt.
