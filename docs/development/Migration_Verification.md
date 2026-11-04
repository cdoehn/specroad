# Lesende Migrationsprüfung

verify_migration prüft ein vollständiges Source-ZIP, die ursprünglichen
Plan-/Berichtbytes und sämtliche Zielbytes gegen explizite erwartete Hashes.
Es berechnet Planungs-/Verlustbericht und Zielwurzel nativ neu, prüft das
vollständige Zielmodell mit registrierten echten ModelGates und vergleicht
historische Originale und Baselinehashes mit dem Quellleser. Ein fehlender
Fachservice bleibt ein Fehler. Vollständige Inventare machen fehlende,
zusätzliche und veränderte Dateien sichtbar.

verify_migration_project ergänzt die stabile lesende Beobachtung des echten
Projektroots und seiner nativen abgeschlossenen Migration. Nur die eigenen
vollständig verifizierten Receipt-/Recoverybytes werden separat ausgewiesen.
Vorhandene passive Source-Dateien bleiben im gebundenen Zielinventar.
Die Prüfung erzeugt keine Locks oder Projektdateien. Sie behauptet weder
einen atomaren Snapshot noch heutige Evidence-Gültigkeit, Readiness oder
Schreib-/Reviewfreigabe. Nachträgliche Änderungen verlangen eine neue Prüfung.

Diese Bibliotheksarbeit registriert keine noch ungeprüften öffentlichen
CLI-/Restorepfade. Die verbleibenden M16-Integrationsgates bleiben ausdrücklich
offen. Tests verwenden klar bezeichnete synthetische Daten, Hostautorität
und Buildbindungen; sie erfinden keine echten Reviews oder externen Läufe.
Verhaltenstests laufen ausschließlich in Apply vor jedem einzelnen Commit.
Collection und AST-/Paketprüfung sind kein Testerfolg.
