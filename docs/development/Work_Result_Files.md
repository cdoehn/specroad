# Vollständige externe Work-Ergebnisse

`publish_read_only_result_files(store)` aus `specroad.work.result_files` liefert
das vollständige gespeicherte Fachresultat eines bereits abgeschlossenen
Read-only-Work-Auftrags als externe JSON-Datei. Unterstützt ist der bestehende
geschlossene Adapter für die sechs Bootstrap-Handler. Anfangsbindung, gesamte
Checkpointkette, tatsächlicher gespeicherter Handlerausgang, Ergebnisschema und
aktueller Build werden vor der Veröffentlichung erneut geprüft. Offene Arbeit
oder fehlender Work-Speicher werden dadurch nicht vervollständigt.

Die Ausgabe liegt ausschließlich im privaten `results/`-Verzeichnis des
gebundenen externen Work-Roots. Der vollständige Payload behält das ursprüngliche
Command-Ergebnisschema. Der zurückgegebene Command-Envelope enthält `result=null`
und `result_ref={path,media_type,size,sha256,result_schema}`; `summary.delivery`
ist `external`. Status, fachlicher Exit Code, Projektbindung und vollständige
Diagnosen bleiben erhalten. Es gibt keine stillschweigende Kürzung.

Ein zusätzliches kanonisches Manifest `work-result-files-v1` bindet Work-ID,
Command, Checkpointgeneration/-hash, den Hash des vollständigen ursprünglichen
Envelopes, den fachlichen Exit Code und die vollständige geordnete Dateiliste.
Der erste Umfang enthält genau eine Result-Datei; ihr relativer Pfad, Rolle,
Medientyp, Größe, SHA-256 und ursprüngliches Ergebnisschema stehen im Manifest.
Die Rückgabe bindet das Manifest selbst wiederum über Größe und Hash, ohne
eine rekursive Selbstreferenz zu erzeugen.

Der Writer erzeugt private temporäre Dateien exklusiv, schreibt alle Bytes in
begrenzten I/O-Blöcken, synchronisiert sie und veröffentlicht sie durch einen
atomaren gebundenen Dateiwechselschritt. Der Result-Payload kommt vor dem
Manifest. Währenddessen bleibt derselbe Work-Lock gehalten; Runtime,
Checkpointkette und Pfadbindungen werden erneut geprüft. Erst nach vollständiger
Nachprüfung beider Dateien wird eine `WorkResultDelivery` zurückgegeben.

Jeder Aufruf von `WorkResultDelivery.as_dict()` prüft Quelle und Ausgabebytes
frisch unter dem lesenden Work-Mutex. Eine vorhandene passende Lieferung wird
ohne erneute Dateierzeugung wiederverwendet. Fehlende oder veränderte Dateien
sind kein bestätigter Ergebnisverweis. Ein Fehler erhält den tatsächlichen
Checkpoint, bereits veröffentlichte Dateien und unvollständige eigene temporäre
Dateien. Ein ausdrücklich erneut aufgerufener Writer prüft vorhandene Resultate
und ergänzt fehlende Ausgaben; er überschreibt keine abweichenden vorhandenen
Resultate und entfernt keine alten Arbeitsdaten.

Die Ausgabe führt keinen Handler erneut aus, erzeugt keine neue
Checkpointgeneration und schreibt keine Projektdateien. Der bereits vorhandene
technische Read-only-Abschluss und diese gesonderte Dateilieferung bleiben
unterscheidbar. Normative Receipts und native Fachcommits werden hier nicht
ausgelöst oder als Work-Abschluss umgedeutet.

## Lieferung nach einem nativen Fachcommit

`publish_normative_receipt_files(store, registry=..., model=..., policy=...,
actor=..., request_id=...)` aus `specroad.work.receipt_files` liefert das bereits
bestätigte Ergebnis des bestehenden normativen Work-Adapters. Die unabhängige
Anfangsbindung, Originalplan, Actor, Request-ID, Projektroot, aktuelle Runtime
und vollständige Checkpointkette werden erneut geprüft. Die Funktion besitzt
keine Schreibautorität und nimmt keine neue Transaktions-ID entgegen.

