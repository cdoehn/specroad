# Audit und Abschlussreceipts (5.n)

`finalize_committing_journal(preflight, journal, held_lock=..., authority=...)`
beendet C.2 für einen vollständig veröffentlichten `committing`-Bestand. Der
weiterhin gehaltene native Writer-Lock, der unabhängige Auftrag, der komplette
aktuelle Zielbestand, gebundene Ressourcen, Images, Fachprüfer und Hostautorisierung
werden erneut geprüft. Die Funktion schreibt ausschließlich Betriebsdaten;
sie veröffentlicht keine normative Zieldatei nochmals.

Der Transaktionsbeleg liegt unter `.specroad/transactions/receipts/` in einem
SHA-256-benannten Verzeichnis der exakten Transaktions-ID. Er bindet den vollständigen
Veröffentlichungsjournalstand, Plan-/Quell-/Zielhashes, Akteur, Operationsfolge,
erzeugte IDs und das Ergebnisobjekt. Bei vorhandener Request-ID entsteht zusätzlich
ein verknüpfter Beleg unter `.specroad/requests/<sha256-der-ID>.json`. Groß- und
Kleinschreibung bleiben unterscheidbar. Human/Tool ohne Request-ID erhalten keinen
künstlichen Requestbeleg. Der normale Transaktionsbeleg bleibt Pflicht.

Belege werden exklusiv geschrieben, vollständig synchronisiert und zurückgelesen.
Erst danach ersetzt ein synchronisierter Nachfolger das Journal durch `committed`
und bindet die exakten Receiptbytes. Fehler lassen entstandene Belege/Arbeitsdateien
stehen. Ein verlorenes Rename-Ergebnis kann einen bereits committed Stand bedeuten;
der Fehler meldet `committed_possible`, nicht einen sicheren Rollback. Bestehende
Belege werden weder überschrieben noch durch pauschale Wiederholung umgangen.

Die Parser für `TransactionReceipt`, `RequestReceipt` und `CommittedJournal`
prüfen Datenverträge. Ein selbstkonsistenter Hash ist keine Authentifizierung,
kein Beweis gegen absichtliche Dateimanipulation und keine aktuelle Schreibberechtigung.
`TransactionCompletion` trennt belegten Abschluss von noch offenen Arbeitsresten.
Die vorhandene allgemeine Read-only-Blockade aktiver Transaktionsverzeichnisse bleibt
bis zu deren expliziter Bereinigung konservativ bestehen.

Noch kein CLI-Befehl, kein vollständig integrierter ChangeBackend, kein Request-Retry-
Dispatcher und kein Rollback-Recovery. Der folgende Schritt 5.o behandelt die
normative Request-Idempotenz. Ein hier gespeicherter Requestbeleg allein autorisiert
keine Wiederholung oder Änderung. Der alte operative Bestand wird niemals aus einem
Receipt ungeprüft auf heutige Modellwerte umgeschrieben. Abgebrochene und abgewiesene
normative Befehle benötigen weiterhin die Auditprojektion ihrer späteren CLI-Anbindung;
die Anforderungsnachweise bleiben deshalb partiell.

Linux/local/native/fsync ist die bestehende Plattformgrenze. Dies ist weder eine
Mehrdatei-Atomizität noch eine stärkere Stromausfallgarantie als die darunterliegenden
Dateisysteme. Die Python-Synchronisations-/Dateiprimitiven sind beschrieben unter
https://docs.python.org/3.10/library/os.html (fsync/open/replace).

Für die Testausführung gilt die lokale `AGENTS.md`; die technische Anleitung
steht in [Testing.md](Testing.md). Die Receipt- und Fehlergrenzentests bleiben
fachliche Nachweise innerhalb der Testsuite.

## Abschluss rekonstruieren und Arbeitsreste entsorgen

`read_transaction_completion(ProjectSource(...), transaction_id)` ist rein lesend.
Er verlangt ein committed-Journal oder dessen archivierte byteidentische Fassung
und alle durch exakte Bytehashes gebundenen Receipts. Receipts allein, eine
Konsolenmeldung oder ein noch `committing`-Journal genügen nicht. Mit dem ursprünglichen
`PublicationPreflight` werden darüber hinaus der komplette Auftrag und die heutigen
Ziel-/Ressourcenbytes erneut geprüft. Ohne ihn wird nur historische lokale
Belegkonsistenz bestätigt, ausdrücklich nicht heutige Modellgültigkeit oder Echtheit.
Ein verlorener Rückgabewert nach dem Journal-Rename kann so ohne zweiten Fachwrite
aufgeklärt werden. Die Rootidentität verhindert die Verwendung einer anderen Kopie.

`cleanup_completed_transaction` ist ein gesonderter, ausdrücklich autorisierter
Aufruf unter demselben Writer-Lock. Vor der ersten Entfernung synchronisiert er
zusätzlich eine unveränderliche Fassung des committed-Journals unter
`transactions/receipts/<transaktionshash>/committed.json`. Transaktionsbeleg,
Requestbeleg und dieser Abschlussmarker bleiben erhalten; nur geprüfte Before
Images, leere Stagingverzeichnisse und das aktive Arbeitsjournal werden entfernt.
Unbekannte Dateien, fremde Journale, veränderte Images/Receipts oder verlorene
Bindungen verhindern ein vermeintlich erfolgreiches Aufräumen. Es wird niemals
rekursiv ein ungeprüftes Verzeichnis gelöscht.

Ein spätes Cleanupversagen kann `commit_completed=true` und zugleich
`cleanup_completed=false` liefern, jedoch nur solange die ursprünglichen
Abschlussbelege weiterhin überprüfbar sind. Ein beschädigter Beleg verbietet auch
diese Erfolgsaussage. Bereits entstandene Reste bleiben bestehen; lediglich die
kontrollierte Bereinigung darf erneut aufgerufen werden. Das ist kein Request-Retry-
Dispatcher und keine automatische Wiederholung des normativen Änderungsplans.
Fehlende Arbeitspfade nach einem früheren Cleanupversuch sind nur mit unverändertem
archiviertem Abschlussmarker zulässig. Lock-Eigentümerreste nach einem Prozesscrash
werden von diesem Reader nicht entfernt oder als geklärt ausgegeben.

Die R-Regressionsprüfungen decken alle zehn Synchronisationsgrenzen des regulären
Ein-Datei-Abschlusses und alle sieben Synchronisationsgrenzen seiner Bereinigung
ab, daneben echte Prozessabbrüche, verlorene Rückmeldungen, Teilwrites und
unveränderte normative Dateibytes. Diese Fehler-Injektionen sind keine Simulation
eines vollständigen Datenträger-Stromausfalls.
