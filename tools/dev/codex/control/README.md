# SpecRoad Codex Control

Control gehört zu `tools/dev/codex/control/`; die Tests zu
`tests/codex_control_tests/`. Es ist ein Entwicklungswerkzeug und wird nicht
mit dem SpecRoad-Core-Paket ausgeliefert. Die bisherige Fachspezifikation
liegt in `spec/SPECIFICATION.md`, ihre Historie in `planning/commit-plan.md`.
Aktuell gelten SpecRoad-Spezifikation 2.5.4 und der gemeinsame Implementierungsplan.

Aufruf aus dem Repository: `python3 -B tools/dev/codex/control/control status`.
Quellcode wird über das gemeinsame SpecRoad-PatchHarbor-Apply entwickelt.
Dev führt keine Testkörper aus; jede W/R/C-Stage hat ihr eigenes reguläres Gate.

## Datenverzeichnis und Installation

`SPECROAD_CONTROL_HOME` überschreibt den Standard
`~/.local/share/specroad/dev/codex/control/`. Alle Control-eigenen Konfigurationen,
History, Jobs, Sperren, Logs, Backups und Releasekopien liegen dort.
Die systemd-User-Registrierung bleibt am üblichen XDG-Konfigurationsort.
Codex-Anmeldung/Threads sowie Exchange gehören ihren bestehenden Werkzeugen.
`--config` darf nur eine Datei im neuen `config/`-Unterverzeichnis benennen.
Alte Konfigurationen werden nicht automatisch übernommen oder neu initialisiert.

Nach erfolgreichem Apply, bei kontrolliert gestopptem Control:

```
python3 -B tools/dev/codex/control/control migrate
python3 -B tools/dev/codex/control/control deploy --result /ABSOLUTES/ERFOLGREICHES/SpecRoad_Result.zip
```

Migration sichert zuerst einen geprüften privaten ZIP-Snapshot und erhält
Originale, Konfigurationsbytes, History, Pause und Budgets. `--legacy-config`
benennt bei Bedarf explizit die alte config.toml. Legacy-XDG-Pfade müssen zum
alten Dienst passen. Der neue Datenbaum darf keine abweichenden Daten enthalten.
Ein Abbruch sperrt Normalbetrieb; dieselbe Migration darf den belegten Rest
fertigstellen. Geänderte Quellen erfordern Diagnose, niemals Reset oder Seed.
Das vorhandene große Sicherheitsbackup und die alte Repositorykopie bleiben.

Deploy akzeptiert ausschließlich nativ verifizierte erfolgreiche saubere
SpecRoad-Apply-Results mit Abschlusscommit und integriertem Control-Code.
Es installiert `releases/<commit>/` und bindet die Unit an dessen geprüfte Bytes.
Ein expliziter Wiederaufruf mit demselben Result kann einen unterbrochenen
Releasewechsel abschließen. Ein Reloadfehler stellt die alte Zuordnung wieder
her oder lässt eine sichtbare Startsperre zurück. Deploy startet nichts.
Neue Einrichtung: erst `configure` mit explizitem Thread, Core und Seed-Result;
danach `deploy` mit dem erfolgreichen integrierten Result. Keine erratene ID.

`start`, `pause`, `resume`, `stop`, `recover`, `handover`, `reconcile-apply`,
`reconcile-blocked` und `disk-space` bleiben explizite Bedienaktionen.
Der Dienst wird nicht enabled und es gibt keine automatische Wiederaufnahme.
Die optionale Klärung nach Vertrag 4 und bestehende Grenzen bleiben erhalten.
Die aktive Speichergrenze wird unverändert übernommen, derzeit beauftragt 10 GB.

Ein Rückwechsel ist eine gesonderte Offline-Bedienaktion: gesicherte alte Unit
und ihren Datenstand prüfen, ohne jüngere History zu überschreiben. Alte und
neue Instanzen niemals parallel starten. Historische Pfade in Belegen bleiben
unverändert; Altverzeichnisse bis zur verifizierten Betriebsabnahme aufbewahren.

Der reguläre Control-Host verwendet Python 3.11 oder neuer. Für die gemeinsame
Python-3.10-Testmatrix enthält ausschließlich die Dev-Abhängigkeitsgruppe den
TOML-Backport tomli 2.2.1; das SpecRoad-Core-Paket bleibt abhängigkeitsfrei.
