# Bundle 710 — Worker vor ihrem Proxy abschließen

Datum: 15. November 2026. Grundlage ist ausschließlich das native Fehler-Result
`specroad-apply_Result_205552_1115_c5cdeb.zip`, SHA-256
`7a3f095a1a0555386f251e48a04c6a5f70d3fa3937f7d88b50ae39885bab2de6`,
Basiscommit `fc398fd4217296aa7832261f4ddb93549e023a64`, Fingerprint
`965cec81822a0d6c` nach `patchharbor-state-v1`, Repository
`a33ed6cf-0a97-4b73-b11a-d4239e7a2145`.

Bundle 709 erreichte im W-Gate die 100-Prozent-Anzeige, brach aber anschließend
in pytest_sessionfinish beim nativen execnet-Gruppenabbau mit
`OSError: cannot send (already closed?)` ab. Der Trace führt über
NodeManager.teardown_nodes, Group.terminate und ProxyIO.kill auf einen bereits
geschlossenen Steuerkanal. Die Auswahl umfasst 14.468 Tests; ein vollständiger
erfolgreicher Gate-/Beobachtungsbeleg fehlt. Daher wird kein bestandener Lauf
behauptet. Kein Commit entstand. 18.u.W/R/C bleiben in dieser Reihenfolge mit
Rolle implementation offen; correction_of bindet den vollständigen alten Plan
`d13b4054b01b5cf3b050b2a62461481a727f217a321fb81eec6e6d7b9e01af6f`.
Die vollständigen erhaltenen W-Dateien sind die Vorherbytes der Korrektur.

## Ursache und begrenzte Korrektur

Die sofortige Interpreterfreigabe aus Bundle 709 bleibt erforderlich und
erfolgt weiter erst nach dem vollständigen Remoteaufruf samt Unconfigure.
Die dortige Aussage zur unverändert ausreichenden Gruppenbereinigung wird
hier präzisiert: execnet 2.1.2 entfernt ein beendetes Gateway aus der aktiven
Gruppe, behält es jedoch in seiner Join-Liste. Seine Proxy-Abhängigkeit wird
beim späteren Gruppenabbau nicht mehr berücksichtigt. Endet der letzte Worker
eines Proxys vor einem lokalen Worker, kann der Proxy deshalb vor dem noch
ausstehenden ProxyIO.wait geschlossen werden.

Der versionsgeprüfte Live-Adapter wartet beim Gruppenabbau zunächst mit
execnets eigenem safe_terminate auf diese bereits beendeten Gateways. Erst
nach diesem nativen Schritt entfernt er genau diese Einträge aus der Join-Liste
und ruft den ursprünglichen Gruppenabbau auf. Proxys bleiben bis dahin offen.
Native Join-, Timeout-, Kill- und Fehlerpfade bleiben erhalten; eine Exception
wird nicht als Erfolg verschluckt. Laufende Worker, deren Testkörper, Finalizer,
Ergebnisbeweise und Schedulerentscheidungen werden dabei nicht vorzeitig beendet.
Es entstehen keine zusätzliche Versuchswiederholung oder neue Timeoutpolicy.

Der vorhandene lokale/Proxy-Drain-Integrationstest erhält einen eindeutigen
Handschlag: Der Zielhost wird auf null gesetzt, sein Test und Finalizer enden,
sein Interpreter ist beendet, während der letzte lokale Worker weiterläuft.
Nach dessen Freigabe muss der gesamte native Lauf erfolgreich schließen und
auch der bereits beendete Zielprozess eingesammelt sein. Vollständige Sechs-Test-
Abdeckung, unveränderte Hostzuordnung, eindeutige Versuche, gespeicherte Messungen
und Finalizerbelege bleiben Pflicht. Die sechs Tail-Varianten aus Bundle 709
prüfen weiterhin Unconfigure-Schutz sowie Erfolg, Teardownfehler und Prozessverlust.
Die vorhandenen Workerabbruch-, Live-, MOVE-, Kopien- und Ressourcenregressionen
bleiben ebenfalls ungefiltert verpflichtend. Test-IDs und Nummern ändern sich nicht.

## Vollständiger Rest und offene Abnahme

W enthält den vollständigen korrigierten normalen Writer-/Preflight-Ausschnitt.
R ergänzt weiterhin die angekündigten Randfall- und Receiptbeweise. C behält
sämtliche Testbytes von R und die bereits vorbereitete strukturelle Bereinigung.
Die Fehlerkorrektur ist in allen drei Zuständen enthalten. Keine neue normative
Klärung, kein Budgetwechsel, kein verkürzter Schritt und kein weiterer Anhang.
Der bestätigte Fortschritt bleibt 768/918; 771/918 und der Einstieg 18.v.W sind
erst nach drei erfolgreichen getrennten Apply-Gates und Commits erreicht.

Dev prüft nur Syntax, reine Collection, Fortsetzungsbindung und native ZIP.
Keine Testkörper, Fixtures oder Test-Unterprozesse laufen hier. Die eigentliche
Verhaltensabnahme bleibt offen für Apply. Lokale Betriebs- und Hostdaten werden
nicht in die Produkt-Payload übernommen.

Vorbereiteter Zustand **18.u.W**: Ziel nach eigenem Gate **769/918**, danach **18.u.R**.
