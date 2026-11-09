# LOCAL-TEST-HISTORY — Hostzuordnung für lokale Testläufe

Ausdrücklicher Nutzerauftrag vom 9. November 2026: Auch normale lokale
Testläufe ohne Hostpool speichern künftig Rechnername und exakten
Umgebungsfingerabdruck. Die bereits additive Datenbankerweiterung wird genutzt;
alte Versuche bleiben unverändert und ohne erfundene Hostzuordnung.
Dies ist ein klar beauftragter OFF-PLAN-Umfang, keine delegierte Detailklärung.

Maßgeblich sind [Spec 2.5.5](../../specification/SpecRoad_Spezifikation.md#255-verteilte-apply-tests--remote-test-hosts)
und die [Laufzeitdokumentation](../../development/Remote_Test_Hosts.md#lokale-laufe-ohne-hostpool).

## Vollständige W/R/C-Abnahmen

- `LOCAL-TEST-HISTORY.W` — `OFF-PLAN: record host identity for ordinary local test runs (W)`:
  Lokale Controller/Worker verwenden für neue Versuche automatisch ihren
  beobachteten Rechnernamen und denselben Umgebungsfingerabdruck wie der Pool.
  Einmalige Ermittlung pro Prozess/Runner; Start und Hostzeile sind vor Setup
  gemeinsam dauerhaft gespeichert. Echte native Integration ohne Hostkonfiguration,
  unveränderte Phasen und erhaltene ältere beziehungsweise andere Hostmessungen.
- `LOCAL-TEST-HISTORY.R` — `OFF-PLAN: validate durable local host measurements (R)`:
  Fehlende/ungültige Identität und Erfassungsfehler verhindern einen Teststart.
  Schreibfehler hinterlassen keinen halben Versuch. Fehlende/veränderte Hostzeilen
  verhindern den erfolgreichen Laufnachweis. Collection erfasst keine Identität;
  Fehlerhistorie und explizite Poolzuordnungen bleiben erhalten.
- `LOCAL-TEST-HISTORY.C` — `OFF-PLAN: share local and remote environment identity (C)`:
  Gemeinsame unveränderte Umgebungsberechnung für lokale Historie und Remoteprobe.
  Bisherige Imports bleiben kompatibel; die Remoteprobe bleibt selbständig auf
  einem Interpreter ohne installiertes SpecRoad ausführbar. Kein neues Verhalten.

Jede Stage erhält ihr eigenes Apply-Gate mit gefilterter N=3-Gruppe und
vollständiger Pflichtunion. Verhaltenstests werden nicht in Dev ausgeführt.
Produktfortschritt bleibt 729/900, nächste Position 18.a.W.
[Ausführungsstand und Vorbereitung](../history/bundle-640-local-test-history.md).
