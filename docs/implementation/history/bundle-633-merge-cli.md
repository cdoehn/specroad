# Bundle 633 — öffentliche Merge-/Work-Integration

8. November 2026. Quelle: Result-SHA-256
`c96c954fbce51828061d9add226e5995ac1d80da119f94be4cfb43785bea4750`,
HEAD `64930b8f34f17e3171a84d705298ce3b1b2e2ce0`, saubere Hauptlinie.
632 ist nachweislich abgeschlossen; 17.l.W wird nicht wiederholt.

Dieser Stand ist die vorbereitete C-Stufe 17.l.C (729/900), keine Behauptung
vorweggenommener Tests. Er erhält seinen eigenen Apply-Testgate vor dem Commit.
Der Klärungspräfix [MERGE-CLI-633](../decisions/merge-cli-633.md) bindet zuvor
die Schnittstelle in Spec 0.2.74 und Planrevision 112.

`merge plan --for-apply` erzeugt den vollständigen vorhandenen nativen
Publication-ChangePlan, auch aus einem abgeschlossenen und erneut geprüften
Work-Ergebnis mit explizit aktuellen Quellen. `merge apply` verwendet diesen
Plan, den bestehenden nativen Writer und die historischen Request-Belege.
Dry-run, falsche Originalbytes, veraltete Quellen, negative Hostautorität,
unterbrochene portable Vorbereitung und nichtkanonische auditierte Auflösungen
sind in den tatsächlichen Verhaltensfällen abgedeckt. Prüfungen und Recovery
werden nicht simuliert oder ersetzt.

Die C-Stufe zentralisiert die Quellen-/Work-/Aufrufmatrix und ihre kleinen
nativen Originalfixtures in `tests/support/merge_matrix.py`. Alle Testnamen,
Parameterwerte und fachlichen Funktionskörper bleiben erhalten; mutable
Projekte und Work-Verzeichnisse bleiben pro Test getrennt. Für sie ist wegen des ausdrücklichen M17-Gates die vollständige
verfügbare Suite als Pflichtmenge vorgesehen. Der Erfolg ist erst aus dem
gebundenen Apply-Result abzulesen; Collection ist keine Verhaltensabnahme.
Fehlende Plattform- und menschliche Freigaben bleiben weiterhin offen.

Zusätzlich ausdrücklich vom Nutzer beauftragt: eine lokale, ignorierte
`CURRENT_WORK.txt` als Arbeitsnotiz im jeweiligen Dev-Root und die portable
Abstimmungsregel in `DEVELOPMENT.md`. Die lokale Notiz selbst ist kein Payload.
Dev führt keine Verhaltenstests, Commits oder Apply-Aufrufe aus. Das Bundle
enthält getrennte Stufen und wird genau einmal an Exchange übergeben.
