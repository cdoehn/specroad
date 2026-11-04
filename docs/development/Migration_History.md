# Historische Evidence und Baselines

verify_source_history qualifiziert vollständige Originalbytes gegen den
eingebauten Vertrag specroad-reference-0.1/1.0.1. verify_migrated_history
qualifiziert das Legacy-Manifest samt allen tatsächlichen Originaldateien
und rekonstruiert denselben Quellbestand. historical enthält die ursprünglichen
Baseline- und Evidencebindungen in ihren jeweiligen Quellhashdomänen.
legacy_manifest_sha256 bindet getrennt den aktuellen Aufbewahrungsnachweis.
Eine gespeicherte Berichtsdatei kann diese Prüfung nicht ersetzen.

verify_baseline_snapshot verwendet für alte Originale dieselbe Sourceprüfung
und deren reference01-model-root-v1. Im migrierten Projekt ist die vollständige
Manifestregistrierung erforderlich; das Label schema_version allein reicht
nicht. Der historische Ergebniszweig heißt historical-baseline-verification-v1
und behauptet keine aktuelle Gesamtvalidierung, Readiness oder atomare
Dateisystemsicht. Aktuelle 0.2-Baselines behalten ihren bisherigen Verifier.
Restore und materialisierte Vergleichsquellen behalten ihre bisherigen
Schemaeinschränkungen bis zur eigenständigen vollständigen Integration.

assess_verification_context erhält für LegacyArtifact ausdrücklich
legacy_manifest mit tatsächlichen Originalbytes. Das Manifest wird erneut
nativ qualifiziert. Der Bericht bleibt stale/migration_context_unverified;
ein aktueller oder unabhängiger Vertrag und eine Navigation ändern dies nicht.
Das optionale Vertragsargument wird nativ geprüft, aber nicht zur Wiederverwendung
alter Evidence eingesetzt. Eine neue Messung benötigt eine neue ID und
prepare_evidence_record mit heutigem Subject-/Vertragskontext. Der alte Datensatz
bleibt unverändert. Dieser Konstruktor ist noch keine persistierte Messung oder
externe Laufbestätigung. Format und die regulären Update-/Lifecyclepfade lassen
keine Legacy-Projektion als schreibbares aktuelles Original zu.

Alle APIs lesen ausschließlich und interpretieren keine Payload als Programm.
Ein positives Integritätsergebnis authentifiziert weder einen externen Lauf
noch einen historischen menschlichen Entscheid. Pure Byte-APIs binden den
übergebenen Snapshot; ihre Besitzer sind für neue Livebeobachtungen zuständig.
Der Dateisystemadapter liest descriptorgebunden, prüft offene Transaktionen
und kontrolliert Original-, Konfigurations- und Rootwechsel erneut.
Die synthetischen Testdaten erfinden keine realen Freigaben. Die vorbereiteten
Verhaltenstests laufen ausschließlich in den getrennten Apply-Gates.
