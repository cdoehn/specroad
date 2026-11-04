# Legacy-Originale und Manifestbindung

mappings/legacy-manifest.json ist eine normative Ressource gemäß Anhang Q
und 12.20.2. Der Leser akzeptiert nur den eingebauten Referenzquellvertrag
0.1/1.0.1. Er rekonstruiert das Originalinventar aus registrierten Bytes,
qualifiziert dessen vollständige historische Closure und vergleicht das
Manifest mit dem gemeinsamen nativen Generator. Ein Versionsetikett oder ein
selbst behaupteter Hash allein genügt nicht. Keine Projektdatei wird als
Schema oder Programm ausgeführt.

ProjectSource bindet diese Qualifikation beim Modelllesen. Die regulären
Artefaktleser liefern für registrierte historische Artefakte LegacyArtifact:
source_bytes und data enthalten das unveränderte Original, storage_class ist
legacy_immutable. navigation ist eine eigene Kopie der Identitäts- und
Relationsprojektion und bleibt schema_version 0.1.0. Sie darf weder formatiert
noch als neues 0.2-Original gespeichert werden. Show/Relationsleser können mit
diesen Projektionen navigieren, ohne das gespeicherte Artefakt umzuschreiben.

Explizite Modellhash-Erfassung nimmt Manifest und registriertes Originalarchiv
immer auf. Legacy-Artefaktrows binden legacy-original-bytes-v1, den Original-
bytehash und den JCS-Hash des Manifests. Aktuelle Artefakte behalten die bisherige
Hashdomäne. Frische Prüfungen binden Manifest und physische Originale; die
Lesebeobachtung ist kein atomarer Snapshot und kein Schreibrecht.

Vollständige historische Verifikation und aktuelle Readiness sind spätere
M16-Gates. Ebenso bleiben produktiver Migrationswriter, öffentliche CLI und
Restore gesondert. Der vorhandene Restore-Formatblock bleibt aktiv. Tests
sind für die einzelnen Apply-Gates vorbereitet und werden nicht in Dev ausgeführt.
