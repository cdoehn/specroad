# Zielvalidation, Diff und Impact (5.f)

`TargetModel` übernimmt ausdrücklich gelieferte Originalbytes von Konfiguration,
Artefakten und Ressourcen unter einer gemeinsamen Projektbindung. Die API öffnet
keine Pfade. Ressourcenhashes und das wirksame Profil werden aus den Bytes erneut
bestimmt. Das ist keine Bescheinigung einer vollständigen Inventur auf dem Gerät.

`assess_change_target(plan, model, policy=..., gates=...)` prüft den unveränderten
Planhash, die Basiswurzel und die nach geordneter Lifecycle-/Metadatenplanung neu
berechnete Zielwurzel. Die `result_artifacts` müssen ebenfalls exakt stimmen.
Die gemeinsame Validierung bekommt ALLE Artefakte des isolierten Ziels; sie wird
nicht auf berührte IDs beschränkt. Erforderliche, aber fehlende Fachprüfer sowie
fehlende explizite befehlsspezifische Gates verhindern `target_validated=true`.
Registrierte Gates prüfen denselben gebundenen Bestand und erhalten plan-,
ressourcen- und befehlsspezifische Eingabebindungen. Ihr Python-Code bleibt
vertrauenswürdig und ist weder durch einen Namen authentifiziert noch sandboxed.

Der vorhandene fachliche Vergleich liefert hinzugekommene, geänderte und andere
beobachtete Zustände samt Feldpositionen. Direkter Impact wird für beide Seiten
berechnet, damit entfernte und neu hinzugekommene Beziehungen sichtbar bleiben.
Das Ergebnis ist keine transitive Einflussanalyse. Exakte Originalbytes und
kanonische Werte bleiben getrennt; unveränderte Dateien werden nicht umkodiert.

## Grenze

Unterstützt ist zunächst der unkonfigurierte, geschlossene Projektbestand über
vollständig übergebene aktuelle Ressourcen. Konfigurierte oder partielle Scopes
benötigen einen eigenen vollständigen Provider und werden hier zurückgewiesen.
Die sechs bestehenden Standardoperationen bleiben die ausführbare Teilmenge.
Neue Approvals und spezialisierte Lifecycle-/Evidence-/Reviewoperationen werden
nicht durch eine generische Freigabe ersetzt.

`target_validated` ist eine Datenbeobachtung, keine erteilte Freigabe. Immer:
`transaction_prepared=false`, `execution_ready=false`, `write_authorized=false`,
`atomic_snapshot=false`. Vor einer tatsächlichen Veröffentlichung sind unter
anderem frische Eingaben, autorisierte Fachworkflows, Locks, Staging und fsync
nötig. Sie werden durch den Hash allein nicht bewiesen.

## Tests

Pixel: nur neue und direkt betroffene Testdateien mit vier xdist-Workern. Keine
lokale Vollsuite und keine serielle Vollsuite. Der Katalogcheck sammelt lediglich
alle Testkennungen. Vollsuite auf GitHub am Bundle-Ende, jedes fünfte Bundle
zusätzlich seriell plus Nachweisvergleich. Menschliche Darstellung ist kein
Testorakel. Die Source- und Reportbindungen werden nicht zu Releasefreigaben.