Der native Request-Reader muss einen bestätigten historischen Receipt liefern;
zusätzlich wird dessen Transaktionsabschluss unabhängig gelesen und mit Request,
Projekt, Transaktion, Zielhash und Receipt-Verweis verbunden. Fehlende,
widersprüchliche oder unbestätigte Belege sperren die Ausgabe auch dann, wenn
alte Ergebnisdateien vorhanden sind. Ein Ausgabeversuch startet keinen Apply,
keinen Projekt-Writer-Lock und keine automatische Recovery.

Der vollständige ursprüngliche `normative-request-resolution-v1`-Datensatz
wird als kanonischer Payload geliefert, einschließlich ursprünglichem Request,
Actor, Ergebnisobjekt, erzeugten IDs und verifizierten Receipt-Verweisen. Sein
historischer Charakter bleibt ausdrücklich erhalten: Er bestätigt weder das
heutige Zielmodell noch neue Schreibberechtigung. Veränderliche
Cleanup-Beobachtungen gehören nicht zum historischen Payload.

Das Manifest `work-receipt-files-v1` bindet Work und Checkpoint, Command,
Request-ID, vollständigen Quellhash und jede Ergebnisdatei. Die Rückgabe
`NormativeWorkResultDelivery` enthält `result_ref` und `delivery_manifest`.
Jeder Zugriff mit `as_dict()` prüft alle Ausgabebytes sowie die nativen Belege
erneut. Während der atomaren Dateiveröffentlichung werden diese Quellen vor
und nach jedem Dateiwechselschritt nochmals geprüft.

Auch nach einem Prozessabbruch unmittelbar nach dem nativen Commit kann ein
neuer Controller das ursprüngliche Ergebnis liefern. Eine später ausdrücklich
gestartete native Cleanup-Recovery ändert den historischen Payload nicht.
I/O-Fehler in der Ergebnislieferung erhalten den Fachcommit, den Checkpoint und
bereits vorhandene oder unvollständige eigene Dateien. Der nächste explizite
Lieferaufruf ergänzt ausschließlich fehlende Ausgaben; er führt niemals die
ursprünglichen Operationen erneut aus. Unvollständige Dateien ergeben keinen
bestätigten Lieferverweis.

Die normative Dateilieferung erzeugt keine neue Work-Generation und behauptet
keinen normativen Work-Abschluss. Die Quellbelege und diese gesonderte Lieferung
bleiben getrennte Zustände; der laufende Vorbereitungscheckpoint bleibt erhalten.

Die interne Projektion in `work/_result_projection.py` bildet ausschließlich
Payload-Verweise, Manifeste und Ergebnisobjekte aus bereits geprüften Werten.
Sie liest keine Projekt-/Work-Dateien, nimmt keinen Lock und veröffentlicht
keine Ausgabe. Die öffentlichen Adapter behalten die Prüfung der nativen
Commit-Belege bzw. gespeicherten Handlerergebnisse, sämtliche Work-Bindungen,
die Dateiveröffentlichung und die frische Lieferprüfung. Die JSON-Verträge und
kanonischen Bytes bleiben gegenüber W/R unverändert.

Beide Adapter sind explizite Host-APIs. Automatische CLI-Auswahl des Lieferwegs,
vollständiger normativer CLI-/Work-Abschluss, mehrteilige Resultate und ein
eigenes Protokoll für ausgelagerte große Diagnosen bleiben offen. Quelle,
kanonischer Payload und Nachprüfung liegen noch vollständig im Speicher;
begrenzte I/O-Blöcke sind kein inkrementeller Ergebnisgenerator. Der
Requirement-Nachweis bleibt partiell.
