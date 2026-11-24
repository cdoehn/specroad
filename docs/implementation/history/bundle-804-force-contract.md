# Bundle 804 — gemeinsamer Forcevertrag

Quelle: `043fff6d178da99abffd38b0675d5c17951939576cf657531e7ce07403efc0ba`;
sauberer nativer Snapshot auf `334f571938b3854d8687ac4ac6f7168edd1ceff9`.
Der OFF-PLAN-Klärungspräfix FORCE-CONTRACT-804 erhält die bereits bestätigten
897 Produktpositionen. Danach folgen 21.d.W, 21.d.R, 21.d.C einzeln.

W ergänzt explizite Requests, Gateklasseninventar, Envelope 2.1, konkrete
resource_replace-Ziele über den vorhandenen Writer und passive negative
Abschlussbelege. R bindet Hashabweichungen, aktuelle Quellen, Originalreceipts,
lesbare Teilbereiche und Fehlerausgänge. C verschiebt reine Ergebnisfunktionen
unverändert und verwendet normale Imports; sämtliche W/R-Testquellen bleiben.

Vorbereitet sind tatsächliche Schreib-, Replay-, CLI-/API- und Fehleroracles.
Dev führt keine Verhaltenstests aus. Collection, Syntax und native Paketprüfung
sind keine bestandenen Produkttests. Jeder Zustand erhält sein eigenes
N=3-plus-ungefilterte-Pflichtauswahl-Gate vor dem Commit. Kein Endstand wird
vorab installiert. Neue echte Messbelege werden separat mit exaktem Buildhash
referenziert; eine Messung ersetzt das Apply-Gate nicht.

21.e sowie die spätere Komponenten-/Plattformintegration und menschliche
Endabnahme bleiben offen. Insbesondere gibt dieses Bundle keinen vollständigen
Produkt-Force- oder menschlichen Review-/Releaseerfolg vor.

## Tatsächliche Messungen der endgültigen Builds

23. November 2026: je ein Aufwärmlauf und fünf vollständige Läufe mit
1.000 Texten (166–440 Unicode-Codepoints), dem nativen Adapter einschließlich
Modellladen und Haupt-/Workerprozess. Messskripte, Modell und Grenzwerte
bleiben unverändert. Keine Messung wird einem anderen Produktbuild zugeordnet.

Referenz: Linux x86_64, Intel Core i7-8700 (6 Kerne/12 logische CPUs),
32 GB RAM, lokale SSD, CPython 3.14.7, Performance-Governor, Swap aus,
Standardprofil, Cache aus, LC_ALL=C und TZ=UTC. Die vollständigen portablen
Plattform-, Paket-, Fixture-, Modell- und Skriptbindungen stehen in den Belegen.

| Stage | CPU-Maximum (s) | Wall-Median (s) | Simultanes RSS-Maximum (Bytes) | Konservative RSS-Obergrenze (Bytes) |
|---|---:|---:|---:|---:|
| 21.d.W | 7.04 | 6.969204 | 239607808 | 383361024 |
| 21.d.R | 7.01 | 6.960708 | 240107520 | 384581632 |
| 21.d.C | 6.96 | 6.971594 | 229720064 | 383533056 |

Alle fünf maßgeblichen Läufe je Build erfüllen die unveränderten Grenzen
von 120 CPU-Sekunden einschließlich Rundungsreserve und 512 MiB Gesamt-RSS.
Die konservative Obergrenze ist keine gemessene simultane Spitze. Der native
Prüfer hat alle drei exakten Buildbindungen und vollständigen Hashketten akzeptiert.

- 21.d.W: Build `f14b149048d13c9f72f590c4de5cee0509fdbb68c8eb9d0c337dd0632768f1ab`; [Receipt](../../../verification/fixtures/analyzer-resources-builds/f14b149048d13c9f72f590c4de5cee0509fdbb68c8eb9d0c337dd0632768f1ab/receipt.json), SHA-256 `0df9805bd5be236cfecfedd9896aadd600f3234c86388d070cb0415fdeb68f7a`.
- 21.d.R: Build `72c9c58a06dcf9a8f66ab19ce1eba4c34b38215d56b57fab2bb8ffb6c0ae9990`; [Receipt](../../../verification/fixtures/analyzer-resources-builds/72c9c58a06dcf9a8f66ab19ce1eba4c34b38215d56b57fab2bb8ffb6c0ae9990/receipt.json), SHA-256 `1ced3dfaacc651dff8e0fd61ac267ae17e49e0f5db7624de62bb72f678b6233f`.
- 21.d.C: Build `598c884f3d36a2b64faeac0563610f6feaab40addf641fbcb5ed66da743f9084`; [Receipt](../../../verification/fixtures/analyzer-resources-builds/598c884f3d36a2b64faeac0563610f6feaab40addf641fbcb5ed66da743f9084/receipt.json), SHA-256 `cb51a87c7a9fa5d2756af06af0d725005cb10eae2d40b110078d85a81e105b2c`.

Insgesamt entstanden sechs vollständige Serien: drei erste Kandidaten,
zwei nach einer statisch gefundenen R/C-Korrektur und eine vollständige
Wiederholung von R. Die ersten R/C-Belege wurden nicht auf die geänderten
Builds übertragen. In der ersten Serie des endgültigen R-Builds erfasste
der Umgebungsbeobachter zwei neu gestartete eigene Messprozesse kurzzeitig
als Fremdlast; diese unqualifizierte Originalserie bleibt erhalten und wird
nicht als Erfolg verwendet. Die vollständige neue R-Serie verwendet dieselben
Skripte, Eingaben und Grenzen. Maßgeblich sind ausschließlich die oben
gebundenen drei Serien mit zusammen 15 Mess- und drei Aufwärmläufen.

Die bestehende Plattform-Allowlist und Entfernung lokaler GNU-time-
Kommandozeilenpräfixe sind im Receipt durch Original- und Exporthash belegt.
Messwerte und Befunde wurden nicht verändert. Historische Produktbelege bleiben
bytegleich; drei neue Buildverzeichnisse kommen hinzu. Betreiberkonfiguration,
Zugangsdaten und Sitzungsschlüssel sind keine Produkt-Payload.

Die portablen Messbelege aller drei Builds liegen ab W vor. Produkt- und
Testzustände bleiben getrennt; jeder Zustand wird erst nach dem vorherigen
erfolgreichen Apply-Gate ausgebracht. Der unveränderte aktuelle Ressourcen-Test
gehört zu jeder Pflichtauswahl. Die Messungen sind kein Apply-, Review- oder
Releaseerfolg. Der Messhost wurde anschließend auf seine ursprünglichen
Einstellungen und den normalen Pool mit zwölf Workern zurückgestellt.
