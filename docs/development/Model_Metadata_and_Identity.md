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
