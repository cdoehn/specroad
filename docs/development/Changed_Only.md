# Changed-only mit Closure (Bibliotheksstand 8.k.R)

`check_changed_sources(before, after, profile_paths=..., core_key=...)` verwendet
zwei bereits erfasste `ComparisonSourceSnapshot`-Werte. Die Basis muss ein gebundener
Git-Commit sein; Projekt-ID und ID-Präfix müssen übereinstimmen. Fehlende oder
unaufgelöste Basen werden vor der Validierung abgewiesen. Es werden weder Dateien
nachgeladen noch aktuelle Dateien ersatzweise in eine historische Quelle eingefügt.

Der semantische Artefakt-/Konfigurationsvergleich bestimmt die geänderten IDs.
Die vorhandene `validate_model`-Pipeline erweitert die Auswahl um eingehende,
ausgehende und ausdrücklich deklarierte Gate-Abhängigkeiten. Struktur, Referenzen
und Graph werden über alle erfassten aktuellen Artefakte geprüft, damit außerhalb
der direkten Auswahl liegende Abhängigkeiten nicht verborgen bleiben. Die
semantischen Prüfungen und Core-Lint verwenden den tatsächlich erweiterten Umfang.

Profile stammen ausschließlich aus den erfassten aktuellen Ressourcenbytes.
`profile_paths` ordnet jeden Schlüssel der komponierten Profilkette genau einem
vorhandenen Profilpfad zu. Es gibt keinen Ersatz durch lose übergebene alte
Profilwerte. Tatsächliche SRX-Profilregeln laufen über die bestehende produktive
Validierung. Profilressourcenänderungen, semantische Konfigurationsänderungen und
gelöschte Artefakte wählen konservativ alle verbleibenden aktuellen Artefakte als
Seeds. Eine engere Auswahl würde dafür zusätzliche zertifizierte Abhängigkeiten
benötigen. Geänderte Ressourcen außerhalb dieser ausdrücklich gebundenen Profile
werden bis zu ihrer fachlichen Unterstützung abgewiesen.

Das eigene Ergebnis `changed-checks-v1` bindet Basis-Commit, beide Quellensnapshots,
Profilressourcen, geänderte/gelöschte IDs, Seeds, tatsächlich geprüfte Artefakte und
zusätzlich erreichte Abhängigkeiten. Native Validierungsberichte, Bewertung unter
dem gewählten Fehlerschwellwert und Core-Lint-Ergebnisse bleiben vollständig
erhalten. `full_project_validation`, `full_lint`, `project_files_verified`,
`atomic_snapshot`, `approval_granted` und `write_authorized` bleiben falsch.
Ein erweiterter Umfang, der zufällig alle aktuellen IDs umfasst, ist keine
zugesicherte Projektvollprüfung.

Ohne semantische Änderungen lautet der Status `no_changes`; ohne verbleibende
aktuelle Artefakte nach Änderungen `no_current_artifacts`. In beiden Fällen bleiben
die Prüfberichte leer, `checks_complete` falsch und `passed` null. Ein leerer
Prüfumfang beweist keinen gültigen Modellzustand. Fehlende erforderliche Dienste
bleiben im nativen Bericht unvollständig; vorhandene Fehler werden nicht verdeckt.

Bei unvollständiger Validierung bleibt ein bereits beobachteter Warnungsbefund
unter `fail_on='warning'` oder `strict=True` im Gesamtergebnis als `passed=false`
erhalten. Fehlende Dienste lassen `checks_complete=false` und `status=incomplete`
bestehen. Die native Diagnosebewertung mit ihrem Exit Code 5 wird unverändert
weitergereicht; ein bekannter Befund und fehlende Vollständigkeit sind getrennte
Aussagen. Ohne bekannten Schwellwertverstoß bleibt das Ergebnis unbekannt.

Scheitert die Abhängigkeitsbestimmung, sind die äußeren geprüften/zusätzlich
erreichten IDs leer und Core-Lint wird nicht gestartet. Der native Bericht kann
weiterhin die versuchten Seeds enthalten; sein Scope-Status erklärt, warum daraus
kein nachgewiesener Prüfumfang folgt. Ohne ausgeführte Modellprüfung lauten die
äußeren strukturellen und semantischen Scopes `not_run`. Eine bereits erfasste
Quelle wird später rein aus ihren eigenen Bytes geprüft, ohne damit aktuelle
Dateien zu bestätigen.

Dies ist eine Bibliothekskomposition für geladene Snapshots. Diff-/Changed-only-CLI,
Work-Fortsetzung, zusätzliche Quellenadapter, live erneuerte Dateiprüfungen,
literal-/sprachbezogenes Gesamtlint, vollständige Ressourcen- und Modellsemantik,
Language-Registry-Anbindung in diesem Adapter und skalierbare Verarbeitung bleiben
offen. Explizite `ModelGate`-Callbacks sind vertrauenswürdiger Host-Code; es wird
kein ausführbarer Projektinhalt entdeckt oder geladen. Die Callback-Schnittstelle
ist kein Betriebssystem-Sandboxvertrag.
