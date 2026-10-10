# Geprüfter Work-Status und expliziter Abbruch

Die Host-APIs in `specroad.work.control` arbeiten auf einem unabhängig gebundenen
`CheckpointStore`. Sie laden die vollständige gespeicherte Checkpointkette,
prüfen die aktuelle Runtime und erhalten alle vorhandenen Arbeitsdaten.

`inspect_work_status(store)` liefert `work-status-v1` mit tatsächlichem Work-Pfad,
Work-ID, Checkpointgeneration/-hash, Command und Klasse, Zustand,
Eingangs-/Buildbindung, gespeichertem Fortschritt, vollständiger Restbindung,
bekanntem Blocker und der im Manifest geprüften nächsten Datenoperation. Der
Aufruf führt keinen Handler aus, liest keinen fachlichen Projektinhalt und
schreibt weder Projekt- noch Work-Dateien. `verification_scope` bezeichnet
ausdrücklich die gespeicherte Work-Kette; die native Transaktion wurde dadurch
nicht geprüft. Ein vorhandener Checkpoint beweist kein unbekanntes Prozessende.

`next_action` ist der bestehende inerte Manifestvertrag. Er ist keine Shellzeile
und wird nicht als bereits registriertes CLI-Kommando ausgegeben. Die Rückgabe
erklärt dies mit `action_is_executable_command=false`. Ein späterer ausführender
Adapter muss seine aktuellen Berechtigungen und fachlichen Voraussetzungen
erneut prüfen. Der Status einer abgeschlossenen Work-Generation ist ebenfalls
keine neue fachliche Erfolgsentscheidung oder Bestätigung externer Ergebnisbytes.

`cancel_read_only_work(store, reason=...)` beendet einen noch laufenden Auftrag
des bestehenden geschlossenen Bootstrap-Adapters. Ein tatsächlich vorhandenes
Handlerergebnis bleibt als ursprüngliche Evidenz erhalten; es wird weder erneut
ausgeführt noch in einen erfolgreichen Gesamtabschluss umgedeutet.

`cancel_normative_preparation(store, registry=..., model=..., policy=...,
actor=..., request_id=..., reason=...)` beendet die bestehende geschlossene
ChangePlan-Vorbereitung. Actor, Request-ID, Projektroot und Originalplan bleiben
gebunden. Die Request-ID muss eine Prüfung auf bereits erfolgte Veröffentlichung
ermöglichen. Ein bestätigter Commit, eine aktive oder verwaiste native Transaktion,
widersprüchliche Belege oder fehlende Bindungen sperren den Abbruch.

Während der erneuten Prüfung und Veröffentlichung des Abbruchcheckpoints hält
der Adapter den bestehenden nativen Projektroot-Mutex. Er erzeugt dabei keinen
Projekt-Lockdatensatz und keine `.specroad/`-Dateien. Kooperierende Writer können
in diesem Zeitraum nicht beginnen. Vorher gibt es eine rein lesende Prüfung,
sodass bereits erkannte Sperren keine Work-Schreibphase auslösen. Dieses lokale
advisory Lock ist keine Sandbox gegen nicht kooperierende Fremdwriter.

Der Abbruch erzeugt genau eine atomar veröffentlichte Nachfolgegeneration mit
`state=cancelled`, `phase=cancelled`, leerer Frontier und `next_action=null`.
Die vollständigen Aufgaben-, Eingangs-, erledigten und offenen Manifeste bleiben
unverändert. In `result_parts` liegt ausschließlich der gesondert typisierte
Kontrollbeleg `work-cancellation-v1`, ohne fachliches Ergebnis oder Exit Code.
Er bindet den expliziten Grund, die ursprüngliche Auftragsbindung und den
unmittelbaren Quellcheckpoint. `diagnostic_parts` bleibt leer. Dieser
Kontrollbeleg ist keine Schreibberechtigung und kein semantischer Erfolgsreceipt.

Alle früheren Objekte und Checkpoints bleiben erhalten. Ein erneuter Aufruf mit
demselben Grund liefert denselben geprüften Abbruchstand ohne neue Generation;
ein anderer Grund überschreibt den ursprünglichen Beleg nicht. Ein vollständig
abgeschlossener Auftrag kann nicht nachträglich abgebrochen werden. Wiederaufnahme
und Finalisierung abgebrochener Arbeit werden vor Handlerausführung und erneut
unter dem Work-Lock verweigert. Native Publisher akzeptieren den Endzustand nicht.

Frühe oder späte Speicherfehler erhalten den tatsächlichen Dateistand. Ist der
atomare Pointerwechsel bereits erfolgt, bleibt die abgebrochene Generation
sichtbar; ein Fehler ist keine automatische Rücknahme. Keine Funktion entfernt
Recoverydaten, führt Recovery aus oder beginnt eine native Transaktion.

## Passive Fortsetzungsanleitung

