# Dokumentprojektion über Work (11.r.W/R/C)

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

Dokumentprojektion und der bestehende Analyseadapter verwenden dieselbe private
`work._unit_window.UnitWindow` für die Ausführung eines Fensters. Sie bündelt
die Start-/Endgrenzen einer Einheit, kanonische Nachweisbytes, ausgeführte
Einheiten und den Budgetentscheid nach vollständiger Berechnung. Der gemeinsame
Checkpointaufruf erhält echte native Modellfehler und übersetzt ausschließlich
beschädigte Work-Verträge in den bisherigen Konflikt. Die Fachadapter behalten
ihre Plan-, Eingangs-, Präfix-, Ergebnis- und Buildprüfungen in derselben
Reihenfolge; der vorhandene `CheckpointStore` veröffentlicht den geprüften
Kandidaten. Die getrennten Abschlussfunktionen und alle gespeicherten Formate
bleiben erhalten. Der Helfer verwendet ausschließlich vom vertrauenswürdigen
Adapter übergebene Funktionen; gespeicherte Daten wählen keinen Handler.

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

Der R-Schritt prüft gespeicherte Kompositionen gegen die vollständigen gebundenen
Quellrelationen. Jedes erforderliche Kind und jedes wiederholte Include muss als
Vorkommen mit richtigem Elternbezug, Reihenfolge und Quellenhash vorhanden sein.
Ein korrigierter Zähler allein macht einen abgeschnittenen Präfix nicht vollständig.
Literaltabellen müssen alle ursprünglichen Zeilen und typisierten Werte enthalten.
Query-Seiten behalten die gebundene Auswahl, Eingangs-/Konfigurationshashes,
Pagination und sämtliche ausgewählten Zeilen samt originalen Feldwerten.
Unbekannte Datenfelder, widersprüchliche Bindungen und erweiterte Erfolgs- oder
Berechtigungsbehauptungen werden vor neuen Writes als Konflikt abgewiesen.

Diese Konsistenzprüfungen wiederholen weder die abgeschlossene Komposition noch
Filterauswertung oder Prose-Parsing. Das exakte Query-Total bleibt ein gespeichertes
Ergebnis des nativen Auswerters. Die Prüfung ist keine Authentifizierung fremder,
beliebig neu gehashter Work-Daten; die unabhängige Anfangsbindung und der geschützte
Work-Speicher bleiben erforderlich. Ergebnisdateifehler erhalten den Checkpoint
und tatsächlich entstandene vollständige oder teilweise Ausgabebytes. Erst ein
ausdrücklicher neuer Aufruf kann fehlende Ausgabe vervollständigen. Jeder gelieferte
Dateiverweis prüft beide Dateien erneut; es gibt keine stille Reparatur.

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

Der R-Nachweis besteht mit 184 gezielten Tests auf vier parallelen Workern:
131 neue R-Fälle, sämtliche 29 W-Fälle und 24 Verifikationskatalogfälle.
Die vollständige Katalogprüfung bindet 13.018 Testidentitäten bei null
ausgeführten Testkörpern. Alle bisherigen Testdateien und Testnummern bleiben
erhalten. Die R-Fälle prüfen auch neu gehashte unvollständige Nachweise,
1.000 Literalzeilen, 130 ausgewählte Query-/Viewzeilen und Fehler vor beziehungsweise
nach echter Dateiveröffentlichung. Dieser Nachweis bleibt ein Teiltestlauf.

Der C-Nachweis besteht mit 351 unveränderten Verhaltenstests auf vier parallelen
Workern: alle 160 Dokument-W-/R-Fälle, 79 Analyse-W-/R-Fälle sowie 112 Fälle
zu Checkpoints, Ergebnisdateien und Verifikationskatalog. Die vollständige
Collection-/Katalogprüfung erfasst unverändert 13.018 Testidentitäten ohne
Testkörperausführung. Alle bestehenden Testdateien und Nummern sind bytegleich
erhalten. Dieser Teiltestlauf ist kein Vollsuite- oder Release-Erfolgsnachweis.
