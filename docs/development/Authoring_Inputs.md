# Strukturierte Authoring-Eingaben

`specroad.authoring.inputs` bereitet die Fachwerte einer Artefakterzeugung vor.
Der gemeinsame Datentyp `ArtifactCreateInput` enthält kanonische JSON-Bytes,
SHA-256 und unabhängig zurückgegebene Fachwerte. Das Format `1.0.0` bindet
`command_id: artifact.create`, den gewählten Artefakttyp und `fields`.
Quellpfad, JSON-Einrückung und Eingabekanal gehören nicht zur Fachidentität.

Die drei ausführbaren Adapter sind:

- `normalize_artifact_create_input(kind, fields)` für bereits gelesene JSON-Werte.
- `read_artifact_create_input(kind, options=..., input=..., cwd=..., stdin=...)`
  für Feldoptionen sowie eine ausdrücklich gewählte Datei oder `input='-'`.
- `parse_artifact_create_input(argv, ...)` für den Befehlssuffix
  `TYPE [Feldoptionen] [--input FILE|-]` über den bestehenden Optionsbinder.

Eine Eingabedatei enthält ein flaches Objekt mit den Fachfeldern, zum Beispiel
`{"title":"Ziel","statement":"Offline arbeiten.","owner":"engineering"}`.
Der Typ stammt aus dem Aufruf. Die entsprechende Tokenliste ist
`['goal', '--title', 'Ziel', '--statement', 'Offline arbeiten.', '--owner',
'"engineering"']`. Feldnamen verwenden in Optionen Bindestriche statt
Unterstrichen. Reine Text-/String-Enumfelder nehmen Text entgegen; Zahlen,
Objekte, Arrays und unionswertige Felder wie `owner` verwenden genau einen JSON-Wert.
Die JSON-Anführungszeichen im Owner-Beispiel sind deshalb Bestandteil des Wertes.
Zusätzliche Objektmitglieder lassen sich nicht über diesen Optionswert
einschleusen; ungültige Werte werden vor dem Lesen von Datei oder stdin abgewiesen.

Datei und Optionen dürfen sich ergänzen. Derselbe kanonische Feldwert ist
redundant zulässig; widersprüchliche Angaben führen zu Code 2. Fehlende Felder
und ungültige JSON-/Schemawerte führen zu Code 3. Pfadverweigerungen behalten
Code 7, tatsächliche I/O-Fehler Code 5. Ohne den exakten Marker `-` wird stdin
nicht gelesen; eine Datei mit diesem Namen bleibt über `./-` auswählbar.
Ein übergebener binärer Stream wird nicht geschlossen. Datei-Reads verwenden
den vorhandenen deskriptorgebundenen Leser und prüfen den beobachteten Zustand.
Eine fehlende binäre stdin-Schnittstelle oder ein geschlossener Stream führt zu
Code 5. Bereits begonnene Reads werden bei Fehlern nicht wiederholt. Ein Reader,
der Text statt Bytes oder mehr Bytes als angefordert liefert, verletzt die
Lesegrenze und führt zu Code 7. Austausch, Wachstum und Schrumpfen der Datei
werden abgewiesen; der fremde Endzustand bleibt erhalten. Benannte Pipes werden
vor einem möglicherweise blockierenden Öffnen abgelehnt.

Die Feldschemas stammen aus den vorhandenen Domain-/Recordverträgen der
24 regulären Drafttypen. Evidence, Baseline, Proposal und Relationsreview
verlangen ihre spezialisierten Dienste. Identität, Auditfelder, Reifegrad und
Schema-/Typfelder dürfen nicht als freie Fachwerte eingeschleust werden.
Nur fehlende `relations` und `extensions` erhalten leere Container; deklarierte
Sprachtags werden durch den nativen Parser kanonisiert. Prosa und normative
Force werden weder übersetzt noch aus Text oder Priorität abgeleitet.

Der W/R/C-Stand ist eine gemeinsame Eingabeschicht für den folgenden Writer, kein
neu registrierter `artifact create`-Befehl und kein vollständiger Change Plan.
Er verwendet keine Entropie, Zeitstempel, Projektwrites oder externe Programme.
Feldschema-Erfolg bestätigt weder Graph-/Profil-/Lifecyclegates noch lokale
Zusatzprüfungen einer vollständigen gespeicherten Instanz. ID-Vergabe,
vollständige Modellvalidierung und atomarer Writer werden in 7.c angebunden.
Der native Einbettungsdienst aus 7.c.W ist in `Artifact_Creation.md` beschrieben;
er verlangt explizit gebundene Modelle, ID-Inventare und Schreibberechtigung.
Die weiteren Authoring-Dienste verwenden anschließend dieselbe Eingabegrenze.
Die tatsächliche CLI-Integration samt versioniertem stdout-Ergebnis bleibt offen.

Rohbytes und normalisierte Werte sind derzeit speicherresident; der Reader
verwendet begrenzte Readblöcke, aber keine behauptete Gesamt-Speicherobergrenze.
Pflichtfeld-/Typfehler, widersprüchliche Quellen und Störfälle der Eingabekanäle
haben in 7.b.R zusätzliche Verhaltensnachweise erhalten. SR-REQ-0240 bleibt
wegen der noch ausstehenden Writer- und CLI-Integration partiell.

Intern bündelt `_input_fields.py` die nativen Draftfeldschemas,
Optionsdefinitionen und Konvertierung der Feldoptionswerte. Der öffentliche
Adapter in `inputs.py` führt diese Vorbereitung vor dem Lesen und Zusammenführen
aus; seine Schnittstellen und die beschriebenen Fehlerverträge bleiben erhalten.
