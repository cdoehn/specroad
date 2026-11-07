# Weitere Laufzeitbereinigung der Tests

Manueller OFF-PLAN-Auftrag vom 7. November 2026, als vollständige C-Bereinigung
ohne neues Produktverhalten. Diese Vorbereitung setzt die noch offene
[Planaufteilung](../implementation/SpecRoad_Implementierungsplan.md) fort und
ergänzt die [Merge-Bereinigung vom Vortag](Test_Runtime_20261106.md). Produktpositionen,
normative Spezifikation und bestehende Testidentitäten bleiben erhalten.

## Änderungen und erhaltene Abdeckung

- **Unveränderliche Journalwerte:** Innerhalb eines Aufrufs werden bereits
  eingelesene Journal- und Plan-Dictionaries lokal wiederverwendet, auch bei
  der Prüfung vieler Dateimodi. Exportierte Dictionaries bleiben eigene
  Kopien; jedes neu aufgenommene Journal und jeder Nachfolger werden weiterhin
  vollständig validiert. Keine Wiederverwendung über einen Guard-Aufruf oder
  eine Autoritätsprüfung hinweg. Live-Dateien, Modi, Elternverzeichnisse,
  Sperren, Journale, Receipts, externe Backups und Provider werden weiterhin
  frisch geprüft. Alle Writer-/Recoverygrenzen und Fehlerverträge bleiben.
- **Release-Varianten:** Die drei Fälle Risiko angenommen, Risiko geschlossen
  und Issue gelöst verwenden das vorhandene kleine, nativ geparste Register
  für de-DE/en-GB. Readiness, gebundene synthetische Reviews, echter Writer,
  Versiegelung, Archivprüfung und unveränderte Quellbytes werden unverändert
  geprüft. Die allgemeine native Release-Publikation behält das vollständige
  mitgelieferte Register; alle übrigen Aufrufer behalten ebenfalls diesen
  Standard. Entfallen ist ausschließlich die wiederholte Kombination jedes
  dieser drei Blockerzustände mit dem vollständigen Register. Es entfällt
  kein Testfall und keine fachliche Assertion. Die drei Merge-Referenzfälle
  mit vollständigem Register bleiben ebenfalls unverändert.
- **Apply-Reihenfolge:** Der bereits für CI verwendete Algorithmus verteilt
  lange Tests auf die anfänglichen Worksteal-Warteschlangen. Apply verwendet
  dafür seinen bereits eingefrorenen Snapshot, nach N=3-Auswahl, Laufzeitfilter
  und Pflichtvereinigung. Die Testmenge, stabilen Nummern, Workergrenzen,
  Testgates und dauerhafte Laufzeithistorie bleiben unverändert. Innerhalb
  jeder anfänglichen Warteschlange stehen lange Tests zuerst; spätere
  Umverteilung bleibt Aufgabe von xdist. Neue oder zuletzt ungültig gemessene
  Tests erhalten nur zur Sortierung eine Schätzung von 300 Sekunden, wie
  beim CI-Standard. Diese Schätzung wird weder als Messwert gespeichert noch
  zur Filterentscheidung verwendet. Historische Läufe ohne aktuelle
  Laufzeitpolicy behalten ihre bisherige Reihenfolge. CI verwendet denselben
  Algorithmus mit seinen unveränderten Planregeln.

Die echten Abbruchtests mit ihren Prozessbeendigungen und der Restore-CLI-Test
bleiben unverändert. Eine Kürzung dieser Integrationsabdeckung ist nicht Teil
dieser Bereinigung.

## Erhaltener Vorgänger und Formatkorrektur

Das native Result `438f88956b41ef558a22fee0619f993f5cd860ae2d966843264c089b18ea13ce`
von Bundle 623 meldet 7.874 bestandene Tests in 389,26 Sekunden, anschließend
aber einen fehlgeschlagenen `git diff --cached --check`: 328 ausgelagerte
Dokumente endeten mit zusätzlichen Leerzeilen. Es entstand kein Commit.
Der vollständige Materialisierungsstand einschließlich Index bleibt die Basis.

Diese manuell beauftragte private Fortsetzung erhält die offene Kennung
`PLAN-MODULARIZATION-20261106`, Rolle, gebundene Commitnachricht, sämtliche
Planänderungen und die ursprüngliche Pflichtauswahl. Sie entfernt nur die
überzähligen abschließenden LF-Zeichen der gemeldeten Dateien und ergänzt die
oben beauftragten Testoptimierungen samt Pflichtregressionen im selben
vollständigen Bereinigungsstand. Alle entfernten Trenn-LFs sind im privaten
Rekonstruktionsnachweis erfasst; Inhalte, Positionen, Abnahmen und Verweise
bleiben erhalten. Kein Gate oder Git-Check wird abgeschwächt. Der aktuelle
Zielstand erfordert ein neues vollständiges Apply-Gate; die grünen Tests des
Vorgängers ersetzen dieses nicht. Produktfortschritt bleibt 726/900, als
nächste Produktposition bleibt 17.l.W offen. Die Bundlezählung des Zielstands
wird nur im tatsächlich erfolgreichen Commit wirksam.

## Abnahme

Neue Verhaltenstests prüfen die ausgeglichene Startverteilung, gleiche
Testmenge, deterministische Gleichstände, fehlende/ungültige Messwerte und
kleine Auswahlen bei unterschiedlicher Workerzahl. Der Runner-Test prüft die
tatsächliche Argumentdatei nach Pflichtvereinigung und anschließend das
unabhängige Commitgate. Spätere Messungen dürfen den eingefrorenen Snapshot
nicht ändern; fehlende, doppelte und ersetzte Beobachtungen bleiben Fehler.
Neue Testnummern werden ausschließlich angehängt.

Vor dem einen vollständigen OFF-PLAN-C-Commit ist die fällige gefilterte
N=3-Gruppe plus vollständige Pflichtauswahl auszuführen. Diese enthält alle
geänderten Testdateien und relevanten Merge-, Migrations-, Writer-, Recovery-,
Release-, Sprach-, Apply- und CI-Vertragsregressionen. Dev führt keine
Testkörper, Fixtures oder Test-Unterprozesse aus. Collection, Syntaxprüfung
und native Paketprüfung sind keine Verhaltensabnahme und kein Laufzeitbeleg.
Ein Geschwindigkeitsgewinn wird erst aus tatsächlichen neuen Messungen
abgeleitet; hier wird weder eine feste Beschleunigung noch ein Erfolg behauptet.

Die private ZIP bleibt in Dev und wird an das vollständig geprüfte
Fehler-Result von Bundle 623 gebunden. Vor einer später autorisierten Übergabe
sind dessen Maßgeblichkeit, Vorherbytes und Bindung erneut zu prüfen. Das Bundle selbst startet keinen
Dienst und keine eigene Warte- oder Apply-Schleife.
