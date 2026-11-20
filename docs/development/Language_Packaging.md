# Optionale Sprachdistribution entwickeln

`specroad[language]` deklariert py3langid 0.4.0 und die nach Python-Minor
getrennten NumPy-Pins. Der Core selbst hat weiterhin keine Zusatzabhängigkeit.
Das ist ein Entwicklungsstand, keine Behauptung eines veröffentlichten Releases.

Offlinepaket aus einem ausdrücklich vorbereiteten Wheelverzeichnis bauen:

```sh
python3 tools/build_language.py --python 3.14 --wheelhouse WHEELS --output language-cp314.zip
```

Für 3.10–3.14 jeweils separat aufrufen. Fehlende oder abweichende Originalwheels
werden abgelehnt, niemals nachgeladen. Die genauen Dateinamen, Hashes und
manylinux-Mindeststände stehen in `tools/language_packaging/inventory.py`.
Wheels und ihre vollständigen Lizenzen bleiben im Paket; ein Paket enthält
nur die gewählte NumPy-ABI. Modell und Adapter sind separat inventarisiert.
Bestehende Ausgabeziele werden nicht ersetzt.

Ab 19.k.R prüft `language_packaging.verify.verify_package` Integrität;
`probe_package(path, interpreter, expected_core_sha256=...)` prüft ausdrücklich
einen installierten Interpreter gegen einen unabhängig bekannten Core-Buildhash.
`probe_matrix` benötigt fünf explizite Paket- und Interpreterpfade für 3.10–3.14
und startet je ABI einen separaten Prozess. Keine automatische Installation,
kein Download, keine Auswahl aus einem Fachprojekt. Diese Prüfungen sind echte
Verhaltensausführung und unterliegen den geltenden Apply-/manuellen Testregeln.
Import und eine NumPy-Operation sind noch keine Sprach- oder Releaseabnahme.
Die vollständigen Sprach-/Ressourcen-/Offlineabnahmen bleiben 19.n, 19.y und 20.k.

## Echte Referenzintegration auf fünf Runtimes

Die Pflichtfälle in `tests/test_analyzer_reference_matrix.py` benötigen vor dem
Teststart fünf explizit vorbereitete Standard-CPython-Interpreter für Linux
x86_64 (3.10–3.14) sowie die Originalwheels aller fünf ABIs. Diese Dateien sind
Testabhängigkeiten außerhalb des Produkt-Payloads. Der Test baut sein eigenes
Offlinepaket aus dem tatsächlich geprüften Core-Quellstand. Er lädt das echte
Originalmodell, prüft vollständige Ranglisten und die Fehlergrenzen. Fehlende
Runtimes oder Artefakte sind Fehler; kein Skip, Nachladen oder ABI-Ersatz.

Nach ausdrücklicher Vorbereitung vorhandener uv-Interpreter kann der Betreiber
eine lokale, exklusive Auswahl erzeugen:

```sh
python3 tools/prepare_language_tests.py --python-directory PYTHON_DIRECTORY \
  --wheelhouse WHEELS --output RUNTIME_MANIFEST
```

Der Befehl prüft Interpreteridentität und Originalwheels, installiert nichts
und führt keine Produkttests aus. Er erhält bestehende Ausgabeziele. Die
Auswahl bindet aufgelöste absolute Interpreterpfade, Versionen und SHA-256.
`SPECROAD_LANGUAGE_TEST_RUNTIMES` wählt die Datei; ohne diese Variable wird
`~/.config/specroad/language-test-runtimes.json` verwendet. Jeder Testhost braucht
seine eigene gültige Auswahl. Keine lokalen Pfade oder Konfigurationen in
Produktbundles kopieren. Die manuelle CI bereitet ihre privaten Abhängigkeiten
vor dem Testlauf separat vor; dieser Workflow startet weiterhin ausschließlich
per Nutzeraktion.

Eine vorbereitete Matrix oder ein gebautes Paket ist kein Laufnachweis.
Erst die bestandenen fünf parametrisierten Apply-/CI-Fälle belegen die echte
Integration auf den dabei gebundenen Versionen. Auch diese synthetischen
Integrationstexte ersetzen weder den menschlich geprüften Sprachkorpus noch
die spätere Releaseabnahme.
