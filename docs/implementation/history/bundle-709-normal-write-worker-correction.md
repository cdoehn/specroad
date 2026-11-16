# Bundle 709 — vollständige Korrektur 18.u.W/R/C

Grundlage ist ausschließlich das native Fehler-Result
`specroad-apply_Result_191612_1115_827eca.zip`, SHA-256
`4ff2e2f823ab41d2dd27441248fa85612cc66d4b1635fa502246cd6498ee5998`,
Basiscommit `fc398fd4217296aa7832261f4ddb93549e023a64`, Fingerprint
`9c9a2399399c3e6f` nach `patchharbor-state-v1`, Repository
`a33ed6cf-0a97-4b73-b11a-d4239e7a2145`.

Bundle 708 scheiterte im W-Gate: 11 fehlgeschlagene und 14.292 bestandene Tests,
zusätzlich ein Workerabbruch vor Collection. Kein Commit entstand. Die offenen
IDs 18.u.W, 18.u.R und 18.u.C behalten ihre Rolle implementation und ihre
Reihenfolge. correction_of bindet den gesamten alten offenen Plan
`3b84b8005d1007731759d472674c5285ef5dd601d7d6f41a1564d114e5e0b75d`.
Die tatsächlichen uncommitteten W-Dateien bilden vollständig den Vorherstand.

## Korrekturen innerhalb der bestehenden Verträge

- Zwei echte Work-Prozessabbrüche erwarten bisher ein fehlendes Ergebnisverzeichnis.
  Work-Vorbereitung legt dieses aber schon an. Die Prüfung verlangt nun unveränderte
  vollständige Work- und Projektinventare sowie identische Checkpointbytes bei
  verweigerter Auslieferung. Fertige Belege oder Markerentfernung ersetzen weiterhin
  keine tatsächliche Freigabe des Writers.
- Ein Vergleich mit während der abschließenden Byteprüfung auftauchendem Altjournal
  verlangt jetzt die bestehende Diagnose project_corrupted, Exit 5, ohne Start
  normaler Arbeit oder automatische Reparatur. Die eingetragenen Journalbytes
  bleiben unverändert; die tatsächliche Race-Injektion bleibt erhalten.
- Fünf native Baseline-Prozessabbrüche erwarten auch beim Publikationsaufruf den
  vorgeschalteten WorkResumeError mit Exit 5 und unverändertem Work-Fehlervertrag.
  Baseline-, Objekt-, Receipt-, Checkpoint- und historische Byteprüfungen bleiben.
- Drei Varianten alter Recovery-Policy/Autorität dürfen keine automatische Recovery
  auslösen. Der aktive Owner führt unverändert zu Exit 6. Gemessene Descriptorzugriffe
  müssen beweisen, dass die große Konfiguration dabei gar nicht gelesen wird;
  die tatsächlich gelesenen Betriebsmetadaten bleiben in der kurzen Phase.

Der wiederholte Workerstartabbruch hat außerdem einen konkreten infrastrukturellen
Befund: Eine ergänzende lesende Hostdiagnose zeigte während dieses Gates erschöpften
RAM/Swap und OOM-Abschaltungen von Python-Prozessen. Die PID des abgebrochenen
Workers lässt sich daraus nicht eindeutig zuordnen. Unabhängig davon belegt der
geprüfte xdist-3.8.0-/execnet-2.1.2-Pfad einen Lebenszyklusfehler: Nach Ende eines
pytest-Workers nimmt xdist ihn aus der aktiven Menge; sein execnet-Interpreter
bleibt ohne explizites Gatewayende bis zum gesamten Gateende erhalten. Bei vielen
neuen Kopien sammeln sich so nicht mehr arbeitende Interpreter im Speicher.

Die Korrektur beendet genau das zugehörige Gateway nach dem nativen Kanalende.
Dieses folgt dem vollständigen Remoteaufruf einschließlich pytest_unconfigure.
Native Ergebnis-/Fehlerereignisse werden zuerst weitergereicht, die vorhandene
Controller-Ereignisschleife beendet anschließend das Gateway. Kein Test wird
vorzeitig abgebrochen, kein Transport geteilt beendet, kein Fehler ignoriert,
kein neuer Retry, kein neuer Testtimeout und keine Hostgeschwindigkeitsregel.
Die vorhandene native Gruppenbereinigung bleibt für das abschließende Join zuständig.

Die sechs vorhandenen Tail-Integrationsvarianten bleiben erhalten und erweitern
ihren echten lokalen/Proxy-Pfad um einen gehaltenen Unconfigure-Handshake: Ein
bereits gemeldeter Abschluss darf den Finalizer nicht töten. Nach seiner Freigabe
muss der beaufsichtigte Interpreter beendet und vom Supervisor eingesammelt sein,
während Original und neuer Tail-Worker noch laufen. Erfolgs-, Teardownfehler- und
Prozessverlustfälle behalten ihre bisherigen vollständigen Nachweise. Die nativen
Live-, MOVE-, Kopien-, Hostpool-, Workerabbruch- und Ressourcenregressionen sind
zusätzlich verpflichtend. Alle Gatefehler bleiben sperrend.

## Fortsetzung und Grenzen

Keine neue normative Entscheidung, keine neue Klärung, keine Budgetänderung.
Alle alten Testidentitäten, Parameterfälle und bereits vergebenen Nummern bleiben
identisch. W enthält den gesamten korrigierten Ausschnitt, R die erhaltenen
Randfall-/Receiptbeweisergänzungen, C ausschließlich die bisherige strukturelle
Konsolidierung mit exakt denselben Testbytes wie R. Alle abhängigen Zustände
enthalten auch die hier beschriebenen Korrekturen.

Jede Stage erhält ihr eigenes Gate vor dem Commit: fällige gefilterte N=3-Gruppe
plus vollständige ungefilterte Pflichtauswahl. Kein Endstand wird vorab installiert.
Der bestätigte Fortschritt bleibt 768/918; 771/918 und der Einstieg 18.v.W gelten
erst nach allen drei erfolgreichen Gates und Commits. Der umfangreiche offene
Rest wird vollständig abgeschlossen vorbereitet; kein verkürzter Schritt und
kein zusätzlicher Spezialwriter-Anhang. Historische Berichte bleiben unverändert.

Dev prüft ausschließlich Syntax, reine Collection und die native Bundlebindung.
Keine Testkörper, Fixtures oder Test-Unterprozesse werden hier ausgeführt.
Die neue Verhaltensabnahme bleibt Apply vorbehalten. Lokale Hostkonfigurationen
und Betriebsmaßnahmen gehören nicht in die Produkt-Payload.

Vorbereiteter Zustand **18.u.W**: Ziel nach eigenem Gate **769/918**, danach **18.u.R**.
