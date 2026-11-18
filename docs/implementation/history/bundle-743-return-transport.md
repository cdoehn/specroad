# Bundle 743 — Rückexport und lokale Übernahme

18. November 2026. Quelle ist das erfolgreiche native Result mit SHA-256
`057b8b2cdb893c72dfad54b8713d177504a8617e72bd80a44d28544299d04ba6` und HEAD
`1e7f2cd9e79bbba5c50ecc4064889fa5f4534d04`. Bundle 742 bestätigt
DIALOG-PERFORMANCE.C, 13.946 bestandene Tests und einen sauberen Zustand;
die Produktposition bleibt damit 795/918. Kein alter Commit wird wiederholt.

[RETURN-TRANSPORT-743](../decisions/return-transport-743.md) schließt die konkrete
Format-/Hostdetail­lücke vor den vollständigen Gruppen 18.q und 18.r. Die Reihenfolge
ist genau RETURN-TRANSPORT-743, 18.q.W/R/C, 18.r.W/R/C. Jede Stage installiert
nur ihren eigenen Zustand, erhält N=3 plus vollständige begründete Pflichtauswahl
und wird erst danach committed. Kein vorab installierter Endstand.

Diese Datei gehört zum Zielstand **18.r.R**. Produktziel nach dessen eigenem
erfolgreichen Gate: **800/918**; nächste Produktposition
**18.r.C**. Vorbereitung, Syntax und reine Collection
sind keine ausgeführten Verhaltenstests. Alle Abnahmen erfolgen ausschließlich
in Apply; die sieben Stageergebnisse müssen getrennt belegt werden.

18.q exportiert einen expliziten Proposal aus unveränderter Originalbasis als
einzige native Patch-ZIP; keine Runtimekopie und kein Working-Tree-Import.
Die echten Modul-/PYZ-Tests erstellen, validieren und prüfen den Proposal in
einem Python-only-Prozess ohne Git, Shell, Netzwerk oder Drittanbieterpakete.
R prüft exaktes Inventar, Original- und Zielbindung, Links, Lösch-/Umbenennungs-
manipulationen, Quellwechsel und no_changes. C teilt nur die native API-Anbindung.

18.r prüft denselben Inhalt mit öffentlichem apply_guarded unter Repositorysperre
vor Payload. Eine explizite Hostzulassung für den Transport und die unabhängige
PublicationAuthority des vorhandenen Writers bleiben getrennt. Der einmalige
Hostkanal führt ausschließlich die native Draftaufnahme aus. Fachdateien und
menschliche Reviewpflicht bleiben erhalten; ein echter separater Review-/Apply-
Rundweg prüft den erwarteten Fachhash. R deckt Manipulation, echte Fremdreviews,
ID-/Stagingkonflikte, belegten Replay, Prozessverlust und Result-Ausfall ab.
C trennt nur den nativen Paketbytezugriff; W/R-Testbytes bleiben unverändert.

Fehlende vollständige Verhaltenssuite, CPython-3.10–3.14-/Plattformnachweise und
formale Releasefreigabe bleiben offen. Der Zielzähler schließt Meilenstein 18
nicht pauschal ab. Keine Dienste, CI, Gitaktionen oder lokale Betreiberdateien
sind Bestandteil dieser Produktübergabe.