`specroad.work.prompt.read_only_work_prompt(store, max_prompt_chars=6000)` und
`normative_work_prompt(store, registry=..., model=..., policy=..., actor=...,
request_id=..., max_prompt_chars=6000)` liefern einen strukturierten Vertrag
`work-continuation-v1` und einen daraus erzeugten Text in `work-prompt-v1`.
Die Ableitung prüft den unabhängig gebundenen Store, die vollständige aktuelle
Checkpointkette, den Runtime-Build und einen der vorhandenen geschlossenen
Adapter. Alle Prüfungen bleiben lesend; es wird keine Facharbeit begonnen.

Für Read-only-Arbeit ist der konkrete nächste Hostaufruf entweder
`resume_read_only_work` oder, nach bestätigtem Handlerergebnis,
`finalize_read_only_work`. Der Text wird niemals als Programm ausgewertet.
Normative Arbeit verlangt erneut Originalactor, Request-ID und Projektbindung.
Ein vollständig quergeprüftes natives Receipt führt zur vorhandenen reinen
Ergebnislieferung `publish_normative_receipt_files`. Ohne bestätigten Commit
wird eine verbleibende Vorbereitungsphase oder `publish_normative_work` genannt.
Ungelöste native Transaktionen verhindern gewöhnliche Fortsetzung; die
Promptableitung startet keine Recovery. Fehlende Request-Identität wird abgewiesen.

Diese Operationen sind bedingte Hostaufrufe mit ihren konkreten erforderlichen
Inputs. Sie sind keine Ausführungserlaubnis. Insbesondere Veröffentlichung
verlangt die aktuelle echte `PublicationAuthority`, einen betrieblichen
Transaktionsbezeichner und sämtliche erneuten nativen Gates. Die ursprüngliche
fachliche Request-ID wird nicht ersetzt. Historische Receipts bestätigen keinen
später veränderten Zielstand. Work- und native Belege werden vor Rückgabe erneut
geprüft; eine zwischenzeitliche Änderung verhindert die Ausgabe.

Der maschinelle Vertrag enthält Work-ID, Generation/Hash, tatsächliche lokale
Work-Lokalisierung, bestätigte Einheiten, die vollständige Restmanifestreferenz,
den exakt gebundenen Distribution-Build und die feste Hostoperation. Originale
Actor-/Request-/Plan-/Quellbindungen werden nur über einen gemeinsamen Hash
referenziert. Vollständige Argumente, Quelltexte, Planformulierungen, freie
Projektanweisungen und Umgebungsvariablen werden nicht kopiert. Pfade bleiben
typisierte Daten und werden im Text JSON-quotiert; sie wählen keinen Code aus.
Es gibt keinen Netzwerk-, Chat-, LLM-, Nachrichten- oder Kindprozessaufruf.

Die Grenze misst Unicode-Zeichen, keine vorgetäuschten Anbietertokens. Erlaubt
sind ganze Zahlen ab 1000, Default 6000. Passen die notwendigen unveränderten
Bindungen, Lokalisierung und Aktion nicht vollständig hinein, lautet der
maschinelle Fehler `prompt_required_content_exceeds_limit` mit Code 2;
Integritätsdaten und Aktionen werden niemals abgeschnitten. Die vollständige
Arbeit bleibt im Store. Ungültige Grenzwerte werden vor Work-Zugriff abgewiesen.

Seit 6.r.C liegt der unveränderte Textaufbau in `_prompt_rendering.py`. Die
maschinelle Ableitung und alle Work-/Projekt-/Belegprüfungen verbleiben im
Koordinator `prompt.py`; er ruft den Renderer an derselben Stelle auf und prüft
danach weiterhin die aktuelle Bindung. Der Renderer erhält ausschließlich den
bereits abgeleiteten Datenvertrag und die geprüfte Zeichengrenze.

Terminale Arbeit erhält keine neue Fortsetzungsanweisung. Ein gespeicherter
Checkpoint und ein historischer Fachcommit bestätigen weiterhin weder ein
unbekanntes Prozessende noch vollständige Ergebnislieferung. Der Vertrag nennt
vollständige Originalarbeit, Gates, Receipts, Lieferung und bestätigtes Prozessende
als erforderliche Erfolgsnachweise. Eine manipulierte Rückgabe ersetzt keine
frische Prüfung im tatsächlich aufgerufenen Hostadapter.

Dies sind explizite Host-APIs für bestehende geschlossene Work-Adapter. Die volle
Work-CLI, ein tatsächlich ausführbarer CLI-Fortsetzungsprompt, weitere
Workflowarten, portable Paketlokalisierung und allgemeine Wiederherstellung
bleiben offen. `work_cli_available` und `portable_package_verified` sind deshalb
ausdrücklich false. Es gibt keinen Code-8-, Release- oder vollständigen
Anforderungsnachweis.
