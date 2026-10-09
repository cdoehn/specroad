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
