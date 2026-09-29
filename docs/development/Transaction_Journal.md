# Building-Journal (5.k)

`prepare_building_journal` erzeugt eine reine, vollständige Dateiinventur aus dem
vorhandenen geprüften PublicationPreflight. Pro tatsächlich veränderter
Artefaktdatei stehen logischer Zielpfad, vorherige Existenz, Bytegröße und SHA-256
der Vorher-/Nachherbytes sowie transaktionslokale Staging-/Before-Image-Pfade
fest. Nicht vorhandene Vorherdaten bleiben null. Die Liste ist kanonisch
pfadgeordnet. Unveränderte Dateien und No-ops werden nicht als Writes erfunden.

Die neue interne Codecidentität ist `transaction-journal-v1`. Nur building wird
in dieser Schicht gelesen/erzeugt, mit published_count=0 und published=false pro
Datei. Andere bekannte Zustände sind noch keine ausführbaren Übergänge.
Plan- und Planbyteshash, Basis-/Zielmodellwurzel, vollständiger Requesthash,
Projekt-/Rootidentität, Akteur und Planzeit bleiben ausdrücklich gebunden.
Es werden keine neuen IDs und keine Uhrzeiten aus der Umgebung erzeugt.

`begin_building_journal` verlangt einen aktuell gehaltenen nativen Writer-Lock
und führt die bestehende endgültige Basis-, Ressourcen- und Autorisierungsprüfung
erneut aus. Danach legt es exklusiv .specroad/transactions/<ID>/journal.json an,
synchronisiert Datei und Elternverzeichnisse und liest die Daten zurück.
Staging und Before Images sind zunächst nur Pfadbindungen, keine bereits
geschriebenen Payloads. Die Funktion ruft keinen normativen Publisher auf.

Bei Fehlern bleiben angelegte operative Dateien/Verzeichnisse erhalten. Eine
partielle oder unlesbare Journaldatei wird nicht als Erfolg ausgegeben und nicht
automatisch gelöscht. Auch ein leer verbliebener Transaktionsordner blockiert
normalen Writer/Modellload; die spätere explizite Recovery entscheidet darüber.
Ein vorhandener Datensatz wird niemals allein wegen identischer ID oder eines
selbst behaupteten Abschlussstatus überschrieben.

`BuildingJournal` erhält Originalbytes und liefert unabhängige Datenobjekte.
`verify_building_journal` vergleicht die gesamte Inventur mit dem unabhängigen
Preflight, nicht nur mit einer im Journal selbst behaupteten Prüfsumme.
`read_building_journal` liest ausschließlich den benannten bestehenden Datensatz
unter der Projektbindung, ohne Lockanlage, Modellreparatur oder Cachewrites.
Ein gelesener Datensatz ist keine Autorisierung, kein Recoveryabschluss und
kein Beleg bereits veröffentlichter Fachdateien.

Die Umsetzung gilt für die derzeit unterstützten Artefakt-Kandidaten der
PublicationRequest-Schnittstelle. Ein nativer vollständiger ChangeBackend,
Anhangs-/Spezialworkflows, prepared/committing, Crash-Recovery und Receipts folgen
in ihren vorgesehenen Schritten. Die bestehende finale Veröffentlichungsprüfung
blockiert weiterhin alle aktiven Journale; eine spätere eigene Journal-Ausnahme
muss an den vollständigen Transaktionsvertrag gebunden werden. Kein bestehender
Sicherheitscheck wird hierfür gelockert. Der kooperative native Lock ist keine
Sandbox gegen fremde absichtlich unkooperative Schreiber.

Lokal: nur neue/direkt betroffene Tests mit vier Workern; Volltests in GitHub,
jede fünfte Bundle-Nummer zusätzlich seriell. Keine Darstellungstests, keine
künstlichen Testtimeouts. Keine neue Core- oder Entwicklungsabhängigkeit.

## Fehler- und Bindungsgrenzen

Der Leseweg kann zusätzlich den ursprünglichen Preflight verlangen und damit
die vollständige Inventur unabhängig nachrechnen. Eine selbstkonsistente
Prüfsumme auf einer falschen oder unvollständigen Liste genügt dann nicht.
Abweichende Rootinstanzen, fremde Transaktionspfade und nichtnormative Ziele
werden nicht als gleichwertig behandelt. Nicht unterstützte Zustände bleiben
explizit abgewiesen; die Codecprüfung startet niemals Recovery.

Die Dateiveröffentlichung des Journals verifiziert auch die Identität der
tatsächlich exklusiv erzeugten Datei. Eine anschließend mit identischen Bytes
ersetzte Datei ist nicht mehr derselbe Write. Während der Anlage beobachtete
zusätzliche Journal-/Recoveryeinträge oder Namespaceänderungen lassen den
Vorgang fehlschlagen und bleiben erhalten. Kurze Writes werden vervollständigt;
ein Null-Write oder eine verweigerte Synchronisierung wird kein Erfolg.
Die fsync-Aufrufe garantieren keine stärkere Dauerhaftigkeit, als Dateisystem
und Datenträger tatsächlich bereitstellen. Keine automatische Wiederholung,
kein Entfernen unvollständiger Dateien und keine Lockerung des Writer-Locks.
