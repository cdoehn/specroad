# Gebundene Read-only-Arbeitspakete

`specroad.work.packages.export_work_package(store)` liefert die vollständigen
kanonischen ZIP-Bytes eines unabhängig gebundenen Read-only-Work-Stores. Der
Aufrufer bewahrt diese Bytes und ihren SHA-256 außerhalb des verlorengehenden
Arbeitsbereichs auf. Die API erzeugt keine Ausgabedatei, startet keinen Handler
und ändert weder Projekt noch Work-Root.

Das Paket enthält `work-package.json` mit `package_kind=work`, Work-ID, aktueller
Generation/Hash, ursprünglicher Manifest-/Checkpointbindung und Tool-Build.
Das Manifest inventarisiert alle tatsächlichen Payloads mit Pfad, Länge,
Medientyp und SHA-256, ohne sich selbst oder den vollständigen ZIP-Hash zu
inventarisieren. `work.json`, sämtliche erreichbaren Checkpointdatensätze,
Objektinventare und alle Objekte jeder Generation werden bytegenau erhalten.
Gebundene Eingangsdaten, Pläne, Teilergebnisse und vollständige gespeicherte
Read-only-Ergebnisse bleiben damit verfügbar. Unreferenzierte temporäre Dateien,
Root-Inodes und Prozess-Lockdatensätze werden nicht als portable Nutzdaten kopiert.

Der generische Codec verwendet geordnete NFC-POSIX-Pfade, ausschließlich reguläre
Dateieinträge, ZIP_STORED, feste Zeit-/Versions-/Attributfelder und keine Kommentare,
Extras oder Datendeskriptoren. Er prüft Containerbytes, externe Hashbindung,
kanonisches Manifest und exakte Payloadbijektion. Die erneute kanonische
Bytebildung erkennt auch abweichende Reihenfolge, Präfixe und angehängte Bytes.
Pfad- und Dateitypfehler werden vor jeglicher Extraktion abgewiesen. Der Codec
selbst extrahiert nichts und greift nicht auf ein Dateisystem zu.

`restore_work_package(raw, expected_sha256=..., registry=...,
protected_roots=..., directory=...)` verlangt einen extern erhaltenen erwarteten
Gesamthash, die aktuelle vertrauenswürdige Command Registry, explizite geschützte
Projekt-/Eingangs-/Ausgabegrenzen und einen tatsächlichen absoluten Zielpfad.
Paketbytes allein beweisen keine Herkunft; die externe Erwartungsbindung gehört
zum Aufruf. Es werden keine Programme aus dem Paket geladen.

Vor Anlage des Ziels werden Paketart, komplette Payloads, Runtime-Build,
Work-Schema und jede Generation der vollständigen Kette geprüft. Der ursprüngliche
Initialzustand, sämtliche Nachfolger und der aktuelle Pointer müssen zusammenpassen.
Zusätzliche unreferenzierte Payloads sind unzulässig. Fehlende Bytes werden nicht
aus ihren Hashes ersetzt. Die Paketdaten werden nicht in neue fachliche IDs oder
eine andere Auftrags-/Quellbindung umgeschrieben.

Das Ziel muss fehlen oder privat und leer sein. Der bestehende Work-Mutex schützt
die Leerprüfung, bevor ein Owner- oder Kontrollsatz geschrieben wird. Selbst ein
bereits gültiger Store desselben Auftrags ist kein erlaubtes Restore-Ziel. Der
native Pfadschutz verweigert Symlinks, unsichere Vorfahren und Überschneidungen mit
geschützten Roots. Die neue lokale Rootbindung verwendet den tatsächlichen neuen
Inode. Alle ursprünglichen Generationen werden über den vorhandenen dauerhaften
Checkpoint-Publisher in private Dateien geschrieben; der letzte Pointer bleibt
bytegleich zum exportierten Zustand.

Bei I/O-Fehlern bleiben tatsächlich geschriebene Dateien und bereits veröffentlichte
Generationen erhalten. Ein später Fehler nach Pointerwechsel wird nicht als
Rollback oder vollständiger Restore umgedeutet. Ein erneuter Restore überschreibt
kein solches inzwischen nichtleeres Ziel. Der gespeicherte vollständige Präfix
kann separat mit seiner ursprünglichen Bindung geprüft werden.

Die geschlossenen Bootstrap-Adapter können nach Wiederherstellung tatsächlich
weiterarbeiten oder ihre ursprünglichen Ergebnisse liefern. Generische deklarierte
Work-Daten und Snapshotbytes behalten ihre Bindungen; daraus entsteht keine
zusätzliche Befugnis, unbekannte Aufgaben auszuführen. Abgebrochene Arbeit bleibt
abgebrochen, unvollständige Handlerarbeit bleibt unvollständig. Eine Distribution
wird separat benötigt und nicht aus dem Arbeitspaket importiert.

Dieser W-Stand verarbeitet Read-only-Arbeit und vollständige gewöhnliche ZIP32-
Archive im Speicher. Normative Work-Aufträge werden ausdrücklich abgewiesen,
solange keine gesonderte aktuelle Transaktions-/Receiptbindung für ihren Export
vorliegt. Ein Paket ersetzt keine aktive Projekt-Recovery. Work-CLI, allgemeine
Workflowausführung, portable normative Zielzuordnung, große fortsetzbare Exporte
und Multipartarchive bleiben offen; die Anforderungen werden nur partiell belegt.
