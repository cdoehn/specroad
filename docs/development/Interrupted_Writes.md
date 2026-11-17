# Unterbrochene Writes und separater Git-Wiederanlauf

Aktueller Vertrag nach RECOVERY-REMOVAL-006, Spezifikation 10.7 sowie Anhang
C/N/P; umgesetzt in 18.s–18.x. Die frühere Produkt-Recovery und ausführbare
Restore-Work-Aufträge sind entfernt. Historische Implementierungsnotizen,
Audits und Originaldaten bleiben Nachweise ihres damaligen Zustands.

## Unterbrochener Root

Vor Modellnutzung prüft der normale Aufruf aktuelle Lock-/Schreibmarker.
Ein aktiver Writer blockiert konkurrierende Fachoperationen; beschädigte oder
unklare Schutzdaten bleiben gesperrt. Das gilt auch für Read-only-, Plan- und
Dry-run-Aufrufe. Begrenzte schreibfreie Betriebsdiagnose ist keine Freigabe.
Weder passende Zielbytes noch fehlende PID-Sicht beweisen einen Abschluss.

Nur der tatsächlich noch laufende normale Writer darf nach vollständiger
Rückprüfung aller Ziele und dauerhaft gespeicherten Originalreceipts seinen
eigenen Marker entfernen. Nach Abbruch gibt es kein automatisches Verwerfen,
Zurückrollen, Fertigstellen, Rekonstruieren fehlender Belege oder Entsperren.
Auch `recover_project_lock` übernimmt keinen Owner: der Kompatibilitätseingang
prüft den Lockvertrag und verweigert das Entfernen. Aktuelle Konfigurationen
weisen das entfernte Feld `transaction_policy.auto_recover` ausdrücklich ab.

## Vom Nutzer gewählter vollständiger Git-Stand

Der Nutzer erhält den beschädigten Root einschließlich fremder Dateien und
aller tatsächlichen Zwischenstände. Er wählt einen bekannt gültigen vollständigen
Git-Stand und erstellt einen frischen separaten Checkout. SpecRoad führt dafür
keinen Git-Befehl aus und setzt den beschädigten Root nicht zurück.

Vor einer neuen Fachoperation muss der neue Root die normalen nativen
Validierungen bestehen. Konfiguration, Profile, Ressourcen, Anhänge, referenzierte
Archiv-/Legacy-Originale und fachlich benötigte Originalreceipts müssen vorhanden
sein. Ein Hash oder ein Git-Commitname ersetzt keinen Vollständigkeitsnachweis.
Fehlende erforderliche Belege werden abgewiesen und niemals nachgebildet.

Ein vollständig gültiger Stand ohne optionale alte Requesthistorie darf eine
neue lokale Historie mit einem tatsächlich neuen Fachauftrag beginnen. Nach
absichtlichem Git-Rücksetzen wird kein Exactly-once-Schutz über die entfernte
Historie hinweg behauptet. Alte Abschlussbelege bleiben historische Originale;
sie sind kein Nachweis unveränderter aktueller Zielbytes und keine neue Freigabe.

## Erhaltene Vorbereitung und Bibliotheksschnittstellen

Normale Migration-/Merge-Vorbereitung, Checkpoints, Workpaketexport/-restore
und abgeschlossene Ergebnislieferung bleiben erhalten. `work restore` liest
ein Workpaket; es repariert kein beschädigtes Projekt. Alte ausführbare
Restore-Kennungen werden vor Zielallokation abgewiesen. Aktuelle Hostprovider
verwenden `QualificationServices`, etwa dessen `proposal_inputs`-Provider,
und eine frisch erteilte fachliche `PublicationAuthority`.

Native lesende Original-, Journal- und Abschlusscodecs bleiben erhalten, soweit
aktuelle Bundle-/Legacy-/Qualifikationspfade sie benötigen. Ihre historische
Formatidentität ist keine aktive Reparaturfunktion. Die eigenständige
SpecRoad-Control-Recovery wird durch den Produktrückbau nicht verändert.

## Nachweise

Die Pflichtauswahl der 18.w-/18.x-Stages bindet normale Writer-/Work-/Transport-
Regressionen, echte Unterbrechungen und lokale Git-Checkouts in isolierten
Apply-Testverzeichnissen. Neue Fälle liegen in `test_recovery_removal*.py`,
`test_git_restart*.py` und `test_retired_formats.py`. Modul-/PYZ-Verträge werden
als Verhalten geprüft. Dev führt nur statische Prüfung und reine Collection
aus. Jede Stage benötigt ihr eigenes erfolgreiches Apply-Gate; weitergehende
Plattform-/Vollsuite-/Releasebelege bleiben in M20 offen.
