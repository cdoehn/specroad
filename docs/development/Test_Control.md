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

Einzelne Tests gezielt verlagern:

```sh
python3 tools/test-control --json status
python3 tools/test-control --json move --run RUN_AUS_STATUS --attempt VERSUCH_AUS_STATUS --target-host HOST
```

`attempts` zeigt die aktuell laufenden Versuchsschlüssel, Worker, Hosts und
Testnamen. Der Auftrag gilt genau diesem Versuch und Lauf. Die erste Antwort
bestätigt nur die Speicherung; `moves` im Status meldet `restarted` oder die
konkrete Ablehnung. Wiederholung desselben Auftrags legt keinen zweiten an.
Der Zielhost muss bereits geprüft, eingeschaltet und frei sein. Der Runner
reserviert dort einen gemeinsamen Hostslot, beendet den Quellworker samt
Unterprozessen und bestätigt dessen Ende. Erst dann startet derselbe vollständige
Test mit frischen Fixtures in einem neuen Worker. Es wird kein Python-Stack
übertragen. Andere Tests und ihre vollständige Auswahl bleiben erhalten.

Die abgeschlossenen Phasen des alten Versuchs bleiben als ungültige Messung
sichtbar; sie ersetzen keine Phase des neuen Versuchs. Der Monitor zeigt beide
Versuchskonten, kennzeichnet den alten als `cancelled` und zählt für den
Testfortschritt den neuesten Versuch. Echte Testfehler bleiben Gate-Fehler.
Bei belegtem Ziel, zwischenzeitlich beendetem Versuch oder verlorenem
Endnachweis wird nicht parallel oder automatisch auf einem Ausweichziel getestet.
Eine Zahlenänderung mit `workers` löst keine Verlagerung aus.

Die Prozessaufsicht benötigt Linux mit pidfd-Unterstützung und überwacht nur
Nachkommen des gestarteten Workers. Das Hostprofil Version 3 bindet seine
Abbruchnachweise; alte Profile bleiben ohne MOVE lesbar. Die Laufzeitdatenbank
wird erst bei bestätigtem Abbruch atomar auf Version 2 erweitert. Vorhandene
Messwerte bleiben erhalten; nur der vollständig neue Versuch kann eine gültige
Dauer liefern. Ältere Schreiber akzeptieren Version 2 nicht. Steuerdateien und
Prozess-Sockets bleiben private Laufzeitdaten außerhalb des Quellbestands.

Abbruchaufträge prüfen den Versuch erneut bei der Zielreservierung. Ein inzwischen
beendeter Test bleibt abgeschlossen; ein bereits gemeldeter Fehler wird nicht
verlagert. Ist nur die Zielreservierung zu langsam, wird der Auftrag abgelehnt
und der Ursprung läuft weiter. Ein fehlender Endnachweis nach begonnenem Abbruch
sperrt dagegen das Gate. Ein gleichzeitig gestopptes Gate oder ausgeschaltetes
Ziel erlaubt keinen Neustart. Dieselbe Anfrage wird pro Generation nur einmal
verarbeitet; fremde Apply-Pfade und ersetzte Generationen werden abgewiesen.

Die Linux-Prozessaufsicht, ihr RPC über den bestehenden Hostgateway und die
steuernde Versuchszustandsfolge liegen in getrennten Modulen. Der Monitor
liest ausschließlich die bestehende Historie und markiert deren Abbruchkonten;
er öffnet keine Steuerverbindung und startet keine Migration. Alle W/R-Abnahmen
bleiben für C verpflichtend.

## Freie Worker am Laufende: parallele Kopien

Neue live gesteuerte Apply-Hostpools verwenden Profilformat 4 und die
[Regel SPECULATE-697](../specification/SpecRoad_Spezifikation.md#2438-spekulative-testkopien--speculate-697).
Noch nicht gestartete Tests haben Vorrang. Erst ohne Warteschlange reserviert
der Controller freie Slots für zusätzliche Kopien: geringste globale
Kopienzahl, zunächst verschiedene aktivierte Hosts, bei Gleichstand stabile
Testidentität. Hostgeschwindigkeit und geschätzte Restdauer gehen nicht ein.

Auch ein für pytest-`nextitem` vorgemerkter Folgetest zählt als ungestartet.
Ist der globale Vorrat leer und auf einem aktivierten Host ein Worker frei,
gibt der Controller eine solche Reservierung hinter einem noch laufenden
Original frei. Zuerst entzieht er dem bisherigen Worker die Startberechtigung
für diesen Folgetest, dann stellt er ihn wieder in die normale Warteschlange.
Der aktuelle Test läuft mit seinen Fixtures weiter; sein Worker führt den
entzogenen Folgetest nicht mehr aus und läuft danach aus. Er zählt bis dahin
weiter als belegter Prozess seines Hosts. So landet der Folgetest nicht nur
in einem neuen Prozess hinter demselben belegten Hostslot.

Diese Übergabe beginnt keinen zweiten Versuch: Der Folgetest wurde noch nie
gestartet. Seine erste Ausführung hat weiterhin Vorrang vor allen Kopien.
Erst wenn auch er tatsächlich gestartet wurde, darf die bestehende Kopienwahl
greifen. Bei Pause, fehlender freier Kapazität, laufender MOVE-Übergabe oder
angefordertem Abbruch wird keine Reservierung freigegeben. Profilformate 1–3
behalten ihre bisherigen Abläufe. Die Laufzeitdatenbank benötigt dafür keine
Migration; nicht gestartete Reservierungen werden nicht als Messung ausgegeben.

Jede Kopie erhält einen frischen Workerprozess. Der erste vollständige
Protokollabschluss einschließlich Teardown entscheidet. Übrige laufende
Kopien werden über ihre bestehende Prozessaufsicht samt Unterprozessen
beendet; ein fehlender Endnachweis lässt das Gate scheitern. Ein gleichzeitig
regulär fertig gewordener Verlierer bleibt mit seinem echten Ergebnis erhalten.
Tatsächliche Fehler irgendeiner Kopie bleiben Fehler. Ein ausgefallener Worker
wird dadurch weder als Erfolg gewertet noch automatisch wiederholt.

Die Laufzeitdatenbank wird beim Start eines Format-4-Laufs atomar auf Version 3
erweitert. Alle vorhandenen Werte und Hostbindungen bleiben erhalten; alte
Schreiber lehnen das neue Format ab. Eigene Reservierungen, Versuchskonten und
der kanonische Gewinner trennen vollständige Messungen von abgebrochenen
Kopien. Für die nächste Laufzeitauswahl zählt die aktuelle aufgelöste Gruppe;
Fehler oder offene Versuche erlauben keinen Rückgriff auf ältere Erfolge.

`test-monitor` und `--once --json` zeigen die Versuchskonten mit Host/Worker,
`copy_role`, `copy_state` und `attempt_token`. Die Übersicht zählt jeden Test
einmal; eine volle Fortschrittsanzeige ersetzt nicht die Bestätigung der
verbleibenden Abbrüche. Hostzahlen lassen sich weiterhin mit `workers` ändern.
Eine manuelle MOVE-Anfrage für einen bereits vervielfachten Test wird abgewiesen;
während einer angenommenen MOVE-Reservierung beginnen keine weiteren Kopien.
Alte Profilformate 1–3 und ihre Nachweise behalten ihre bisherigen Verträge.
