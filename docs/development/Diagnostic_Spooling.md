# Externe Diagnose-Sortierung

`specroad.diagnostics.spooling.create_diagnostic_spool` ist ein ausdrücklich
aufgerufener Bibliothekspfad. Der Aufrufer übergibt einen einmal konsumierten
Iterator geprüfter `Diagnostic`-Werte, einen noch nicht vorhandenen absoluten
Spool-Pfad und ein nicht leeres Tupel von `ProjectBoundary`-Objekten für sämtliche
geschützten Projekt-, Eingabe- und Ausgabe-Roots. Quellbindung und Auswahl aller
geschützten Grenzen liegen beim vertrauenswürdigen aufrufenden Adapter.

```python
with create_diagnostic_spool(external_path, diagnostics,
                             protected_roots=(project_boundary,),
                             batch_bytes=65536) as spool:
    with spool.cursor() as cursor:
        while not cursor.state["complete"]:
            page = cursor.read_page(100)
            # Die Anwendung übernimmt sämtliche Einträge dieser Seite.
```

`batch_bytes` ist ein positives weiches Ziel für die kodierten Eingaberecords
einer Sortiercharge. Ein einzelner größerer Befund wird allein verarbeitet.
Die Größe begrenzt weder die Anzahl der Befunde noch deren Inhalte. Sie ist keine
Gesamt-RSS- oder Hostquotenzusage: Pythonwerte, Sortierschlüssel, ein gerade
eingelesener nächster Befund, die beiden Mergeköpfe und I/O-Puffer benötigen
zusätzlich Speicher. Eine Ausgabeseite benötigt Speicher für ihre ausdrücklich
angeforderte Zahl von Befunden.

Jeder Befund erhält genau einmal seine Eingabeposition. Chargen werden nach dem
bestehenden `diagnostic_key` und dieser Position stabil sortiert. Ein Paarmerge
vereinigt immer zwei bereits sortierte Läufe; die logarithmisch große Liste
offener Laufreferenzen vermeidet das Sammeln aller Befunde oder aller Laufköpfe
im Speicher. Pflichtbefunde und identische Duplikate bleiben erhalten. Es gibt
keine stillschweigende Deduplikation oder Ausgabeabschneidung. Der Hash der
vollständigen sortierten Recordbytes bleibt bei anderer Chargengröße gleich.

Die Läufe sind JSONL mit `sequence` und der unveränderten Diagnoseprojektion.
Sie verwenden dieselbe ASCII-JSON-Zahl-/Stringdarstellung wie der bestehende
Diagnoseschlüssel; insbesondere bleibt die bestehende Ganzzahlsemantik der
Ortskoordinaten erhalten. Die interne Referenz bindet Dateiname, Bytezahl,
SHA-256, Recordzahl und maximale Recordlänge. Vor jedem Parserzugriff wird der
vollständige Lauf blockweise gehasht. Die Prüfung von Descriptor, Pfadidentität
und Inhaltssignatur begrenzt die Leseoperation; Seiten werden erst nach ihrer
Abschlussprüfung zurückgegeben. Die API importiert keine fremden Referenzen.

Das kleine `spool.json` beschreibt nach vollständiger Sortierung das Eingabehash,
den Endlauf und beobachtete Chargengrößen. Es enthält keine absoluten Pfade.
Die Datei wird exklusiv erzeugt, synchronisiert und zurückgelesen. Eine
fehlgeschlagene Konstruktion liefert keine Spool-Capability. Es gibt noch keinen
Leser, der eine liegengebliebene Manifestdatei als gültigen Checkpoint übernimmt.
`manifest` gibt eine abgelöste Kopie zurück; Änderungen daran schaffen keine
Datei- oder Schreibberechtigung.

Der Cursor bezeichnet mit Manifesthash, `record_index` und `byte_offset` die
nächste Ausgabeposition. Jeder nicht leere erfolgreiche Seitenaufruf bewegt ihn
vorwärts. `complete` gilt erst nach genau allen Records und bestätigtem EOF;
ein Präfix erhält keinen Abschlussstatus. Ungültige Seitengrößen werden vor
einer Cursorbewegung abgewiesen. Ein Lese- oder Integritätsfehler invalidiert
den Cursor, ohne die betroffene Seite auszuliefern. Bereits vorher gelieferte
Seiten werden dadurch nicht rückwirkend zu einer vollständigen Ausgabe.

Die POSIX-Implementierung öffnet alle Pfadkomponenten descriptorbezogen ohne
Symlink-Folgen. Der Spool darf keine geschützte Root überlappen. Er entsteht
exklusiv mit 0700, Dateien mit 0600; vorhandene Verzeichnisse, Dateien oder
Verknüpfungen werden nicht wiederverwendet. Dateihardlinks und nachträglich
verbreiterte Rechte werden abgewiesen. Unterstützt eine Plattform diese
Schutzoperationen nicht, wird die Konstruktion abgewiesen. Native I/O- und
Allokationsfehler werden weitergegeben; die API erhöht keine Ressourcenlimits.
Schließen gibt nur Descriptoren frei. Fertige und unvollständige eigene Dateien
bleiben bei Fehlern erhalten; es gibt keine automatische Löschung oder Retry.

