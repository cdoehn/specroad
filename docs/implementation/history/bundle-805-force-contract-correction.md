# Bundle 805 — vollständige Korrektur von 21.d.W/R/C

23. November 2026. Maßgeblich ist das native Fehler-Result
`ad972edfc9bc0713eceba8f739dd2383d3afb68f2f706b001bc446eac902cb6f`.
Der Klärungscommit `76b526718206564c4d39b5c360bf1f0492088178` ist erfolgreich
und bleibt erhalten; 21.d.W scheiterte mit 186 Fehlern bei 26.564 bestandenen
Tests. R und C wurden nicht ausgeführt. Bestätigt bleiben 897/996
Produktpositionen bis 21.c.C. Die normative Spezifikation bleibt unverändert.

Die Korrektur setzt genau den vollständigen offenen Rest 21.d.W, 21.d.R,
21.d.C mit seinen ursprünglichen implementation-Rollen und Commitnachrichten
fort. Kein erfolgreicher Präfix wird wiederholt, keine neue Klärung ergänzt.
Die correction_of-Bindung verweist auf Plan-SHA-256
`5e4e53488f49a94a726fc7c2c2a093f9e5919ab56bf4ec5106454398ace3e880`.

173 Fehler zeigen zyklische Imports zwischen dem neuen Force-Writer und
Authoring/Verification/Planlesern. Die fünf neuen öffentlichen Force-Exporte
werden erst bei Zugriff geladen. Der reine Force-Datenvertrag importiert
keinen Speicher-/Projektleser für bereits kanonisierte JSON-Werte; Hilfe und
Version bleiben projektfrei. work.resume verweigert die nicht unterstützte
Forceoption vor dem Projektlesen. Der native Zielbericht berücksichtigt die
explizit konfigurierte Sprachregistrierung auch außerhalb generischer
Verzeichnisklassen; fehlende oder beschädigte Originalbytes bleiben negativ.

Die übrigen Fehler betreffen diese Start-/Options-/Ressourcenpfade und
Testdaten für die additive Raw-Operation, globale Flags und Katalogzahlen.
Die gültige Raw-Hilfe heißt --help. Die typisierten Operationstests prüfen
resource_replace mit vollständigen Feldern und einem separaten 1.3-Plan;
unzulässige Mischpläne bleiben abgelehnt. Keine vorhandene Prüfung wird
entfernt oder als Erfolg umgedeutet. Neue unabhängige Prozessfälle prüfen
öffentliche Imports aus Quelle, Modul und Zipapp. Ein Ressourcentest prüft
vorhandene, fehlende und beschädigte Sprachregistrierungsbytes.

Alle Korrekturen gelten in W, R und C; die zusätzlichen R-Fälle bleiben
erhalten. C verschiebt weiterhin dieselben reinen Funktionen und hat exakt
die R-Testquellen. Die im Fehler-Result vorhandenen Testnummern bleiben
unverändert; neue Kennungen werden angehängt. Die bisher angekündigte
Pflichtauswahl wird erhalten und um sämtliche Fehlerdateien, geänderten
Testdateien und statisch betroffenen Helfer-Verbraucher erweitert.

Jede Stage behält ihr eigenes N=3-plus-Pflichtauswahl-Gate vor dem Commit.
Es wird kein Endstand vorab installiert. Syntax, reine Collection und native
Bundlevalidierung ersetzen keinen bestandenen Verhaltenstest. In Dev werden
keine Testkörper ausgeführt; die Apply-Abnahme dieser Korrektur ist offen.
Die Zähler in den einzelnen Stages sind Ziele nach deren erfolgreichem Gate.
21.e und die menschlichen Endabnahmen bleiben unverändert offen.

## Korrektur des Messbeobachters

Ein zusätzlicher belegter Beobachterfehler ordnete neu gestartete eigene
Messprozesse zwischen Baumaufnahme und Umfeldprüfung kurzzeitig als Fremdlast
ein. Die unqualifizierten Originalserien bleiben erhalten. v2 prüft eine
stabile aktuelle Elternkette bis zur ursprünglichen Wrapperidentität; Namen
allein begründen keine Ausnahme. Unaufklärbare, verschwundene, umgehängte
oder wiederverwendete Identitäten werden nicht ausgenommen. Dreizehn neue
Apply-Fälle prüfen diese Grenze einschließlich gleichnamiger echter Fremdlast.

Die archivierten v1-Skripte bleiben bytegleich. Der Quellenbeleg akzeptiert
exakt den vollständigen v1- oder v2-Skriptsatz. Die eigentliche CPU-/RSS-
Abnahmefunktion, Grenzwerte und native Auswertung bleiben unverändert. SR-TC-0721
bindet die ergänzten Regressionen; seine fachliche Anforderung bleibt erhalten.

