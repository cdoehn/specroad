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

Dies ist eine explizite Host-API. Automatische CLI-Auswahl des Lieferwegs,
normative Ergebnislieferung, mehrteilige Resultate und ein eigenes Protokoll für
ausgelagerte große Diagnosen bleiben offen. Quelle, kanonischer Payload und
Nachprüfung liegen noch vollständig im Speicher; begrenzte I/O-Blöcke sind kein
inkrementeller Ergebnisgenerator. Der Requirement-Nachweis bleibt partiell.