Der W-Stand 6.f.W liefert einen konkreten Cursor innerhalb des laufenden
Prozesses. `durable_checkpoint` ist ausdrücklich `false`. Er implementiert
noch keine pausierbaren Mergecursor, Work-Locks, atomaren Checkpointgenerationen,
portable Wiederaufnahme, automatische Work-Root-Wahl oder Einbindung sämtlicher
Fachbefehle. Alle Zwischenläufe bleiben erhalten; die zusätzliche Plattenbelegung
kann mit der Anzahl der Mergeebenen wachsen. Der dokumentierte Teilnachweis für
SR-REQ-0605 ersetzt weder die vollständige P.5-Abnahme noch den weiterhin offenen
Graphtraversierungs-/Pfadausgabevertrag SR-REQ-0585. 6.f.R erweitert denselben
Ausschnitt um die noch offene Fortsetzung und Robustheit.

## Live-Fortsetzung ab 6.f.R

`DiagnosticSort` zerlegt denselben Algorithmus in aufrufbare Einheiten.
`advance(units)` nimmt ein positives Arbeitsfenster entgegen; selbst `1` führt
einen realen nächsten Schritt aus. Ein Schritt bestätigt einen angenommenen
Eingaberecord, einen vollständig geschriebenen Record, einen synchronisierten
und zurückgeprüften Lauf oder den abschließenden Übergang zum fertigen Spool.
Dateiöffnung, eine kleine Chargensortierung und die vollständige blockweise
Integritätsprüfung eines benötigten Laufs bleiben Vorbedingungen solcher
Einheiten. Das Fenster ist keine präemptive CPU-/Wall-Clock-Garantie.

```python
with DiagnosticSort(external_path, diagnostics,
                    protected_roots=(project_boundary,), batch_bytes=4096) as task:
    while not task.state["complete"]:
        progress = task.advance(1)
        # Der Aufrufer kann hier pausieren und dasselbe Objekt später fortsetzen.
    with task.result.cursor() as cursor:
        while not cursor.state["complete"]:
            page = cursor.read_page(10)
```

`state` ist eine abgelöste JSON-Projektion: Phase, bestätigte Einheiten,
angenommene und gepufferte Eingaben, eine gegebenenfalls bereits gelesene nächste
Eingabeposition und die logarithmisch vielen offenen Laufreferenzen. Während
eines Merges bezeichnet sie beide vollständigen Inputreferenzen mit nächster
Record-/Byteposition sowie Namen, geschriebene Bytes/Records und Versiegelungs-
status des Outputs. Die Summen der beiden konsumierten Eingabepräfixe stimmen
mit dem geschriebenen Output überein. Die zwei gegebenenfalls vorgelesenen
Mergeköpfe und der Quelliterator verbleiben im lebenden Prozess. Sie werden
bei Fortsetzung nicht erneut aus einer früheren Eingabecharge aufgebaut.

Nur eine vollständige Sortierung gibt über `result` eine Spool-Capability frei.
Ein fehlgeschlagener Schritt erhöht die Zahl bestätigter Einheiten nicht; der
Task wird geschlossen und kann nicht automatisch erneut versuchen. Schließen
eines unvollständigen Tasks beendet seine offenen Generatoren und Descriptoren
und behält sämtliche eigenen Dateien. Der Aufrufer bleibt für den Lebenszyklus
seines gelieferten Quelliterators verantwortlich. Schließen eines fertigen Tasks
schließt auch seinen Spool und dessen Liefercursor. Der synchrone Adapter
`create_diagnostic_spool` verwendet denselben Treiber und übergibt den fertigen
Spool an seinen Aufrufer.

`specroad.graph.path_output` ergänzt `PathRecord`, `PathSort` und
`create_path_spool` für bereits berechnete vollständige Pfadaufträge. Die
Recordprojektion erhält alle Artefakt-/Relationsidentitäten, Identitätsschemata
und Inversrichtungen. `PathRecord.from_views` prüft einen zusammenhängenden Walk
aus vorhandenen typisierten Relationsansichten. Der Spool erhält genau die
Reihenfolge und Duplikate seines Produzenten; ein kleines Arbeits-, Chargen-
oder Lieferfenster ist keine fachliche Pfadgrenze. Leere Kantenfolgen und
invertierte Ansichten behalten ihre eigene Bedeutung. Der gesamte Pfad muss
als einzelner Record in den tatsächlichen verfügbaren Speicher passen; ein
weiches Chargenziel allein verweigert ihn nicht.

Der Teilnachweis verwendet einen expliziten geschichteten Graphen mit 128
gleich kurzen Pfaden und liefert alle vorbereiteten Pfade auch mit Einrecord-
Fenstern. Er behauptet keine produktive Why-Suche: Auswahl gültiger Pfade,
Maximaltiefe, vollständige Frontier und Fachreihenfolge bleiben Verantwortung des
zukünftigen Graphproduzenten in 8.e/8.f. Dieser Schritt schließt nur den
Pfadtransport-Teil von SR-REQ-0585 und erweitert den Teilnachweis SR-REQ-0605.

Die Fortsetzung ist weiterhin an das lebende Taskobjekt gebunden. Eine
Stateprojektion lässt sich nicht importieren oder als Work-Checkpoint ausgeben;
`durable_checkpoint` bleibt `false`. Dauerhafte Work-Identität und Generationen
folgen in 6.i–6.l. Bereits vollständige Läufe bleiben bei einer Pause erhalten;
unversiegelte Ausgabedateien sind kein eigenständig anerkennbarer Checkpoint.
