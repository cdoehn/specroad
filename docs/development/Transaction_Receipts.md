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

Lokal nur neue und direkt betroffene Tests parallel mit vier Workern. GitHub führt
am Bundle-Ende die Vollsuite aus, jedes fünfte Bundle zusätzlich seriell mit Vergleich.
Keine Tests auf Meldungstexte, Farben, Dokumentation oder Layout; keine neuen Timeouts.
