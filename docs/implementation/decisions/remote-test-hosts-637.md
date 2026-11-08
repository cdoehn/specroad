# REMOTE-TEST-HOSTS — ausdrücklicher Entwicklungsauftrag

8. November 2026. Der Nutzer beauftragt die zuvor besprochene lokale/SSH-
Testverteilung einschließlich Vorbereitung, langlebiger SSH-Nutzung,
heterogener Laufzeitschätzung und Hostanzeige als ein W/R/C-Bundle.
Dies ist ein ausdrücklicher OFF-PLAN-Umfang, keine delegierte Detailklärung.

Gewählte Umsetzung: vorhandene pytest-xdist-Worker und execnet-Proxies,
getrennte verwaltete Python-Umgebungen und ein kleiner hostgewichteter Scheduler.
Container würden eine zusätzliche Betriebsumgebung verlangen; gemeinsame
Netzwerk-SQLite-Dateien würden den bestehenden Dauerhaftigkeitsvertrag schwächen.
Stattdessen bestätigt der Koordinator Starts und native Phasen synchron nach
SQLite-FULL-Transaktionen. Installationen bleiben eine ausdrückliche CLI-Aktion.
Persönliche Schlüssel/Passphrases bleiben außerhalb von SpecRoad.

Maßgeblich sind [Spec 2.5.5](../../specification/SpecRoad_Spezifikation.md#255-verteilte-apply-tests--remote-test-hosts)
und die [Bedienung](../../development/Remote_Test_Hosts.md).

## Vollständige Stage-Abnahmen

- `REMOTE-TEST-HOSTS.W`: nutzbare Host-CLI, exakte Umgebung, geprüfte aktuelle
  Snapshots, echter Proxy-/Workerpfad, kurze heterogene Warteschlangen,
  dauerhafte zentrale Phasenmessung, Hostanzeige und gebundenes Apply-Gate.
  Synthetische native Integration weist tatsächliche Worker-Ausführung und
  fehlgeschlagenen Prozessabbruch nach. Kein externer Zugang ist Testvoraussetzung.
- `REMOTE-TEST-HOSTS.R`: fehlerhafte Hostprofile, abweichende Umgebungen,
  konkurrierende Belegung, Nachrichtenreihenfolge und Speicher-/Transportfehler
  werden geschlossen abgewiesen; Scheduler-Endzustände erhalten alle IDs.
- `REMOTE-TEST-HOSTS.C`: gemeinsame Profil-/Transportverträge zentralisieren;
  identische Ergebnisse, Pflichtmengen und Fehlergrenzen erhalten.

Jede Stage hat eine vollständige Pflichtauswahl zusätzlich zur gefilterten
Rotationsgruppe. Keine Testkörper/Fixtures in Dev. Statische Prüfung und
Collection sind keine erfolgreiche Verhaltensabnahme. Echte externe SSH-
Hosts werden erst nach Installation über `check`/`prepare` qualifiziert;
dieses Bundle behauptet keine bereits erfolgte Remote-Einrichtung oder
gemessene Beschleunigung. Produktfortschritt 729/900 und nächster Schritt
18.a.W bleiben unverändert. [Bundlebericht](../history/bundle-637-remote-test-hosts.md).

Die offene Folge wird nach dem fehlgeschlagenen W-Start mit
[Korrekturbundle 638](../history/bundle-638-remote-test-hosts-correction.md)
fortgeführt; Kennungen, Rollen und fachliche Abnahmen bleiben erhalten.
