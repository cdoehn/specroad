# Ressourceninventur und Anhangsdaten (2.l)

## Verwendung

```python
from specroad.storage.project import ProjectSource
from specroad.model.attachments import AttachmentDescriptor
from specroad.storage.attachments import inspect_attachment, verify_attachment
from specroad.storage.inventory import inventory_project, check_inventory_current

source = ProjectSource("/path/to/project")
# Medientyp bewusst deklarieren, nicht aus Endung oder fremdem Programm erraten.
observed = inspect_attachment(source, "attachments/report.bin", "application/octet-stream")
expected = AttachmentDescriptor.from_data(observed.data)
verify_attachment(source, expected)

# Enthält sämtliche aktuellen normativen JSON-Dateien in den verwalteten
# Verzeichnissen und die im Evidence-Feld attachments referenzierten Bytes.
# Zusätzliche Referenzen müssen ausdrücklich übergeben werden.
inventory = inventory_project(source, attachments=(expected,))
check_inventory_current(source, inventory)
```

`inspect_attachment` ermittelt die tatsächliche Byte-Länge und SHA-256.
`verify_attachment` vergleicht sie mit der vorgegebenen Beschreibung.
Eine erfolgreiche Prüfung belegt diese Bytes, nicht die Echtheit externer Evidence,
das inhaltliche Dateiformat oder das Bestehen eines Produkttests. `media_type` ist
eine deklarierte Metadatenangabe; es gibt keine MIME-Erkennung oder Registrierung.

## Vollständigkeit und Pfadklassen

`scope=current_resources` umfasst `specroad.json`, alle normativen JSON-Dateien in
den konfigurierten Teilen von `spec/`, `profiles/`, `rules/`, `mappings/`, konfigurierte
Sprachregisterbytes und die explizit referenzierten Anhänge. Überlappende verwaltete
Verzeichnisse werden ohne Doppelzählung behandelt. Konfigurierte einzelne JSON-
Dateien müssen existieren; leere/fehlende optionale Verzeichnisse sind zulässig.
Ein Verzeichnis bleibt auch mit der Endung `.json` ein Verzeichnis.

Nur das definierte `attachments`-Feld von Evidence wird automatisch ausgewertet.
Beliebige Strings in Extensions, Links oder Shelltext sind keine Anweisungen.
Mehrere Evidences dürfen dieselbe exakt übereinstimmende Anhangsbeschreibung
referenzieren. Widersprüchliche Größe, Hash oder Medientyp werden nicht geraten.
Doppelte Referenzen innerhalb einer Evidence beziehungsweise einer ausdrücklich
übergebenen Liste werden abgewiesen. Groß-/Kleinschreibungs-Kollisionen sind Fehler.

Unreferenzierte Anhänge, Archivobjekte, generierte Ausgaben, Cache und betriebliche
Recovery-/Receipt-Dateien werden nicht still zu aktuellen normativen Eingaben.
Die Spezialclosure von Baselines, Bundles und Work sowie aktive Profile, Sprach-
pakete und andere spätere Fachauflösungen gehören nicht zu dieser Inventur.
Sie müssen ihre zusätzlichen Pflichtmengen ausdrücklich über deren Verträge binden.
Die Inventur ist deshalb kein bereits fertiges Vollbundle oder Baseline-Manifest.

Artefaktdateien werden auf gemeinsame Felder und Pfad-/ID-Zuordnung geprüft;
Profile/Regeln/Mappings hier auf strikte JSON-Syntax und Formatversion.
Das ersetzt keine vollständige typspezifische, Relations-, Profil- oder SRX-Prüfung.

## Integrität und Sicherheitsgrenze

Anhangsbytes werden blockweise (standardmäßig 64 KiB) gehasht. Die gesamte Datei
wird nicht im Arbeitsspeicher gehalten. Neue Leser erwarten sichere relative
Pfade, öffnen relativ zu gebundenen Verzeichnisdeskriptoren und folgen keinen
Symlinks. Auch interne Symlinks und Sonderdateien werden konservativ abgelehnt.
Frisches stat ohne Linkverfolgung vermeidet gecachte DirEntry-Typangaben.
Fehlt die notwendige Plattformunterstützung, wird nicht auf ungesicherte Pfad-
öffnungen ausgewichen. Die vorhandene Windows-/Plattform-Nachweisgrenze bleibt
bestehen; diese Änderung behauptet keine Windowsfreigabe.

Dateiaustausch, beobachtete Inhaltsänderungen, neue verschachtelte Projektroots,
fehlende Dateien und Lese-/Berechtigungsfehler führen zum Abbruch. Ein wachsender
Anhang darf den Lesevorgang nicht endlos verlängern: Mehr Bytes als zu Beginn
beobachtet werden unmittelbar zurückgewiesen. Alle geöffneten eigenen
Deskriptoren werden auch bei Fehlern geschlossen.

Vor Rückgabe werden die gebundenen Inhalte sowie die JSON-Dateimenge erneut
geprüft. Es wird kein teilweise erfolgreiches Inventar zurückgegeben. Trotzdem
ist `atomic_snapshot` ausdrücklich `False`: Ohne Transaktionslock ist die
Gesamtsicht kein atomarer Mehrdatei-Snapshot und erkennt nicht jede mögliche
ABA-Änderung. Künftige schreibende/versiegelnde Operationen müssen ihre eigenen
Locks, Vorbedingungen, vollständigen Closures und Zielprüfungen einsetzen.
`check_inventory_current` kann nie als dauerhafte Schreibberechtigung dienen.

Die Inventur speichert sowohl den Originalbytehash als auch den vollständigen
JCS-Werthash normativer JSON-Ressourcen. `inventory.sha256` bindet den gesamten
byteempfindlichen Inventarvertrag. Er ist ausdrücklich **nicht** der spätere
fachliche `model_root_sha256`; reine Formatänderungen können die Inventarbindung
ändern, obwohl der JCS-Werthash gleich bleibt. Hashes sind keine Signaturen.
Die lokale Rootbindung für Frischeprüfungen wird nicht in portable Fachhashes
aufgenommen. Ein anderer Root mit denselben Daten hat also dieselbe inhaltliche
Inventarbindung, erhält dadurch aber keine lokale Zugriffsberechtigung.

## Struktur und Tests

`model/resource_inventory.py` enthält die unveränderlichen Beobachtungswerte.
`storage/resource_discovery.py` kapselt die Inventarisierung. `storage/byte_binding.py`
hält die wiederverwendbare blockweise Hashbildung; Descriptor-/Rootprüfungen
bleiben in `security/resource_access.py`. Die bisher eingeführten Imports aus
`storage/attachments.py` und `storage/inventory.py` bleiben nutzbar.

Verhaltenstests benutzen eigene temporäre Projektverzeichnisse, echte Binärdaten
und gezielte Störungen. Sie prüfen vollständige Ressourcenmengen, Bytebindungen,
Frische, blockweises Lesen, Isolation, sichere Fehler und verschobene Modul-/Zipapp-
Distributionen. Keine Layout-, Konsolentext-, Farb- oder Dokumentationstests.
Für die parallele Vollsuite gilt die lokale AGENTS.md; technische Aufrufe beschreibt
[Testing.md](Testing.md).
Keine neuen Core-Abhängigkeiten, kein neuer CLI-Befehl, kein Cache- oder Projektwrite.
