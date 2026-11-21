# Bundle 775 — vollständige Analyzer-Korrektur mit realen Folgemessungen

Quelle ist das native Fehler-Result von Bundle 774, SHA-256
`cb7a24c968952ffc99dd3b11c5b13123ab081c75b169bc6c1308af6df4e0475d`.
Der Klärungscommit `73bf1bb81d8e867ac38fc2f34eb6de45ff9a5deb` ist nach
7.443 bestandenen Tests committed. Das anschließende Gate für 19.w.W meldete
24 Fehler und 9.086 bestandene Tests; kein Implementierungscommit entstand.
Diese Korrektur ersetzt die offene Vorbereitung aus [Bundle 774](bundle-774-analyzer-work-roundtrip.md).
Der vollständige Rest 19.w.W/R/C und 19.x.W/R/C, alle IDs, Rollen und exakten
Commitnachrichten bleiben erhalten. Keine neue Klärung und kein Wiederholen
des erfolgreichen Präfixes.

Der Work-Worker kopierte eine Engine-Liste mit dem absichtlich nur Objekte
akzeptierenden JSON-Parser. Die Kopie verwendet jetzt eine Objekthülle und
erhält die strikte Dekodierung sowie unabhängige verschachtelte Werte.
Der vorhandene CLI-Test unterscheidet den bekannten ausführbaren Adapter von
unverändert externen fremden Deskriptoren. Seine Read-only-Abnahmen bleiben.

Ein neuer ausdrücklicher Messauftrag lieferte für die drei korrigierten
19.w-Produktbuilds jeweils einen Aufwärmlauf und fünf reale Referenzläufe mit
1.000 vollständigen Texten. Die native Auswertung bestätigt alle drei Serien.
Ihre konservative RSS-Obergrenze liegt unter 512 MiB und die gesamte CPU-Zeit
einschließlich Rundungsreserve unter 120 Sekunden. Quellen, Originaldaten,
Hashketten, tatsächliche Werte und die unveränderten Messskripte sind gebunden.
Der C-Build gilt auch für die folgenden produktbytegleichen 19.x-Stände.
Details und Zahlen: [Ressourcenmessung](../../development/Analyzer_Resources.md).

Die alte Messung bleibt bytegleich erhalten, einschließlich ihrer festen
Zahlen- und Prozesslabel-Regressionsorakel. Zusätzlich lädt das aktuelle Gate
den neuen Beleg ausschließlich unter dem tatsächlich nativ gebauten Corehash.
Ein fehlender oder abweichender Build kann weiterhin nicht bestehen. Die
neuen Belege werden stufenweise ergänzt; kein W/R/C-Endstand wird vorab installiert.

Dev führt nur statische Prüfungen, reine Collection und native Paketvalidierung
aus. Jede der sechs Stufen braucht ihr eigenes gefiltertes N=3-plus-Pflichtgate
vor dem Commit. Die Zielzähler sind keine hier behaupteten Apply-Erfolge.
19.t und die menschlichen Korpusreviews bleiben vor 19.y erforderlich;
Ressourcenmessungen ersetzen keine CLI-/Work-, Vollsuite- oder Releaseabnahme.