## Tatsächliche Messungen der korrigierten Builds

23. November 2026: je ein Aufwärmlauf und fünf vollständige Läufe mit
1.000 Texten (166–440 Unicode-Codepoints), dem nativen Adapter einschließlich
Modellladen und Haupt-/Workerprozess. Die drei Produktpakete blieben während
der Messungen unverändert. Keine Messung wird einem anderen Build zugeordnet.
Der korrigierte Beobachter v2 ist durch seinen Skript-Hash gebunden; die drei
anderen Messskripte, der Workload und die Grenzen sind unverändert.

Referenz: Linux x86_64, Intel Core i7-8700 (6 Kerne/12 logische CPUs),
32 GB RAM, lokale SSD, CPython 3.14.7, Performance-Governor, Swap aus,
Standardprofil, Cache aus, LC_ALL=C und TZ=UTC. Die vollständigen portablen
Plattform-, Paket-, Fixture-, Modell- und Skriptbindungen stehen in den Belegen.

| Stage | CPU-Maximum (s) | Wall-Median (s) | Simultanes RSS-Maximum (Bytes) | Konservative RSS-Obergrenze (Bytes) |
|---|---:|---:|---:|---:|
| 21.d.W | 7.01 | 6.939023 | 218771456 | 381329408 |
| 21.d.R | 6.99 | 6.930927 | 234274816 | 383320064 |
| 21.d.C | 6.97 | 6.951436 | 239050752 | 383369216 |

Alle fünf maßgeblichen Läufe je Build erfüllen die unveränderten Grenzen
von 120 CPU-Sekunden einschließlich Rundungsreserve und 512 MiB Gesamt-RSS.
Die konservative Obergrenze ist keine gemessene simultane Spitze. Der native
Prüfer akzeptiert die vollständigen Hashketten und die drei exakten Buildbindungen.

- 21.d.W: Build `5fb01944988b112d21a606d857565285059b362c016966a8b09071772d2802fc`; [Receipt](../../../verification/fixtures/analyzer-resources-builds/5fb01944988b112d21a606d857565285059b362c016966a8b09071772d2802fc/receipt.json), SHA-256 `24a748f16ebb126c10039271dcf8ce4e79bf0b4773572d388385a6efd1cf23c5`.
- 21.d.R: Build `186d0998254ec5ba6ea24194d9377b80d26884a305f786ba8987779d65090b68`; [Receipt](../../../verification/fixtures/analyzer-resources-builds/186d0998254ec5ba6ea24194d9377b80d26884a305f786ba8987779d65090b68/receipt.json), SHA-256 `307a7bd855471ab2bf52034c01cea7b3882999777da256cd60a7eb55239f96ef`.
- 21.d.C: Build `dcc48b7abd623f8c95d95cb871d3704cf9dd4db67299867e1392c2078411f2d0`; [Receipt](../../../verification/fixtures/analyzer-resources-builds/dcc48b7abd623f8c95d95cb871d3704cf9dd4db67299867e1392c2078411f2d0/receipt.json), SHA-256 `9c65c4c2df5ac29be439d06c20181aef908e34f5c9990c99fd0a37986d70969f`.

In diesem Korrekturauftrag entstanden acht vollständige Serien: zuerst drei
mit v1, dann eine begrenzte Wiederholung von R und C mit unveränderten
Eingaben, anschließend drei neue Serien mit dem korrigierten Beobachter v2.
Die ersten R/C-Serien und die C-Wiederholung sind wegen der beobachteten
Prozesszuordnungsfehler unqualifiziert. Sie bleiben als Originaldaten erhalten
und werden nicht nachträglich als Erfolge gewertet. Auch die qualifizierten
früheren W-/R-Serien bleiben erhalten. Maßgeblich für diese Übergabe sind die
oben gebundenen drei vollständigen v2-Serien mit 15 Mess- und drei Aufwärmläufen.

Die bestehende Plattform-Allowlist und Entfernung lokaler GNU-time-
Kommandozeilenpräfixe sind im Receipt durch Original- und Exporthash belegt.
Messwerte und Befunde wurden nicht verändert. Historische Produktbelege und
v1-Skripte bleiben bytegleich; drei neue Buildverzeichnisse kommen hinzu.
Betreiberkonfiguration, Zugangsdaten und Sitzungsschlüssel sind keine Payload.

Alle drei Messbelege liegen ab W vor. Die Produkt- und Testzustände bleiben
getrennt; jede Stage folgt erst auf das erfolgreiche Apply-Gate der vorherigen.
Die Messungen ersetzen weder Apply noch menschliches Review oder Releasefreigabe.
Der Messhost wurde auf seine ursprünglichen Einstellungen und den normalen
Pool mit zwölf Workern zurückgestellt. Die Apply-Abnahme bleibt offen.
