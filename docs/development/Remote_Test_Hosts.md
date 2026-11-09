# Apply-Tests auf mehreren Hosts

Ausdrücklicher Nutzerauftrag REMOTE-TEST-HOSTS vom 8. November 2026,
[normativer Vertrag 2.5.5](../specification/SpecRoad_Spezifikation.md#255-verteilte-apply-tests--remote-test-hosts).
Diese Werkzeuge gehören zur Entwicklung. Sie starten weder CI noch Control
und verändern keine laufenden Apply-Bundles. Ohne lokale Hostkonfiguration
arbeitet der bestehende lokale Runner weiter.

## Lokale Konfiguration

Die Datei `~/.config/specroad/test-hosts.json` bleibt außerhalb des Repositorys.
Alternativ `SPECROAD_TEST_HOSTS` oder `run_apply_tests.py --hosts DATEI`;
`--local` schaltet für einen Lauf auf den bisherigen lokalen Runner zurück.
Die folgenden Werte sind ausschließlich erfundene Beispiele:

```json
{
  "format_version": 1,
  "hosts": [
    {"name": "laptop", "ssh": null, "directory": "/home/tester/test-host", "workers": 6, "speed": 1.0},
    {"name": "server", "ssh": "hetzner-tests", "directory": "/home/tester/test-host", "workers": 8, "speed": 2.0, "persist": 1800}
  ]
}
```

`ssh` bezeichnet einen vorhandenen Alias aus der OpenSSH-Konfiguration.
`workers` begrenzt die Hostbelegung, `speed` schätzt die relative Leistung
eines einzelnen Workers: 2 bedeutet ungefähr doppelt so schnell wie 1.
Der Wert ist eine erste Schätzung, kein Benchmark. Aktuelle Messungen pro
Host/Test/Umgebung gehen vor; Beobachtungen während des Laufs passen nur die
Verteilungsschätzung an. Der normative Laufzeitfilter benutzt weiter seine
unveränderten Rohmesswerte. Beide Apply-Linien sollen denselben Hostnamen und
dieselbe Slotgrenze für denselben Remote-Benutzer verwenden.

## Einrichtung und Kontrolle

Alle Befehle mit dem Python der tatsächlichen Apply-Umgebung aufrufen:

```sh
.venv/bin/python tools/test-hosts list
.venv/bin/python tools/test-hosts connect server
.venv/bin/python tools/test-hosts prepare server
.venv/bin/python tools/test-hosts --json check
.venv/bin/python tools/test-hosts status
.venv/bin/python tools/test-hosts disconnect server
```

`prepare` ist die ausdrücklich auszulösende Installationsaktion. Sie installiert
auf Ubuntu/Debian fehlende Betriebssystempakete über den nativen sudo-Dialog,
überträgt die lokale uv-Binärdatei und erstellt eine getrennte, durch den
Umgebungshash adressierte Python-Umgebung. `--uv PFAD` wählt die Binärdatei.
CPython einschließlich Microversion, ABI, Architektur und Python-Paketversionen
sowie SQLite-, OpenSSL- und zlib-Laufzeit müssen zur ausführenden Apply-Umgebung passen. Eine nicht verfügbare exakte
Version wird als Fehler gemeldet; kein stiller Wechsel auf System-Python.
Die System-Python-Installation wird nicht ersetzt. Pakete werden ausschließlich
als Wheels installiert. Ein erneuter Aufruf bringt dieselbe eigene Umgebung
auf denselben Paketstand und prüft sie erneut.

`check` installiert nichts und führt keine Tests aus. Ein fehlender SSH-Zugang,
eine andere Umgebung oder fehlende Werkzeuge verhindern die Verwendung im
Pool. Der erste Profilumfang unterstützt CPython/Linux mit gleicher Architektur.
Die Einrichtung braucht Netzwerkzugriff und gegebenenfalls sudo; der spätere
Testlauf benötigt weder sudo noch Installationen oder interaktive Passwörter.
`prepare --non-interactive` erlaubt ausschließlich bereits verfügbare sudo-Rechte;
zusammen mit `--json` entsteht eine maschinenlesbare Antwort ohne Dialogausgaben.

OpenSSH übernimmt Passphrase, Agent und gegebenenfalls Askpass. SpecRoad hält
einen privaten Multiplex-Socket mit konfigurierbarer **Leerlaufzeit** `persist`
(Standard 1800 Sekunden). Aktive Verbindungen laufen weiter. Ein Prozessabbruch,
Hostneustart oder eine abgelaufene Sitzung kann erneut Anmeldung verlangen.
Für tagelangen unbeaufsichtigten Betrieb muss die Administration einen dafür
geeigneten SSH-Zugang einrichten, etwa einen eingeschränkten separaten Testbenutzer
mit eigenem Schlüssel. SpecRoad legt keine privaten Schlüssel, Passwortdateien
oder Zugangsdaten an; bestehende Agent-/SSH-Einstellungen bleiben zuständig.

## Ausführung und Belege

Vor dem Teststart werden alle gewählten Hosts geprüft. Der Runner kopiert die
aktuellen Dateien der jeweiligen W/R/C-Stage in ein eigenes Runverzeichnis und
prüft vollständige Dateiliste, Bytes und Modi. Auch noch uncommittierte Dateien
dieses Zustands zählen. Die erlaubten Eingaben sind `src`, `tests`, `tools`,
`verification`, `docs`, `.github` sowie ausdrücklich benannte Rootdateien.
`.git`, lokale Arbeitsnotizen, Umgebungen, Buildausgaben und Zugangsdaten werden
nicht übertragen. Zusätzliche Testeingaben müssen zuerst in den Vertrag und
die Snapshot-Auswahl aufgenommen werden. Der Quellstand wird vor und nach dem
Lauf geprüft. Remote-Arbeitskopien bleiben zur Diagnose erhalten; sie sind keine
Git-Branches und kein neuer Apply-Result-Ersatz.

pytest-xdist bleibt für Worker, Collection und Testprotokoll zuständig. Ein
gezielter Scheduler verteilt längste bekannte Tests zuerst nach geschätzter
Fertigstellungszeit je Host, untersucht unbekannte Tests früh auf schnellen
Slots und behält kurze Tests zum Auffüllen. Kleine Warteschlangen berücksichtigen
pytest-`nextitem`. Ein langsamer Host darf ungenutzt bleiben. Laufende Tests werden
nicht verschoben oder spekulativ doppelt gestartet; ein ausgefallener Worker
erzeugt einen fehlerhaften Gate-Ausgang. Es gibt keine Laufzeitzusage.

Worker halten Betriebssystemsperren für ihre gesamte Lebensdauer. Derselbe
Benutzer teilt `~/.local/state/specroad/test-host-slots` beziehungsweise den
entsprechenden `XDG_STATE_HOME`-Pfad über beide Apply-Linien. Belegte Slots werden
nicht überschrieben. Eine Änderung der Hostgrenze braucht freie Slots. Diese
Grenze umfasst konfigurierte Pool-Worker dieses Benutzers; fremde Programme und
andere Benutzer werden dadurch nicht begrenzt. CPU-Affinität/cgroup-Quoten sowie
`--worker-limit` begrenzen zusätzlich. Nice mindestens +10 und I/O-Klasse 2 mit
Priorität 7 werden vererbt; verschachtelte Testläufe bleiben auf einen Worker
begrenzt. CPU-/I/O-Priorität ist keine feste Ressourcenreservierung.

Die SQLite-Datenbank bleibt ausschließlich beim Koordinator der jeweiligen
Apply-Linie. Vor einem Testkörper bestätigt der Koordinator den dauerhaft
gespeicherten Start; jede native Phase wird ebenfalls vor ihrer Bestätigung
gespeichert. Fehlende Bestätigungen, Verbindungsabbrüche, Quellenwechsel oder
unvollständige Phasen erlauben keinen Commit. Bereits vorhandene Datensätze
werden weder gelöscht noch nachträglich einem Host zugeschrieben.

`test-monitor` zeigt für neue Pool-Messungen Host, Worker und alle drei Phasen;
die Suche umfasst auch den Hostnamen. `--once --json` enthält `host` und
`environment_sha256`. Historische Datensätze ohne Hostbeleg bleiben `null`/`—`.
Apply-Bericht v5 und Auswahlbindung v6 ergänzen die vollständigen Hostbelege.
Die bestehende N=3-Rotation, aktuelle Fünftelfilterung und ungefilterte
Pflichtauswahl bleiben gleich; jede W/R/C-Stage erhält ihr eigenes Gate.

Implementierungsgrundlagen: [xdist-Remote/Proxies](https://pytest-xdist.readthedocs.io/en/stable/remote.html),
[xdist-Protokoll](https://pytest-xdist.readthedocs.io/en/stable/how-it-works.html),
[uv CLI](https://docs.astral.sh/uv/reference/cli/),
[OpenSSH ControlPersist](https://man.openbsd.org/ssh_config#ControlPersist).
Das Remoteprotokoll ist zunächst ausdrücklich an xdist 3.8.0 und execnet 2.1.2
gebunden. Versionswechsel brauchen erneute native Integrationsabnahme.

Die Hostkonto-Identität kombiniert die gehashte Maschinenkennung mit der
Benutzer-ID. Gleiche Rechnernamen sind dadurch kein Identitätsbeweis; doppelte
Aliase desselben Hostkontos werden abgewiesen. Große Manifeste werden gestreamt.
