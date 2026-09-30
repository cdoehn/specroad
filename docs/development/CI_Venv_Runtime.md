# Python-3.10-Venv-Start auf dem verschobenen Toolcache

OFF-PLAN `CI-VENV-RUNTIME`, Bundle 041. Produktstand bleibt 225/885.

## Nachgewiesener Ausgangsfehler

Result `specroad_Result_161115_0930_475daf.zip`, Commit
`c254fb1fb060b8ef824c4ec17aa24ec52ca67da5`, Run 36742807853, Attempt 1:
`CoreRobustnessTests.test_unactivated_virtual_environment_without_pip`
scheitert unter CPython 3.10.21 parallel und seriell vor Ausführung des
SpecRoad-Codes an der fehlenden Standardbibliothek (`encodings`). Der verwendete
Interpreter liegt unter dem eigenen Runner-Toolcache, die fehlgeschlagene Suche
landet hingegen unter dem einkompilierten `/opt/hostedtoolcache/...`.
CPython 3.11–3.14 bestehen beide Vollsuiten samt Vergleich. Das ist kein Beleg
für einen OOM-Abbruch und kein erneut fehlender `LD_LIBRARY_PATH`.

## Begrenzte Korrektur

Der Test erzeugte mit dem API-Default von `venv.EnvBuilder` eine Interpreterkopie.
Die Testfixture verwendet jetzt wie die normale POSIX-venv-CLI symbolische
Verknüpfungen; Windows behält die normalen Redirector-Dateien. Dadurch bleibt
beim verschachtelten Erzeugen die Verbindung zum tatsächlichen Basisinterpreter
erhalten, statt sich auf den einkompilierten Installationspräfix zu verlassen.
Die Erzeugung erfolgt frisch und ohne pip, Paketinstallation oder Aktivierung.

`run_core` und sein `-I -S -B` bleiben unverändert. Insbesondere wird `site` nicht
zugelassen, `PYTHONHOME` nicht gesetzt und kein beliebiger Elternprozesspfad
übernommen. Produktcode, bisherige Testidentität und Bibliothekspfad-Allowlist
bleiben unverändert. Es gibt keinen Skip, Versionsausschluss oder Retry.

Die Regressionen prüfen echte Interpreterstarts, die Identität der Basis-
Standardbibliothek, verschachtelte Environments, nicht vorhandenes pip/pytest
im neuen Environment und die Nichtausführung von Projekt-/site-Hooks. Der
unabhängige venv-Identitätsprobeprozess darf site laden; der SpecRoad-Testprozess
bleibt strikt ohne site. Getestet wird Verhalten, kein Konsolenwortlaut.

## Nachweisgrenze

Die Chat-Prüfumgebung bietet nur CPython 3.13.5. Die gezielten Tests wurden dort
vorbereitet und ausgeführt; ein erneuter echter 3.10.21-Lauf auf dem Hetzner
ist damit nicht vorweggenommen. Der nächste bewusst manuelle Full-Run muss
die Korrektur auf allen fünf unterstützten Versionen bestätigen.

## Primärquellen

- Python 3.10 venv-API/CLI: https://docs.python.org/3.10/library/venv.html
- CPython 3.10.21 `Modules/getpath.c`, insbesondere `calculate_argv0_path`,
  `calculate_read_pyenv` und `calculate_path`:
  https://github.com/python/cpython/blob/v3.10.21/Modules/getpath.c
- CPython 3.10.21 `Lib/venv/__init__.py`, `ensure_directories` und
  `create_configuration`:
  https://github.com/python/cpython/blob/v3.10.21/Lib/venv/__init__.py
