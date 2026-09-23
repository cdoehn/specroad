# CI-Payload-Identität: Korrektur 4.j.W-FIX1 (Bundle 018)

## Geprüfte Eingaben und tatsächlicher Zustand

- Result: `specroad_Result_181711_0923_6458d6.zip`, SHA-256 `04951d8c72daa24f24b7b41a0a09f4afcd4d007dd0d1e86914f355ca566f8679`.
- CI-Archiv: `logs_97218498080.zip`, SHA-256 `580491b5a626b471f058fb12f1db028190f60f95d4834069d747c18d95a8f727`.
- Gemeinsamer geprüfter Commit: `444708919d391eba123c1f49871133eacf0349b4`.
- GitHub-Workflow-Run: `35902230403`, Bundle 017, Modus `parallel`.
- Das Result enthält einen erfolgreichen lokalen Apply, sauberen Stand und
  erfolgreichen Push auf dev. Der Plan steht bei 165/885 nach 4.m.C.
- Der verfügbare GitHub-Connector liefert 404. Die folgenden CI-Aussagen stammen
  aus allen fünf vollständigen Joblogs des hochgeladenen Archivs, nicht aus
  einer geratenen aktuellen GitHub-Abfrage.

## Befund

Alle fünf Jobs für CPython 3.10, 3.11, 3.12, 3.13 und 3.14 sammeln 3172 Tests
und enden mit genau einem Fehler und 3171 bestandenen Tests. Der Select-Job
weist denselben Commit und die richtige Bundle-Nummer 17 aus. Katalogprüfung
und Teststart funktionieren; es ist kein früherer xdist-Startfehler.

Einziger fehlgeschlagener Test in jeder Version:

`tests/test_identity.py::IdentityRobustnessTests::test_payload_hash_binds_program_bytes_not_paths_or_timestamps`

Quellen im Archiv: die Dateien `0_CPython 3.14 _ parallel.txt`,
`1_CPython 3.12 _ parallel.txt`, `2_CPython 3.11 _ parallel.txt`,
`3_CPython 3.10 _ parallel.txt`, `4_CPython 3.13 _ parallel.txt`, jeweils
Abschnitt `FAILURES` und `short test summary info`. Die zugeordneten separaten
Schrittlogs enthalten dieselben Meldungen und sind keine zusätzlichen Läufe.
Die JSON-Auswertung meldet zwei fehlgeschlagene Requirements, weil dieser eine
reale Test SR-TC-0194 und SR-TC-0392 zugeordnet ist; es sind nicht zwei Testfehler.

Der Builder liefert bereits die vier Profilressourcen aus und bindet ihre
Bytes korrekt in den Buildhash ein:

- `profile_data/profiles.json`
- `profile_data/core.json`
- `profile_data/software-de.json`
- `profile_data/software-en.json`

Die unabhängige Testberechnung enthielt nur Python-Quellen und die älteren
Sprachressourcen. Damit berechnete sie den Hash einer anderen Dateimenge.
Die Integration der vier Dateien wurde im aufbewahrten Paket für 4.j.W
bestätigt (`specroad_Patch_190950_0922_68c9bc.zip`, Operation tools/build_core.py).
Der Fix wird deshalb diesem Plan-Commit zugeordnet, ohne Produktfortschritt
nachträglich zu erhöhen oder vorhandene Commits umzuschreiben.

Beide Hashes des unveränderten Ausgangszustands konnten lokal reproduziert
werden: tatsächlicher Build `e672b40b01fa8a15cecf372844964dcce03f663745c54630046a1c961c607d92`,
unvollständiger Testvergleich `0c4b818e57087019b50d55175c1bb808595e8b348a36f169d9769e0709d3d806`.
Sie werden nicht als neue feste Sollwerte in Tests eingetragen.

## Reparatur und Schutzwirkung

Der ursprüngliche Test bleibt unter derselben Kennung aktiv. Ein unabhängiger
Testhelfer beschreibt alle 17 mitgelieferten Datendateien zusätzlich zu den
Python-Quellen. Er importiert weder die Ressourcen-Allowlist noch die Hashfunktion
des Builders. Erwartungswerte werden aus den tatsächlichen Quellbytes mit dem
bekannten Hashvertrag berechnet. Kein Hardcoding des CI-Hashes, kein Entfernen
von Ressourcen aus der Produktion und keine aufgeweichte Assertion.

Zwölf neue Verhaltenstests prüfen die vollständige Dateimenge und ihre Bytes
in Modultree UND Zipapp, Mutationen jeder der vier Profil- und 13 Sprachdateien,
Änderungen gleicher Länge bei zurückgesetztem mtime, Rohbyteänderungen bei
gleichem JSON-Wert, Unabhängigkeit von absoluten Pfaden/Zeitstempeln und
Bindung relativer Dateinamen. Weitere Prüfungen verhindern die Aufnahme
unregistrierter Dateien und Cacheinhalte, prüfen den Ausschluss des abgeleiteten
_build-Records und erhalten die ursprünglichen Quellbytes. Fehlende Ressourcen
werden vom Testorakel nicht als kleinere erfolgreiche Sollmenge akzeptiert.
Explizit unvollständige oder beschädigte Vergleichsmanifeste müssen vom
beobachteten tatsächlichen Buildhash abweichen.

Unter `src/`, im Builder, in den Abhängigkeiten und im Workflow ändern sich
keine Bytes. Die zwei betroffenen Testmanifeste erhalten die neuen echten
Testkennungen, behalten aber `implementation_status: partial` und ihre offenen
Produktabnahmen. Maschinenlesbare Hash-/Lieferdaten sind fachliche Verträge;
keine Tests auf Farben, Layout, Konsolenformulierungen oder Dokumentation.

## Prüfablauf und Nachweisgrenze

Vor der Korrektur wurde ausschließlich tests/test_identity.py parallel geprüft:
genau derselbe Fehler, 17 andere Tests bestanden. Der lokale Fix-Gate umfasst
nur explizite betroffene Testdateien mit vier xdist-Workern und den vorhandenen
vollständigen Katalog-Sammelcheck. Keine lokale Vollsuite, kein serieller
Produkttest und keine neuen Timeout-Grenzen. Der finale Commit von Bundle 018
fordert die volle parallele GitHub-Matrix an; Bundle 020 bleibt der nächste
reguläre Doppelmodus mit serieller Referenz und Vergleich.

Die getrennte Vorprüfung nutzt CPython 3.13.5, pytest 9.0.2 und bereits
bereitgestellte Upstream-Testbuilds von xdist/execnet. Sie verändert weder die
Release-Abhängigkeiten des Projekts noch die Pixel-Umgebung. Ein dortiger Apply
und die erneut grüne CI-Matrix können erst durch ihre wirklichen Läufe bestätigt
werden. Die Fehlerprotokolle des alten CI-Laufs werden nicht umgedeutet.

## Weiterarbeit

Ein einziges separates Korrekturbundle mit einem Fix-Commit. Produktzähler
unverändert 165/885, nächster geplanter Commit 4.n.W. Erst die Korrektur-CI
abnehmen, dann die containerbezogene Sprachmischung implementieren.
Bei künftigen Änderungen an Lieferressourcen, Profilen, Sprachdaten oder
Buildregeln gehören tests/test_identity.py und tests/test_payload_identity.py
zwingend zur lokalen Auswahl, zusätzlich zu den jeweiligen Fachtests.
