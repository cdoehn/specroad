# CI-Korrektur: echte Testidentitäten und Katalogvorprüfung

Die hier beschriebenen Testauswahl-, CI-Auslöse- und Volltestmodusregeln gehören
zu den historischen Bundles 010–012 und sind außer Kraft. Für die aktuelle
Testausführung gilt die lokale `AGENTS.md`; die technische Anleitung steht in
[Testing.md](Testing.md). Die damaligen Befunde und Nachweisgrenzen bleiben erhalten.

## Befund vom 22. September 2026

Das Result `specroad_Result_094144_0922_666714.zip` bestätigt Bundle 010
lokal und den sauberen Stand `5ece0d41b2afac51fb1f82b697cd029948230ccf`
auf dev mit 150/885 Produktplan-Commits. Die angehängten GitHub-Logs melden
bei CPython 3.10, 3.11, 3.12, 3.13 und 3.14 bereits vor dem ersten Test
`Manifest names an unavailable real test: SR-TC-0295`. Die folgende xdist-
Assertion ist nicht der Beleg eines gescheiterten SpecRoad-Fachtests.

Die tatsächliche pytest-Sammlung hat 2.710 Einträge. Der Vergleich findet
21 falsche Referenzen in SR-TC-0295, SR-TC-0296 und SR-TC-0523.
Native pytest-Funktionen verwenden `tests/datei.py::test_name`, nicht die
für diese Funktionen ungültige Schreibweise `datei.test_name`. Bestehende
unittest-IDs bleiben unverändert. Die Korrektur schreibt ausschließlich die
21 Verweise um; sie entfernt keine Tests und erhöht keine Anforderungsreife.

## Vorprüfung ohne Testausführung

`tools/check_test_catalog.py --output NEUER_PFAD` lädt den Katalog und
sammelt die Tests tatsächlich über pytest. Es importiert vertrauenswürdige
Testmodule; es ist keine Import-Sandbox. Keine Testfunktion, keine Testfixture
und kein xdist-Worker wird bei dieser Sammlung ausgeführt. Parametrisierte
Fälle müssen mit ihren konkreten Test-IDs gebunden sein. Keine Umwandlung,
kein Import von im Manifest genannten Python-Ausdrücken, kein stiller Alias.

Der JSON-Bericht ist ausdrücklich `catalog_collection_preflight` mit
`tests_run: 0` und `full_suite_passed: null`. Er enthält alle fehlenden
Referenzen und Bindungen an Quellen, Spezifikation und Katalog. Er ist niemals
ein bestandener Volltest oder Release-Nachweis. Bestehende Berichte werden
nicht überschrieben; Quellenänderungen während der Sammlung machen ihn ungültig.

Vor einem lokalen Aufruf von `tools/run_selected_tests.py` wird diese Prüfung
im getrennten Interpreter ausgeführt. Anschließend laufen nur die explizit
gewählten Testdateien parallel. Die Katalogprüfung erweitert nicht heimlich
den lokalen Testumfang auf die gesamte Produktsuite. In GitHub erhält die
Matrix einen separaten Sammlungsschritt vor den Volltests und sichert auch
bei dessen Fehler den Diagnosebericht als Artefakt.

Die Volltestpolicy bleibt unverändert: manuelle Volltests bei Zwischenständen,
automatische parallele Volltests beim Abschluss auf dev, zusätzlich seriell
und Vergleich bei jeder durch vier teilbaren Bundle-Nummer. Kein Update von
main, kein Force-Push, keine ausgelassenen Prüfungen zur Erzeugung grüner CI.

## Nachweisgrenze

Der Status des alten CI-Laufs wird nicht nachträglich grün erklärt.
Die Korrektur benötigt nach lokalem Apply und normalem dev-Push einen neuen
GitHub-Lauf über die unterstützte Python-Matrix. Teiltests auf dem Pixel
und kleine künstliche Framework-Prozessregressionen ersetzen diesen nicht.

## Kontrollierter Fehler vor dem Teststart

Auch ein direkter Volltest-Aufruf ohne vorgeschaltete Katalogprüfung prüft die
Zuordnung vor der Worker-Scheduling-Freigabe. Bei einem Vertragsfehler meldet
der Worker einen ausdrücklichen Session-Stopp, statt kommentarlos aus dem
xdist-Lebenszyklus zu verschwinden. Die Abschaltung und Verteilung bleiben bei
pytest/xdist; SpecRoad implementiert keinen eigenen Scheduler.

Der Controller erhält die tatsächliche Fehlerursache und veröffentlicht nach
Möglichkeit einen gesonderten Fehlerbericht und die Laufbeobachtungen. Ein
Katalogfehler ist kein bestandener Entwicklungsnachweis und keine Freigabe.
Fehlt der erfolgreiche Testlauf, bleiben `suite_passed` und `release_approved`
falsch. Die kleinen Prozessregressionen prüfen dies mit 0, 2 und 4 Workern; sie
führen dabei nur synthetische Vier-Test-Projekte aus, keine serielle
SpecRoad-Vollsuite auf dem Pixel.

## Abschluss und erhaltene Grenzen

Die Identitätsabbildung liegt gemeinsam in `collection_identity.py`, die
Katalog-/Berichtsverträge in `catalog_contract.py`. Sammeln und Ausführen
verwenden denselben Identitätsvertrag, aber getrennte Prozessabläufe. Die
Spezifikation, sämtliche Produktdateien und die Anforderungsreife bleiben
unverändert. Lokal werden nur die ausgewählten Testdateien mit vier Workern
ausgeführt. Die vollständige Sammlung ist ausdrücklich kein bestandener
Volltest. Auch die kleine synthetische Vier-Test-CI-Referenz ist kein echter
GitHub-Lauf. Bundle 011 fordert parallele Volltests in GitHub an; Bundle 012
behält parallel plus seriell und Vergleich. Aus dem erfolgreichen lokalen
Apply oder Push darf kein erfolgreicher GitHub-Lauf abgeleitet werden.
