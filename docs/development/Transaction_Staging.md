# Staging, Before Images und Prepared (5.l)

`stage_building_journal(preflight, journal, held_lock=..., authority=...)`
übernimmt genau das vorhandene, unabhängig an den geprüften Auftrag gebundene
Building-Journal unter seinem weiterhin gehaltenen nativen Writer-Lock. Es
verwendet die vollständigen Vorher- und Nachherbytes des vorhandenen
PublicationPreflight. Vorhandene Stagingreste werden weder wiederverwendet noch
aufgeräumt. Ein Vorgang wird nicht automatisch wiederholt.

Die bisherigen normalen Lock- und Veröffentlichungsgrenzen bleiben unverändert:
Dort blockiert jedes aktive Journal. Ausschließlich dieser Stagingpfad akzeptiert
exakt sein vollständig geprüftes eigenes Journal; weitere Recovery-/Journalnamen
blockieren ihn. Modell, Auftrag, Lockeigentümer und Dateibindung müssen passen.
Vor Aufbau und vor dem Prepared-Übergang werden Zielprüfung und Autorisierung
wiederholt. Änderungen während der Prüfer werden anschließend erneut erkannt.

Before Images und neue Zielbytes werden als getrennte private reguläre Dateien
unter `before/` und `staging/` angelegt. Neue normative Dateien haben ausdrücklich
kein Before Image. Es werden keine Ziele veröffentlicht, keine zusätzlichen
Revisionen erzeugt und keine fehlenden normativen Zielverzeichnisse angelegt.
Kurze Writes werden vervollständigt. Sämtliche Bytes, Größen, Hashes und
Dateiidentitäten werden kontrolliert. Jede vollständige Datei und ihr Verzeichnis
werden synchronisiert. Eine ursprünglich leere Änderungsmenge bleibt leer.

Der vollständige Zielbestand wird aus den tatsächlichen zurückgelesenen
Stagingbytes und den gebundenen unveränderten Quelldateien materialisiert.
Dateimenge und Bytedigests müssen dem geprüften Auftrag entsprechen. Die
vorhandene Modellmanifestfunktion berechnet daraus die Zielmodellwurzel erneut;
die vollständige bestehende Modellvalidierung und registrierte Fachprüfer
prüfen diese konkreten Dokumente, auch die unveränderten. Bei einem leeren Ziel
laufen ausdrücklich erforderliche Command-Gates trotzdem. Die nachfolgende
Frischeprüfung kontrolliert außerdem Änderungen während dieser Fachprüfer.

Erst wenn alle Images vollständig vorliegen und mit dem Change Plan
übereinstimmen, wird ein privater Prepared-Journalnachfolger geschrieben,
synchronisiert und atomar über das weiterhin identische Building-Journal
umbenannt. Danach wird das Journalverzeichnis synchronisiert und alles erneut
geprüft. `published_count=0` und alle Eintragsflags bleiben false. Das sind native
lokale Linux-Dateisystemgrenzen; keine stärkere Garantie als das Dateisystem und
der Datenträger tatsächlich liefern. Ein nichtkooperierender Schreiber wird
nicht durch eine Betriebssystem-Sandbox ausgeschlossen.

Fehler erhalten alle bis dahin entstandenen Betriebsdateien. Vor dem Austausch
bleibt building stehen, nach einem möglicherweise erfolgten Austausch kann
prepared vorhanden sein. `StagingError.prepared_possible` unterscheidet diese
Grenze. Kein Fehler behauptet erfolgreiche Veröffentlichung oder automatischen
Rollback. Aktive Betriebsdaten bleiben Recoveryblocker; der spätere
Recovery-Schritt entscheidet über Verwerfen oder Fortsetzen.

`PreparedJournal` ist nur ein strikter unveränderlicher Datenwert. Sein Parser
beweist keine vorhandenen Dateien, Dauerhaftigkeit oder Schreibberechtigung.
`verify_prepared_journal` rechnet die vollständige Inventur gegen den
unabhängigen Preflight nach. `read_prepared_journal` liest zusätzlich sämtliche
Images, prüft ihre vollständigen Hashes und die exakte Dateimenge, ohne Writes,
Lockanlage oder Reparatur. Dies ist eine frische Lesebeobachtung, kein atomarer
Mehrdatei-Snapshot. Für spätere Veröffentlichung ist eine erneute Prüfung nötig.

Noch kein committing, normatives Publishing, Receipt, vollständiger nativer
ChangeBackend oder CLI-Schalter. Diese Stufe unterstützt die bereits vom
PublicationRequest abgedeckten geänderten Artefaktdateien; Anhangs-/Spezialwrites
werden nicht durch erfundene Inventoryeinträge vorgetäuscht.

Für die Testausführung gilt die lokale `AGENTS.md`; die technische Anleitung
steht in [Testing.md](Testing.md). Der Doppelmodus für Bundle 035 ist eine
historische, abgelöste Ausführungsregel. Dieser Abschnitt führt keine neuen
Abhängigkeiten ein; die CI-Beobachtung liegt weiterhin unter tools/.

Die C-Bereinigung kapselt die unveränderten nativen Lese-/Schreib-,
Hash- und Namensmengenprimitiven in `changes/_staging_files.py`.
Die Anwendungsfolge und alle W-/R-Verhaltenstests bleiben unverändert.
