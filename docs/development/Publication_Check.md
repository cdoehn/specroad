# Prüfung unmittelbar vor Veröffentlichung (5.j)

`prepare_publication_check` übernimmt einen bereits gespeicherten Change Plan und
seinen vollständigen bereitgestellten `TargetModel`-Bestand. Diese ausdrücklich
angeforderte Prüfung gehört zur Vorbereitung einer konkreten Veröffentlichung,
nicht zum sparsamen automatischen Start-/Umgebungs-Preflight nach Anhang N.
Sie prüft das Ziel und liest die aktuellen Quelldateien. Sie erzeugt weder einen
Lock noch Journal, Cache, Receipt oder normative Änderungen. Ein erfolgreicher
Frühbefund ist keine spätere Schreibberechtigung.

`recheck_publication` verlangt denselben Auftrag, einen aktuell gehaltenen nativen
Writer-Lock, die passende Request- und Transaktions-ID sowie eine ausdrücklich
registrierte `PublicationAuthority`. Unter diesem Lock werden alle Quellbytes
neu gehasht, konfigurierte normative JSON-Dateimengen erneut ermittelt,
Ausgangsbasis und Zielprüfung erneut validiert und der Host erneut zur
Autorisierung gefragt. Danach werden Dateien, Pfade, Rechte, Lock und
Recoveryzustand nochmals geprüft. Kein Rebase, keine Ersatz-ID, kein Zugriff
auf einen anderen gleichnamigen Projektroot. Zeitstempel ersetzen keine Hashes.

`publish_after_recheck` ruft den vertrauenswürdigen Publisher unmittelbar nach
diesen Prüfungen auf. Es erstellt keinen eigenen Dateischreiber. Ein zukünftiger
nativer `ChangeBackend` kann diese Grenze in seinem `publish` verwenden; dessen
Receipt-/Readback-Prüfung bleibt weiterhin erforderlich. Bereits gehaltene Locks
werden weder übernommen noch freigegeben. Ungelöste Journale blockieren diese
Grundlagenschnittstelle, auch wenn sie vermeintlich zur aktuellen Transaktion
gehören. Eine Freistellung kann erst der folgende echte Journalvertrag liefern.

Die Rechteprüfung bleibt eine frische Beobachtung. Der tatsächliche Schreiber
muss seine Systemaufrufe weiterhin auf verweigerte Rechte, ACL-/Mountänderungen,
Quota, Platzmangel und I/O-Fehler prüfen. Es gibt keine Schreibprobe, chmod,
Permissionserhöhung, Diskspeicherreservierung oder OS-Sandbox. Ein kooperativer
Projektlock verhindert keine Änderungen durch absichtlich unkooperative Prozesse.
Die Werte `write_authorized=false`, `atomic_snapshot=false` und
`durability_verified=false` vermeiden eine verfrühte Freigabeaussage.

Ein ungültiger Auftrag wird vor der Veröffentlichung abgewiesen. Abweichende
Basisdateien oder Dateimengen liefern Konflikt 6; gefährliche Pfade oder eine
verweigerte Hostentscheidung Code 7; ungelöste Recoveryzustände und I/O-Probleme
bleiben getrennte Fehler. Nach Aufruf eines fehlerhaften Publishers bleiben
Schreibfolgen unbekannt. Keine automatische Wiederholung und kein Rollback.

Lokale Entwicklung prüft nur neue/direkt betroffene Verhaltenstests mit vier
Workern. Volltests laufen am Bundle-Abschluss in der CI, jede fünfte Nummer
zusätzlich seriell mit Nachweisvergleich. Keine Darstellungstests oder Testtimeouts.
Die Testpublisher sind absichtlich einfache owned-tempdir-Fixtures, keine
Produktimplementierung eines crashsicheren Journal-/Receipt-Backends.
