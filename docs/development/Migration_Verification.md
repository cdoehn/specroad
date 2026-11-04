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

Die nativen Host-APIs prepare_migration_planning_work und
prepare_migration_verification_work erstellen passive Work-Eingaben mit
expliziter CommandRegistry. resume_migration_work bestätigt je Aufruf eine
der festen Source-/Plan-/Prüfphasen; ein weiterer Aufruf sichert den Abschluss.
Alle Eingaben und alte Phasenbeweise werden nativ requalifiziert. Ein positiver
gespeicherter Bericht ist keine Fortsetzungs- oder Schreibberechtigung.
Work-Pakete erhalten vollständige Checkpointketten und Originalbytes;
neue Verzeichnisse erhalten neue native Root-/Ownerbindungen. Ein anderer
Build, Datenverlust oder unbestätigter Zustand führt zu einem echten Blocker.

migration_work_result prüft ein abgeschlossenes Ergebnis frisch anhand seiner
gebundenen Originale. Planungs-Work benennt den Zielstand als geplant,
Prüf-Work als bereitgestellte Zielbeobachtung. apply_migration_work übergibt
nur einen vollständig erneut qualifizierten Plan an den bestehenden Writer.
Der Host liefert Projektwurzel, externe Sicherung, Transaktions-ID, echte
Autorität und Fachdienste neu. Alle ursprünglichen Hashbindungen gelten.
Der Writer prüft Source und Ziel frisch unter dem gemeinsamen Writerlock,
publiziert eine Transaktion und erhält die bisherigen Receipt-/Recoveryregeln.
Ein Work-Replay startet keine automatische Recovery und erhöht keine Revision.

Diese Bibliotheksarbeit registriert keine noch ungeprüften öffentlichen
CLI-/Restorepfade. Die verbleibenden M16-Integrationsgates bleiben ausdrücklich
offen. Tests verwenden klar bezeichnete synthetische Daten, Hostautorität
und Buildbindungen; sie erfinden keine echten Reviews oder externen Läufe.
Verhaltenstests laufen ausschließlich in Apply vor jedem einzelnen Commit.
Collection und AST-/Paketprüfung sind kein Testerfolg.
