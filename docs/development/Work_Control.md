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

Dies sind explizite Host-APIs für bestehende geschlossene Work-Adapter. Die volle
Work-CLI, ein konkreter CLI-Fortsetzungsprompt, weitere Workflowarten und die
allgemeine portable Wiederherstellung bleiben offen. Es gibt keinen Code-8-,
Release- oder vollständigen Anforderungsnachweis. Promptableitung und die
Abgrenzung fremder Projektanweisungen folgen im R-Schritt.
