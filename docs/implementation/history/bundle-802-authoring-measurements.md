# Bundle 802 — Echte Messbelege für den vollständigen 21.c-Rest

Datum: 23. November 2026. Maßgebliches Result von Bundle 801:
`cd1d3619f7e617fa05bee1aefd9d1201cdb4e56c8f00d1d1a614755110d556b6`.
Es bestätigt **26.640 bestandene und einen fehlgeschlagenen Test** in 21.c.W.
Einziger Fehler war der fehlende aktuelle Buildbeleg in
`test_measured_full_adapter_stays_within_total_cpu_and_memory_limits`.
Kein Commit entstand. Die Reparaturen von Bundle 801 bleiben vollständig erhalten.

Der ausdrückliche manuelle Messauftrag wurde für die drei unveränderten
W/R/C-Produktbuilds ausgeführt: jeweils ein Aufwärmlauf und fünf neue Läufe
mit 1.000 vollständigen Texten von 166 bis 440 Unicode-Codepoints, nativer
Adapter samt Modellen und Haupt-/Workerprozess. Keine Messwiederholung,
keine Übertragung eines Befunds auf einen anderen Build.

Referenz: Linux x86_64, Intel Core i7-8700 (6 Kerne/12 logische CPUs),
32 GB DDR4 (konfiguriert 2400 MT/s), lokale NVMe-SSD, CPython 3.14.7;
Performance-Governor, kein Swap oder konkurrierender Testlauf, Standardprofil,
Cache aus, `LC_ALL=C`, `TZ=UTC`. Vollständige Plattform-, Fixture-, Modell-,
Paket- und Messskriptbindungen liegen in den komprimierten Originalbelegen.

| Buildstage | CPU-Maximum (s) | Wall-Median (s) | Beobachtetes simultanes RSS-Maximum (Bytes) | Konservative RSS-Obergrenze (Bytes) |
|---|---:|---:|---:|---:|
| 21.c.W | 6.95 | 6.937034 | 229019648 | 383131648 |
| 21.c.R | 7.00 | 6.941259 | 234983424 | 382926848 |
| 21.c.C | 6.96 | 6.901801 | 238809088 | 382910464 |

Alle fünf Läufe je Build erfüllen die unveränderten Grenzen von 120
CPU-Sekunden einschließlich Rundungsreserve und 512 MiB Gesamt-RSS.
Die konservative Obergrenze ist eine Schranke, keine gemessene simultane Spitze.
Der native Belegprüfer hat alle drei Hashketten und Ressourcenbefunde akzeptiert.

Exakte Bindungen und portable Belege:

- 21.c.W: Build `aec3365aaffa2b443d84c64bc0494d1a55de2b4574eb9944ac292e9a801e8c14`; [Receipt](../../../verification/fixtures/analyzer-resources-builds/aec3365aaffa2b443d84c64bc0494d1a55de2b4574eb9944ac292e9a801e8c14/receipt.json), SHA-256 `16af2a270efa54a9f4ccfbd243963c996a16c4bfab8641d7dd0f758a88202cfc`.
- 21.c.R: Build `c7d816153a8330d818742b2b888cd9feaf951caf6f885be1cf1a90be6e4acd73`; [Receipt](../../../verification/fixtures/analyzer-resources-builds/c7d816153a8330d818742b2b888cd9feaf951caf6f885be1cf1a90be6e4acd73/receipt.json), SHA-256 `5d9294b65aa7cc6ef86262b62c96bfcb3340e1d845b3e684859881f0b1f2bfc2`.
- 21.c.C: Build `311975993091508149567b2ac61699bfa10b2e88e14ccd7bdb20c8f6dd102804`; [Receipt](../../../verification/fixtures/analyzer-resources-builds/311975993091508149567b2ac61699bfa10b2e88e14ccd7bdb20c8f6dd102804/receipt.json), SHA-256 `9c99b603bf477e39c4f863e278923539b5302a7945e39bcc90be1e0d9a4d35cf`.

Die unveränderten Messskripte, GNU-time-Zahlen, Prozessinventare, RSS-Samples,
Ergebnis- und Fixturebytes bleiben hashgebunden. Ausschließlich die bestehende
Plattform-Allowlist und das Entfernen lokaler GNU-time-Kommandozeilenpräfixe
werden im Receipt mit Vorher-/Nachherhash dokumentiert. Keine Hostkonfiguration,
Zugangsdaten oder Sitzungskennungen werden ausgeliefert. Historische Belege
bleiben unverändert; die drei neuen Buildverzeichnisse werden ergänzt.

Der vollständige offene Commitrest **21.c.W → 21.c.R → 21.c.C** behält alle
IDs, Rollen `implementation`, Produktquellen, Testquellen, Testnummern und
bisherigen Pflichtabnahmen. Der erfolgreiche Klärungscommit wird nicht
wiederholt. Es gibt keine neue Klärung und keine zusätzlichen Planstages.
`correction_of` bindet exakt den offenen Rest des nativen Fehler-Results.

Die portable Evidenz für alle drei Builds liegt schon in W vor; Produktcode
und Testzustände bleiben getrennt und werden erst nach dem vorherigen
erfolgreichen Gate ausgebracht. C bleibt die vorbereitete Strukturbereinigung
mit unveränderten R-Testquellen. Der unveränderte Ressourcen-Test bleibt in
jeder Stage verpflichtend. Dev führt keine Verhaltenstests aus; der separate
manuelle Messauftrag ist kein Apply-Gate. Jede Stage benötigt weiterhin ihr
eigenes N=3-plus-Pflichtauswahl-Gate vor dem Commit.

Die vorbereiteten Fortschrittswerte gelten erst nach dem jeweiligen Apply-Gate.
Aktuelle Apply-Abnahme, menschliche Sprach-/Herkunftsreviews und Freigabe zur
Produktbenutzung werden durch diese Messung nicht behauptet. Control bleibt
pausiert; keine Budgetänderung oder automatische Fortsetzung.
