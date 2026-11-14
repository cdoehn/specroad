# Laufende Testworker steuern

`python3 tools/test-control` bedient den unabhängigen Apply-Testpool. Es startet
weder Apply noch die Entwicklungsautomatik `control`. Die aufgerufene Kopie
wählt standardmäßig ihre Apply-Linie; `--apply-dir /pfad/zum/apply` wählt sie
ausdrücklich. `--json` gibt denselben Zustand maschinenlesbar aus.

```sh
python3 tools/test-control --json status
python3 tools/test-control config --host local --workers 4
python3 tools/test-control workers --run RUN_AUS_STATUS --host local --workers 0
python3 tools/test-control workers --run RUN_AUS_STATUS --host local --workers 4
```

Hostnamen stammen aus der lokalen Testhost-Konfiguration. `config` ohne Optionen
liest die gespeicherten Vorgaben. Diese gelten beim nächsten Gate. Der Runner
akzeptiert zusätzlich wiederholbares `--host-workers HOST=ZAHL`: Aufruf vor
gespeicherter Vorgabe vor geprüftem Hostmaximum. Die laufbezogene Aktion
`workers` setzt eine Sollzahl für genau die im Status bezeichnete Generation.
Ihre Antwort bestätigt die Speicherung; erst der aktualisierte Status zeigt
die Übernahme durch den Runner. Eine abgeschlossene oder ersetzte Generation
wird abgewiesen. Die Änderung füllt keine Control-Budgets auf.

Mit dem normalen konfigurierten Hostpool ist die Steuerung für lokale und
SSH-Hosts aktiv. `--local` ohne Hostpool behält den bisherigen lokalen Runner;
für steuerbaren lokalen Betrieb einen lokalen Host im Pool konfigurieren.
Die geprüfte CPU-/Host-/Aufrufgrenze ist das Maximum dieses Gates. Eine neue
Hostregistrierung oder andere Python-Umgebung benötigt ein neues geprüftes
Gate; das CLI installiert oder aktiviert keine unbekannten Rechner.

Erhöhen erzeugt zusätzliche Workerprozesse mit erneuter Prüfung des gebundenen
Snapshots und derselben vollständigen Testauswahl. Verringern beendet keinen
laufenden Versuch: vorhandene Tests einschließlich Teardown laufen aus,
unbegonnene Reservierungen gehen nach bestätigtem Worker-Ende zurück. Null
pausiert neue Zuteilung, auch auf allen Hosts gleichzeitig. Das Gate bleibt
offen und unterliegt weiterhin dem äußeren Apply-Timeout. Eine reine Änderung
der Sollzahl verlängert diesen nicht. Beim Start sammeln die geprüften
Hostworker zunächst die unveränderte Auswahl; auch Soll null erlaubt diese
Collection, aber keinen Testkörper.

Jeder Versuch belegt atomar einen gemeinsamen Hostslot bis zum Ende seines
Testprotokolls. Wartende Worker besitzen keinen solchen Slot. Mehrere Applies
teilen diese Grenze, behalten aber getrennte Sollzahlen und Messdatenbanken.
Nice mindestens +10 und IO-Klasse 2/Priorität 7 bleiben verbindlich. Hostverlust
oder eine ungültige Umgebung scheitern mit dem Gate; es gibt keine automatische
Wiederholung verlorener Tests. Ein kontrollierter Drain gibt nur ungestartete
Reservierungen zurück. Alle tatsächlich gestarteten Versuche und Phasen bleiben
der ursprünglichen Host- und Workeridentität zugeordnet.

`test-monitor` zeigt in der Detailansicht Sollzahl, laufende Versuche,
Workerprozesse und auslaufende Worker je Host. `--once --json` enthält diese
Daten unter `test_control`; der Monitor schreibt keine Steuerdateien. Eine
fehlende Steuerquelle ist keine Meldung über freie Apply-Sperren.

Die privaten Daten liegen je kanonischem Apply-Pfad unter
`$XDG_STATE_HOME/specroad/test-control` (sonst `~/.local/state/...`). Für eine
isolierte Betriebsumgebung gibt es `SPECROAD_TEST_CONTROL_HOME`. Dateiwechsel
sind atomar und Besitzer-Sperren trennen aktive von übrig gebliebenen Ständen.
Diese Dateien und Hostinventare gehören weder ins Repository noch in Bundles.
Nach einem Controllerabbruch wird ein alter Request nicht an einen neuen Lauf
übertragen; nur persistente Vorgaben bleiben erhalten.

Das gezielte Beenden und Neustarten eines einzelnen Tests gehört zur weiterhin
offenen MOVE.W/R/C-Folge und wird durch Zahlenänderungen nicht ausgelöst.
