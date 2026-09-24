# Strukturierte Diagnosen und Fail-Policy (4.p)

Die gemeinsame Bibliothek `specroad.diagnostics` liefert dasselbe `Diagnostic`-
Wertobjekt wie der bisherige Import `specroad.cli.results.Diagnostic`. Sie führt
keine Regel aus und bestätigt keine Herkunftsauthentizität. `origin` bezeichnet
nur eine der sieben deklarierten Ursprungsklassen; der frühere interne Default
`core` lautet jetzt spezifikationskonform `core_rule`.

Alle 13 Felder aus SR-REQ-0089 bleiben in der strukturierten Darstellung vorhanden.
Nicht beobachtete Fundstellen sind null. Ein JSON Pointer kann den Root mit `""`
bezeichnen; null bedeutet dagegen nicht ermittelt. Zeilen und Spalten sind
1-basiert, Byte- und Unicode-Codepoint-Offsets 0-basiert. Der Projekt-JSON-Reader
liefert seine Positionsdaten unverändert. Zusätzliche Bytepositionen werden nur
bei ausdrücklich übergebenen, gebundenen Originalbytes berechnet. Parser ohne
Positionsbeobachtung (zum Beispiel Doppelschlüssel nach der Syntaxphase) erhalten
keine durch Textsuche erratenen Fundstellen.

`diagnostic_key` ordnet error, warning, info, Dateilabel, Artefakt-ID, JSON Pointer
und Code; verbleibende Gleichstände werden durch die vollständigen Daten
aufgelöst. Kein Locale, keine automatische Pfad-/Unicode-Normalisierung und keine
Anzeigegrenze verändern Mengen oder Identitäten. Identische Diagnosevorkommen
bleiben mehrfach enthalten. related_ids sind dagegen eine eindeutige Referenzmenge.

`assess_diagnostics` verlangt beobachtete Befunde und die ausdrücklich geprüften
Artefakt-IDs. `fail_on=error|warning` und `strict=True` bewerten nur die Schwelle;
Warnungen werden nicht in Fehler umgeschrieben. Strukturelle geschützte Codes
verwenden dieselbe Untergrenze wie die Profilkomposition. Ein unabhängiger
Fehlercode 2–7 bleibt erhalten. Unvollständige Prüfungen erzeugen keinen Erfolg
und keinen Code 8 ohne tatsächlichen Checkpoint. `strict` startet hier keine
optionalen Lintprüfungen oder Analyzer; diese müssen später explizit angebunden
werden. Ein erfolgreicher Befund ist keine Freigabe oder Schreibberechtigung.

`assess_validation` verarbeitet ein echtes `ValidationReport`. Die ursprünglichen
Stufen und alle herstellerspezifischen Zusatzfelder bleiben im `source_report`
erhalten. Optionale Originalquellen müssen genau zur Source-Hashliste passen.
`validation_command_result` bildet dies in den bestehenden CLI-Envelope ab,
registriert aber keinen neuen `validate`-Befehl. Quellen sind bereits geladene
Bytes, keine durch Diagnosedaten aufgelösten Dateien oder URLs.

Unbekannte nichtleere Diagnose- und Regelkennungen bleiben unverändert erhalten.
Der additive Katalog spiegelt die stabilen SRV-Bedeutungen aus Kapitel 13 wider,
behauptet aber keine Ausführung sämtlicher dort genannten Prüfungen. Die
zusätzlichen stabilen Codes `MODEL_VALIDATION` (nicht feiner klassifizierter
Pipelinebefund) und `VALIDATION_UNAVAILABLE` (fehlender erforderlicher Prüfer)
werden nicht willkürlich einem fachlichen SRV-Code gleichgesetzt.

Lokale Abnahme: nur neue oder unmittelbar durch den gemeinsamen Diagnosevertrag
betroffene Tests, vier Worker. Vollsuite ausschließlich in CI, parallel und in
jedem fünften Bundle zusätzlich seriell mit Nachweisvergleich. Keine Tests auf
Meldungstexte, Farben, Layout oder dieses Dokument. Die gesamte Produktmatrix und
der lokale Ziel-Apply benötigen weiterhin tatsächliche neue Ausführungsnachweise.

## R: vollständige Beobachtungen, keine erfundenen Fundstellen

Mehrere unbekannte explizite Selektions-IDs werden einzeln erhalten. Sie erhöhen
nicht die Anzahl tatsächlich identifizierter geprüfter Artefakte. Sämtliche von
unabhängigen Pipelinephasen gelieferten Befunde bleiben enthalten, auch identische
Vorkommen. Nach einem strukturellen Fehler blockierte Phasen bleiben als solche
sichtbar: Die Diagnoseprojektion kann keine noch nicht ausgeführten Prüfungen
nachholen und behauptet nicht, alle möglichen Fehler des defekten Modells gefunden
zu haben. Unerwartete Fachprüfer-Ausnahmen bleiben Klasse 4 statt policy class 1.

Die zusätzliche Ordnung nach numerischen Koordinaten, Ursprung, Regel-ID und
vollständigen Daten dient nur der deterministischen Auflösung von Gleichständen
nach den spezifizierten Primärschlüsseln. Der API-Transport kann unbekannte Codes
und Referenz-IDs aufnehmen, ohne sie zu verwerfen, aufzulösen oder als bekannte
Prüfregeln auszugeben. Unbeobachtete Pointer bleiben null statt fiktivem Root.
Beim Ergänzen von Byteoffsets müssen bekannte Zeile/Spalte mit den gebundenen
Originalbytes übereinstimmen. Keine Anzeigegrenze kürzt die Diagnosemenge.

Nach C sind die unveränderlichen Diagnosewerte (`values`), die semantische Ordnung
(`ordering`), Parserprojektion (`projection`), Fail-Auswertung (`policy`) und das
Schema (`schema`) getrennt. Die bisherigen öffentlichen Imports bleiben gleich.
Der Envelope-Adapter liegt separat in `validation.result_adapter`; er registriert
keinen Befehl und startet keine zusätzliche Validierung.
