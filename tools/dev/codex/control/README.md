# SpecRoad Codex Control

Control gehört zu `tools/dev/codex/control/`; die Tests zu
`tests/codex_control_tests/`. Es ist ein Entwicklungswerkzeug und wird nicht
mit dem SpecRoad-Core-Paket ausgeliefert. Die bisherige Fachspezifikation
liegt in `spec/SPECIFICATION.md`, ihre Historie in `planning/commit-plan.md`.
Aktuell gelten SpecRoad-Spezifikation 2.5.4 und der gemeinsame Implementierungsplan.

Aufruf aus dem Repository: `python3 -B tools/dev/codex/control/control status`.
Quellcode wird über das gemeinsame SpecRoad-PatchHarbor-Apply entwickelt.
Dev führt keine Testkörper aus; jede W/R/C-Stage hat ihr eigenes reguläres Gate.

## Entwicklungsaufträge ausschließlich über Control

Nutzerauftrag vom 5. November 2026, OFF-PLAN TEST-SPEED-CONTROL-599:
Die bisherigen manuellen Chat-Kurzbefehle `S` und `N` sind aufgehoben.
Control beauftragt jeweils genau einen vollständig gebundenen Dev-Durchlauf;
Dev veröffentlicht höchstens eine ZIP und beendet den Turn. Watcher/Apply
übernehmen Ausführung und Tests; Control beobachtet das Result und veranlasst
bei freigegebener Automatik den nächsten Auftrag. Dev wartet nicht selbst.
Start/Fortsetzen/Pause/Stopp erfolgen über ausdrückliche Control-Bedienaktionen.
Manuelle Entwicklungsaufträge bleiben bei pausierter Automatik und ohne
aktiven Control-Auftrag möglich; alle Bindungs- und Apply-Regeln gelten weiter.

Die lokale Dev-AGENTS.md wird am Entwicklungsort bereinigt und gehört nicht
in Produkt-Payloads. Historische Prompt-/Auftragsbytes, alte Nachweise und
Recoverybindungen bleiben unverändert. Ein dort vorhandenes `N` ist keine
aktuelle Definition eines Chat-Kurzbefehls. Die Testrotation N=3 bleibt
unverändert. Dieses Bundle startet oder installiert keinen Dienst.

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

## Klärung für eine alte Automationskette ausdrücklich freigeben

Neue freigegebene Aufträge verwenden Vertrag 4: falls notwendig ein optionaler
Klärungscommit vor echten Plancommits in derselben ZIP. Die Grenzen aus
SPECROAD-DECISION-1 gelten. Drei Restplätze allein erteilen keine Befugnis.

Nach erfolgreichem Apply und Installation dieser Version kann der Betreiber
für einen noch nicht beanspruchten direkten sauberen Nachfolger ausdrücklich
freigeben (Platzhalter durch die geprüften Werte ersetzen):

```sh
python3 -B tools/dev/codex/control/control authorize-clarification \
  --source-sha256 <SHA256_DES_BISHERIGEN_RESULTS> \
  --result /absoluter/pfad/zum/erfolgreichen/Nachfolge-Result.zip \
  --reason "Optionale Detailklärung für künftige Aufträge freigegeben"
```

Der Dienst muss für diesen Offline-Bedienbefehl gestoppt sein. Eine aktive
Chatnachricht verhindert nur die spätere Übernahme, nicht das Vormerken.
`status` zeigt `clarification_authorization` an. Der Befehl startet nichts,
setzt keine Pause zurück und ändert noch keinen laufenden Auftrag. Nach
separatem Start/Resume wartet der Worker auf den freien Thread und übernimmt
den gebundenen neuen Auftrag atomar. Alter Vertrag, Fehler und Versuche sowie
das vorhandene Restbudget bleiben erhalten. Installation/Recovery allein
führen diese Freigabe nie aus. Eine identische Wiederholung ist idempotent.

Abgelehnt werden insbesondere fehlendes/erschöpftes Budget, offene Klärungs-
fortsetzung, unvollständiger Apply, unklare Paketfolge, bereits beanspruchte
Ziel-Results und geänderte Nachweise. Alte Verträge ohne gespeichertes Budget
benötigen weiterhin einen regulären belegten Umsetzungsabschluss. Eine
Spezifikationsklärung wird durch den Bedienbefehl weder ausgeführt noch als
Produktfortschritt verbucht. Maßgeblich: SpecRoad-Spezifikation 2.4.3.2.

## Startwartezeit

`start` startet den installierten Dienst. Die Entwicklungsautomatik wartet
danach standardmäßig 60 Sekunden; Status, Pause und Stop reagieren sofort.
Unter `[automation]` in der externen config.toml ist
`start_delay_seconds = 60` konfigurierbar (0 bis 86400, Bruchteile erlaubt).
Null bedeutet ausdrücklich ohne Startwartezeit. Bestehende Dateien ohne
diesen Eintrag verwenden 60, ohne beim Lesen geändert zu werden. Eine neue
Einstellung gilt beim nächsten ausdrücklich gestarteten Worker. Ein laufender
Dienst wird durch erneutes `start` nicht verzögert oder neu gestartet.
`status` liefert `start_delay.seconds`, `remaining_seconds` und `waiting`.
Pause/Resume verkürzen die Frist nicht; eine bereits abgelaufene Frist beginnt
durch Resume nicht erneut. Der Stop wartet nicht auf die Frist. Thread-,
Speicher-, Result- und Budgetprüfungen bleiben zusätzlich wirksam.

## Korrekturen mit unverändertem Repositoryzustand

Control ordnet kanonische v2-Pakete zusätzlich über die exakte Quell-Result-SHA
zu. Unterschiedliche Result-ZIPs mit denselben vier Zustandswerten erzeugen
damit keine falsche `ambiguous_patch`-Blockade. Der passende native Quellbeleg
muss im Exchange oder Archiv vorhanden sein. Fehlender/widersprüchlicher
Beleg sperrt mit `patch_source_unproven`; zwei Pakete für dasselbe Result
bleiben mehrdeutig. Alte Pakete und die History bleiben erhalten. Die Auswahl
ändert keine Freigabe und erneuert kein Budget unbekannter manueller Übergaben.
