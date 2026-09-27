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

## Direkte Planung und Robustheit (R)

`prepare_change_target` nimmt explizite, bereits vorbereitete Operationen sowie
Plan-ID, Request-ID, Akteur, Zeitpunkt, Scope, Metadatenpolicy und Befehlspolicy
entgegen. Sie erzeugt einen regulären gespeicherten Plan und verwendet danach
EXAKT dieselbe Zielbewertung wie `assess_change_target`. Es gibt keinen zweiten
vereinfacht grünen direkten Schreibweg. Create-Payloads müssen zum bestehenden
Planvertrag passen, insbesondere ihre expliziten Erstellungsmetadaten. Dies ist
noch kein Komfort-Authoring für unvollständige CLI-Entwürfe.

Der übergebene Bestand wird vor jedem Aufruf erneut aus seinen Originalbytes
aufgebaut. Abgeleitete Ressourcenmetadaten ersetzen nie die Quelldateien.
Sprachpakete werden aus ihren tatsächlichen Bytes neu gebunden. Ausdrücklich
bekannte historische und reservierte Artefakt-/Relations-IDs fließen in die
Prüfung und Ergebnisbindung ein; eine vollständige Historie wird nicht behauptet.

Alle registrierten Whole-Target-Extension-Gates laufen auch bei einem leeren
Artefaktbestand. Fehlende erforderliche Gates verhindern einen vollständigen
Abschluss. Rohe Regel-/Mappingressourcen benötigen zusätzlich den ausdrücklich
registrierten vertrauenswürdigen Prüfer `extension:target-resources`; ihre
Hashform allein ist keine semantische Integritätsprüfung. Der Prüfer bindet
seine tatsächlichen Ressourcen über die bestehenden Gate-Verträge. Wie bei den
anderen Python-Gates bleibt dies eine explizite Vertrauensgrenze.

Ein fehlerhafter Gesamtbestand liefert keine Freigabe, auch wenn alle unmittelbar
bearbeiteten Artefakte einzeln gültig erscheinen. Warnings und Fail-Schwellen
bleiben getrennt. Ein alter Gate-Nachweis passt nicht zu einem anderen Plan,
Befehl, Ressourcensatz oder Reservierungsbestand.

## Gemeinsame Grenzen (C)

`target_model.py` kapselt ausschließlich unveränderliche Eingabeaufnahme,
Ressourcen-/Profilbindung und Manifestbildung. `_target_checks.py` verbindet
registrierte Gesamtziel-Gates und den bestehenden Vorher-/Nachher-Impact.
`target.py` bietet beide öffentlichen Adapter über einen gemeinsamen
Validierungspfad. Es gibt keine alternative, schwächer geprüfte Write-Route.
Die Statusentscheidung bleibt im bestehenden Lifecycle-Planner, nicht in einem
Dateischreiber. Die Tests aus W und R bleiben bei dieser Trennung unverändert.
