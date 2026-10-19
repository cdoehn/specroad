# Dokumentprojektion über Work (11.r.W)

Die explizite Host-API `specroad.documents.work` bindet einen vollständigen,
bereits vom Aufrufer bereitgestellten `TargetModel`-Bestand und eine Dokument-ID.
Sie entdeckt keine Projektdateien und bestätigt keine Vollständigkeit auf Disk.
Der Host stellt eine geschlossene `CommandRegistry` für `document.project`:
`READ_ONLY`, `BOOTSTRAP`, `NONE`, Ergebnisvertrag `document-work-v1`, Exitcode 0.
Gespeicherte Daten registrieren keine Befehle und führen keinen Handler aus.

`prepare_document_work(registry, model, document_id)` erzeugt das unabhängige
initiale Work-Manifest. Es enthält die vollständigen gelieferten Originalbytes
von Konfiguration, Artefakten, Ressourcen und Sprachpaketen sowie passive
Profil-, Anhangs- und Reservierungsbindungen. Alte absolute Projektpfade und
Prozessidentitäten sind kein Bestandteil dieser semantischen Bindung. Der Host
bewahrt diese initiale Bindung unabhängig vom veränderlichen Work-Verzeichnis
auf und veröffentlicht sie mit dem vorhandenen `CheckpointStore` in einer
privaten `WorkDirectory` außerhalb aller geschützten Projekt-/Eingaberoots.

`advance_document_work(store, call, registry=registry, max_units=1)` verwendet
eine aktuelle `InvocationConsumption`. Die erste Einheit komponiert das
Dokument mit der nativen Includes-/Zyklenprüfung. Danach folgt je eine Einheit
für jeden Inhaltsblock des gespeicherten Bestands. Erst die bestätigte
Komposition entscheidet über seine Auswahl. Nicht ausgewählte Blöcke werden
ausdrücklich als nicht ausgewählt quittiert, ohne ihre Payload auszuführen.
Query-/Tabellen-, Referenz- und Prose-/Admonition-Blöcke verwenden die bestehenden
nativen Datenfunktionen. Include- und Seitenumbruchblöcke behalten ihre passiven
Originaldaten; wiederholte Includes bleiben als getrennte Vorkommen erhalten.
Gemeinsam verwendete Blockdaten werden nur einmal berechnet.

Jedes Fenster bestätigt einen echten Präfix der festen Aufgabenliste in der
generischen Work-Engine. Ein bereits überschrittenes weiches Zeitbudget
versucht trotzdem eine Einheit. Bestätigte native Berechnungen werden in
späteren Prozessen nicht wiederholt. Bei einem Fehler bleibt der letzte
veröffentlichte Checkpoint erhalten; noch nicht veröffentlichte Einheiten des
aktuellen Fensters gelten nicht als bestätigt. Es gibt keinen automatischen
Retry, keine automatische Bereinigung und keine leeren Fortschrittsgenerationen.

`finalize_document_work(store, registry=registry)` ist eine separate dauerhafte
Abschlussstufe. Solange eine deklarierte Einheit fehlt, gibt es kein fertiges
Ergebnis. Die Projektion enthält die komplette native Komposition und alle
ausgewählten Blockdaten. Eine explizite Query-Seite behält ihren Filter,
Offset, Limit, Total und `truncated`-Wert; die Work-Fortsetzung erweitert diese
fachliche Auswahl nicht stillschweigend. Alle Zeilen der ausgewählten Seite
müssen vorhanden sein. Das Ergebnis ist weder Rendering noch Modellfreigabe
oder Schreibberechtigung.

`specroad.documents.work_result.publish_document_result_files(store,
registry=registry)` liefert die vollständige abgeschlossene Projektion über
den bestehenden Work-Ergebnisdateivertrag. Die kanonischen Ergebnisbytes werden
atomar veröffentlicht, danach das Manifest mit Größe, SHA-256 und Schema.
Jeder Zugriff auf `delivery.as_dict()` prüft Checkpoint und Ausgabebytes erneut.
Vorhandene identische Dateien werden ohne Schreibzugriff wiederverwendet.
Projektbytes, `.specroad/` und der abgeschlossene Work-Checkpoint bleiben gleich.

Der W-Schritt ist ein Teilnachweis für SR-REQ-0605 und SR-REQ-0623. Komposition,
einzelne native Blockberechnungen, Snapshot-Rekonstruktion und Ergebnisreduktion
arbeiten weiterhin mit vollständigen Werten im Speicher. Die Fenstergrenze
unterbricht keine laufende native Berechnung. Feinere Include-, Query- und
Zeilen-Cursor, begrenzter Gesamtspeicher, automatische CLI-Weiterleitung und
automatische Wahl zwischen Inline-/Dateiausgabe werden hier nicht zugesagt.
Die unabhängige Anfangsbindung und ein kompatibler aufgezeichneter Build sind
für Prozesswechsel erforderlich. Modul-/PYZ-Prozesse können mit verlagertem
Work-Root aus den gesicherten Bytes weiterarbeiten, auch wenn die ursprünglichen
Projektdateien nicht mehr vorliegen.

Der W-Nachweis umfasst 29 neue Dokument-Verhaltenstests. Der abschließende
gezielte Lauf über `test_document_work.py`, die drei Schema-Katalogdateien und
`test_verification.py` besteht mit 138 Fällen auf vier parallelen Workern.
Weitere 1.013 unveränderte Regressionen bestanden zuvor bei bytegleichen
Produktquellen; anschließend wurden der neue Schema-Name in der Erwartungsliste
des Katalogtests und die kanonische Reihenfolge des noch unveröffentlichten
Nummerierungsanhangs vervollständigt. Alle alten Testnummern bleiben gleich. Die getrennten
Nachweise umfassen damit 1.151 unterschiedliche Testidentitäten. Die vollständige
Collection-/Katalogprüfung erfasst 12.887 Tests und führt keine Testkörper aus.
Dies ist ein Teiltestnachweis, kein Vollsuite- oder Release-Erfolg.
