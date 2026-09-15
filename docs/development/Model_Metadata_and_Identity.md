# Modellgrenzen: Metadaten und Identität

## 2.f – passive Metadaten

`extensions` enthält ausschließlich namespaced Schlüssel. Ein Namespace besteht
 aus mindestens zwei nichtleeren, punktgetrennten Komponenten ohne Leerraum oder
Steuerzeichen. Eine Registrierung, Anbietererreichbarkeit oder Beschränkung auf
ASCII wird nicht vorausgesetzt. Unterhalb eines solchen Schlüssels bleiben
beliebige gültige JSON-Werte Daten; auch `$ref`, Shelltexte und Pluginnamen werden
weder aufgelöst noch ausgeführt. Die Prüfung gilt auch für Projektkonfiguration
und bereits vorhandene Extensions-Felder gespeicherter Relationen.

Provenance folgt dem Minimalvertrag aus Spec 9.5. Die lokale Feldabbildung lautet
`source_id` oder `locator`, `captured_at` und mindestens `excerpt` oder
`content_sha256`. Locator, Zeitpunkt, Excerpt und Hash verwenden dieselben Namen
wie die Source-Datenverträge. Beide Alternativen dürfen zugleich vorhanden sein.
Weitere Anbieterangaben gehören in `extensions`. Diese Formprüfung authentifiziert
keine Quelle, liest keinen Locator und vergleicht keinen Hash mit externen Daten.

`display_id` ist optionaler Text, keine andere Schreibweise der stabilen `id`.
Die vorhandenen Common-/Domain-/Record-Leseschichten erhalten dieses Feld.
`storage.metadata.serialize_common_artifact` ist ausschließlich ein reiner
JSON-Byte-Serializer für gemeinsame Feldverträge. Er schreibt keine Datei,
vergibt keine Revision und ist weder JCS-Formatter noch Publikationsfreigabe.
Die vollständigen Typ-/Graph-/Profil-/Freigabeprüfungen bleiben eigenständige
Schichten. Der Katalog weist die jeweiligen Anforderungen weiterhin als teilweise
implementiert aus.

Der reine `resolve_artifact_reference`-Helfer prüft ein explizit übergebenes
Projektinventar und sucht ausschließlich nach `id`. Gleiche `display_id`-Werte
sind zulässig; doppelte reale IDs sind Fehler. Ein Label wird auch dann nicht als
Alias akzeptiert, wenn es zufällig wie eine gültige ID aussieht. Die Existenz
aller Quellen oder die Vollständigkeit eines Projektgraphen wird damit nicht
behauptet; der Helfer lädt selbst keine Dateien.

## 2.g – Artefaktidentitäten

Neue Artefaktidentitäten verwenden `secrets.token_bytes(16)`, unveränderte 128 Bits
und einen kanonischen 26-stelligen Crockford-Token (erstes Zeichen 0–7). Legacy-IDs
sind ausschließlich lesbare Bestandsidentitäten. Kein zentraler Zähler, Server,
Netzwerkzugriff oder Git-Branch wird zur Generierung benötigt.

`IdentityInventory` verlangt alle drei Mengen ausdrücklich: aktuell, archiviert
und reserviert. Nach einer Kollision wird neu ausgelost; erst ein freier Kandidat
führt zu einer zurückgegebenen Kopie mit zusätzlicher Reservierung. Der Eingang
wird nie verändert. `IdentityAllocation` ist ein Modellwert, KEIN dauerhafter
Projektanspruch. Der spätere Transaktionspfad muss vollständige Inventare ermitteln,
binden, erneut prüfen und Reservierung/Artefakt atomar veröffentlichen. Die
hier implementierte Generierung enthält absichtlich keine Dateisuche oder Writes.

Normale Änderungswege können `require_identity_unchanged` verwenden: `id`,
`id_scheme`, Typ und Projektanteil dürfen nicht wechseln. Fehlendes Legacy-Schema
wird nicht generisch ergänzt; die Ausnahme bleibt auf die spätere Migration
beschränkt. Labels, Titel und andere Metadaten ändern diese Identitätsprüfung
nicht. Sie ist keine Aussage zur fachlichen Zulässigkeit anderer Änderungen.
Doppelte aktuelle IDs werden zurückgewiesen; mehrfach in historischen Ständen
vorkommende IDs bleiben als eine dauerhaft belegte Identität gesperrt.
