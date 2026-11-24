# Bundle 807 — Originalbelege und Hostablehnung in 21.d.R/C

24. November 2026. Das native Result
`1c2f300b9d75dea752f5789c30317ee30597c5f1a6d8d13f259d40cc6fb0d3fe`
belegt den erfolgreichen W-Commit
`a5cc0606f785e248c3a3cf911eb94a43caeb26ae`: 27.026 bestandene Tests.
21.d.R scheiterte danach mit zwei Fehlern bei 27.030 bestandenen Tests;
21.d.C wurde nicht ausgeführt. Bestätigt sind damit 898/996 Positionen.
Der Schedulerstillstand aus Bundle 805 trat in diesen beiden Gates nicht auf.
Der vorherige strombedingt abgebrochene Versuch bleibt ein Abbruchnachweis.

Die zwei Fehler sind im fehlenden Request-Original und in der CLI-Meldung
einer unabhängigen Hostverweigerung belegt. Der Force-Belegleser übersetzt
fehlende Dateien einschließlich eines Verschwindens zwischen stat und Read
in einen strukturierten Konflikt (Exit 6), andere physische Lesefehler in
einen strukturierten I/O-Fehler (Exit 5). Descriptorrelative No-follow-Reads,
Identitäts-/Hash-/Namensraumprüfungen und die doppelte Beobachtung bleiben.
Fehlende Originale werden weder ersetzt noch als gültige Nachweise behandelt.

Der Force-Writer meldet eine Hostverweigerung vor dem Aufruf des gemeinsamen
Publikationskerns als not_committed. Nach Eintritt in diesen Kern bleibt
der unbestätigte Ausgang konservativ unknown. Exit 7, negative Forcebefunde,
fehlende Freigabe und das Verbot automatischen Retries bleiben erhalten.
Die Korrektur erfüllt den bestehenden X.11/X.12-Vertrag; keine neue Klärung.

Die ursprünglichen beiden Fehleroracles bleiben bestehen. Neun zusätzliche
Fälle prüfen alle drei Originalbelege, einen konkurrierend verschwindenden
Request, einen Leserechtefehler, negative/nichtboolesche/manipulierte
Hostantworten sowie Hostverweigerung nach einer tatsächlich geschriebenen
Datei. Der CLI-Fall prüft zusätzlich unveränderte Zielbytes und das Fehlen
eines Schreibmarkers oder Erfolgsbelegs vor Publikationsbeginn. Die neuen
Fälle verwenden eigene temporäre Dateien und synthetische Hostantworten.

Die Fortsetzung enthält genau 21.d.R und 21.d.C mit ursprünglichen IDs,
implementation-Rollen und Nachrichten. correction_of bindet den offenen
Rest des Plans
`95d335c5b05bd81e63d37116842eadbb4caef7097cd448a37ae00f55f318a9c7`.
Die vollständigen Vorherbytes stammen aus dem erhaltenen R-Arbeitsstand;
W und der Klärungscommit werden nicht wiederholt. Alle alten Pflichtfälle
und stabilen Testnummern bleiben erhalten. Die geänderte Testdatei und
transitiv betroffene Verbraucher werden vollständig in beide Gates aufgenommen.
C erhält exakt die R-Testquellen und die bisher geplante reine Auslagerung
von Ergebnisfunktionen. Kein Endstand wird vorab installiert.

Die Core-Korrekturen erfordern neue echte Ressourcenbelege pro R/C-Build;
historische Messungen und CPU-/RSS-Gates bleiben unverändert. Jedes eigene
N=3-plus-Pflichtauswahl-Gate muss vor dem jeweiligen Commit bestehen.
Dev führt keine Testkörper aus; Collection und native Paketvalidierung sind
keine Apply-Abnahme. Die vorbereiteten Zähler gelten erst nach dem Gate.
21.e und sämtliche menschlichen Endabnahmen bleiben offen. Control bleibt
pausiert; das Bundle ändert keine Betreiberfreigabe oder Budgets.

## Tatsächliche Messungen vom 24. November 2026

Je ein Aufwärmlauf und fünf vollständige Läufe mit 1.000 Texten (166–440
Unicode-Codepoints), dem nativen Adapter samt Modellladen, Haupt- und
Workerprozess. Zwei unveränderte exakte Core-Pakete, Beobachter v2, keine
Wiederholung und kein übertragener Nachweis eines früheren Builds.

Referenz: Linux x86_64, Intel Core i7-8700, sechs Kerne/zwölf logische CPUs,
32 GB RAM, lokale SSD, CPython 3.14.7, Performance-Governor, Swap aus,
Standardprofil, Cache aus, LC_ALL=C und TZ=UTC. Die vollständigen portablen
Plattform-/Paket-/Fixture-/Modell-/Skriptbindungen stehen in den Originalbelegen.

| Stage | CPU-Maximum (s) | Wall-Median (s) | Simultanes RSS-Maximum (Bytes) | Konservative RSS-Obergrenze (Bytes) |
|---|---:|---:|---:|---:|
| 21.d.R | 6.90 | 6.927318 | 242245632 | 385507328 |
| 21.d.C | 6.90 | 6.915825 | 233033728 | 387497984 |

Alle zehn maßgeblichen Läufe erfüllen die unveränderten Grenzen von
120 CPU-Sekunden einschließlich Rundungsreserve und 512 MiB Gesamt-RSS.
Die konservative Obergrenze ist keine gemessene simultane Spitze. Der native
Prüfer akzeptiert die vollständigen Hashketten und exakten Buildbindungen.

- 21.d.R: Build `add82a4f74d65d63b9a8f6e60d76f9396cf0e29c45eae0d1b147aca2c81966c4`; [Receipt](../../../verification/fixtures/analyzer-resources-builds/add82a4f74d65d63b9a8f6e60d76f9396cf0e29c45eae0d1b147aca2c81966c4/receipt.json), SHA-256 `a92291cfa7ab80e7c049258a423f7b3b6b8d52d47a32db39a030bbf83a64a2ae`.

- 21.d.C: Build `a237a748eaf4fef698652f8d04f50c9168c8cb3e98e48781033d47ef27e6e2d7`; [Receipt](../../../verification/fixtures/analyzer-resources-builds/a237a748eaf4fef698652f8d04f50c9168c8cb3e98e48781033d47ef27e6e2d7/receipt.json), SHA-256 `a54f00db4a15f75dbefc64119a7d3d9c4f3af80b5e5b3df818ecd5437b70ba67`.

Die dokumentierte Plattform-Allowlist entfernt lokale Host-/Boot-/Maschinen-
Kennungen; GNU-time-Kommandozeilenpräfixe sind entfernt. Original-/Exporthashes
belegen dies im Receipt. Messwerte bleiben unverändert, historische Belege
bytegleich erhalten. Die beiden neuen Belegsätze sind ab R verfügbar;
Produktzustände bleiben getrennt und jeweils an ihr eigenes Apply-Gate gebunden.
Die Hosteinstellungen und der Poolbetrieb mit zwölf Workern wurden vollständig
wiederhergestellt. Diese Messungen sind keine Apply-, Review- oder Releaseabnahme.
