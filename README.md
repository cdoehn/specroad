# SpecRoad

SpecRoad ist eine lokale, Git-native Workbench für Spezifikationen,
Anforderungen und deren Nachweise. Die Implementierung läuft nach dem
[Implementierungsplan](docs/implementation/SpecRoad_Implementierungsplan.md);
die [Produktspezifikation](docs/specification/SpecRoad_Spezifikation.md)
beschreibt das verbindliche Sollverhalten.

## Lokale Entwicklungsumgebung

Voraussetzungen auf dem Laptop: Git, ein vorhandenes Python ab 3.10 und
[uv](https://docs.astral.sh/uv/getting-started/installation/). Git und uv
sind externe Werkzeuge und keine Python-Pakete in der Dev-Abhängigkeitsgruppe.
Der Aufbau benötigt Netzwerkzugriff, soweit Downloads nicht bereits im Cache
liegen. Im Repository reicht anschließend:

```bash
python3 tools/setup_dev.py
```

Der Befehl installiert die in `.python-versions` aufgeführten Interpreter
3.10, 3.11, 3.12, 3.13 und 3.14 über uv. Die Datei beginnt mit 3.14,
damit uv auch ohne ausdrückliche Versionsangabe 3.14 auswählt. Die zusätzlichen Versionen liegen im
uv-Benutzerverzeichnis, nicht gemeinsam in `.venv`. Anschließend erzeugt er
eine `.venv` mit Python **3.14** oder verwendet eine bereits passende Umgebung.
Er installiert SpecRoad editierbar und die Gruppe `dev` aus `pyproject.toml`
(pytest und pytest-xdist), mit `--link-mode copy`. Wiederholte Aufrufe sind
möglich; eine unpassende oder defekte vorhandene `.venv` wird mit einer
Fehlermeldung erhalten und muss bewusst separat geklärt werden.

uv wird über `PATH` gesucht; auf dem Laptop wird außerdem `~/.local/bin/uv`
gefunden. Der Aufbau verändert weder Shell-Startdateien noch den systemweiten
`python3`-Standard. Er setzt kein `--default`, startet keine Tests und legt
keine lokale Testmatrix an. Für normale lokale Entwicklung und Tests bleibt
die Projektumgebung auf Python 3.14. Die vollständige Versionsmatrix wird
über den manuellen GitHub-CI-Workflow geprüft.

Dev-Chats können bei Bedarf einzelne andere Interpreter direkt verwenden,
ohne die Projektumgebung umzubauen. Falls `uv` nicht auf `PATH` liegt,
verwende dafür `~/.local/bin/uv`:

```bash
uv python list --only-installed
uv python find --managed-python --no-project 3.11
```

Der zweite Befehl gibt den ausführbaren Interpreterpfad aus. Beispielsweise
lässt sich ein bewusst gewähltes Skript ohne Projekt-Synchronisierung so
ausführen:

```bash
python311="$(uv python find --managed-python --no-project 3.11)"
"$python311" mein_skript.py
```

Die zusätzlichen Interpreter erhalten dadurch keine eigene Kopie der
Dev-Pakete; diese liegen in der regulären `.venv` für Python 3.14. Gezielte
Tests verwenden weiterhin den vorhandenen parallelen Starter aus
[Testing.md](docs/development/Testing.md). Die Einrichtung ändert weder
Testauswahl und Apply-Rotation noch CI, Control oder den PatchHarbor-Watcher.
