# Bundle 627 — vollständiger Zielstand 17.l.W

7. November 2026. Maßgebliche saubere Quelle ist
`specroad-apply_Result_120609_1107_af0963.zip`, SHA-256
`1b261d7b928893600effc8ea10355c803c5e9a3450dc6195b0a0a64b4e4bd2d0`,
HEAD `2d073d1f4e95ad6705ce3def1237c8af73e33584`.
Der native Abschluss von Bundle 626 belegt die technische Testkorrektur;
Produktstand davor: 17.k.C, 726/900. Es wird kein erfolgreicher Commit wiederholt.

Nach der zulässigen Detailentscheidung [MERGE-WORK-627](../decisions/merge-work-627.md)
folgt genau der vollständige W-Stand: alle vier nativen Quellenarten,
öffentliche passive Planung, vollständige native Inventur/Konflikt-/Metadaten-/
Zielphasen und deren persistierte Work-Fortsetzung. Im Plan bleibt nur der
Fortschritt; technische Umsetzung und Nachweisgrenzen stehen hier.

Die gemeinsame Vorbereitung benutzt vorhandene Merge-Engines; der externe
Work-Store bindet originale Quelldateien, History und gegebenenfalls den
Auflösungsplan. Blockweise Integritätsprüfung, Phasen und abschließende
unabhängige Nachrechnung gehören zum vollständigen Auftrag. Wiederaufnahme
liest keine gespeicherten Quellpfade automatisch neu. Negative Prüfungen
liefern keine Zielbytes oder Schreibbefugnis. Der bestehende Writer bleibt
maßgeblich; dieses passive Ergebnis autorisiert ihn nicht.

45 neue vorbereitete Verhaltenstests prüfen Quellenparität, unterschiedliche
Fortsetzungsschritte, Originalplanbytes, echte Konflikte/Änderungen,
Quellenänderung nach Versiegelung, manipulierte Phasen, Eingaben über 64 KiB,
öffentliche argv-/Request-Aufrufe, vollständige Work-Lieferung, Abbruch und
Grenzen. Maschinenverträge, Registry und echte öffentliche Beispiele sind
mitgeführt. Kleine native Fixtures vermeiden unnötige Vollregistry-Kopien;
volle vorhandene Größen-/Quellen-/Writerreferenzen bleiben in der Pflichtauswahl.

Jede Stage hat ein eigenes Apply-Gate aus Pflichtauswahl plus gefilterter
fälliger N=3-Gruppe. Alle neuen/geänderten Testdateien sowie relevante
Merge-, Work-, CLI-, Schema-, Snapshot-, Bundle-, Baseline-, Restore- und
Migrationsregressionen sind verpflichtend. Dev führt keine Testkörper,
Fixtures oder Test-Unterprozesse aus. Syntax und reine Collection sind keine
Verhaltensabnahme. Zähler 727/900 und Checkbox W werden erst mit erfolgreichem
Apply-Gate und tatsächlichem Commit wirksam; ein grüner Klärungspräfix genügt nicht.

17.l.R/C bleiben offen: öffentliche Merge-Apply-Gesamtintegration, portable
Work-Gesamtintegration, vollständige Manipulations-/Fehler-/Resume-Matrix und
Bereinigung. M17 ist nicht abgeschlossen. Vollsuite, Plattformnachweise,
Produktfreigaben und menschliche Reviews werden nicht behauptet.
