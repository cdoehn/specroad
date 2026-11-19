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
