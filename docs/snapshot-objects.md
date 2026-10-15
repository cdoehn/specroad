# Snapshotobjekte

`specroad.archive.SnapshotObject.from_json(original_bytes)` prüft ein JSON-Objekt
mit dem bestehenden strikten Reader und speichert seine kanonischen RFC-8785-
Bytes. `from_attachment(original_bytes)` übernimmt die Bytes unverändert.
`reference` enthält SHA-256, Byte-Länge und den daraus abgeleiteten Pfad
`archive/objects/<erste-zwei-hex>/<sha256>`.

`SnapshotObjectStore(root, protected_roots=(ProjectBoundary(project), ...))`
verwendet ein vorhandenes privates Arbeitsverzeichnis außerhalb aller angegebenen
Projekt-, Eingabe- und Ausgabegrenzen. Der Aufrufer benennt diese Grenzen
vollständig. Konstruktion und `get(reference)` schreiben nichts.
`put(snapshot_object)` speichert vollständige Bytes atomar ohne Überschreiben;
ein identischer vorhandener Inhalt wird nach erneuter Prüfung wiederverwendet.
Die native Speicherung benötigt die vorhandenen sicheren Linux-Datei- und
Lockprimitiven. Bei einem Fehler bleiben tatsächliche Dateien erhalten; daraus
folgt keine automatische Reparatur oder Freigabe zum Wiederholen.

`read_snapshot_object(ProjectBoundary(project), reference)` kann bereits
vorhandene Archivobjekte schreibfrei gegen Länge und Hash prüfen. Das bestätigt
die Objektbytes, keine Vollständigkeit oder Gültigkeit einer Baseline.

Der externe Store bereitet die Nutzdaten für den spezialisierten Baseline-Write
vor. Er legt keine Baseline im Projekt an. Die normative Veröffentlichung von
Manifest, Baseline-Artefakt und Objektdateien benötigt weiterhin den gemeinsamen
Change-Plan-, Writer-Lock-, Journal- und Receiptvertrag. Rolle, Medientyp,
Artefaktidentität, Revision und Scopebindungen ergänzt das Baseline-Manifest;
sie ändern nicht den Inhaltsschlüssel des einzelnen Snapshotobjekts.
