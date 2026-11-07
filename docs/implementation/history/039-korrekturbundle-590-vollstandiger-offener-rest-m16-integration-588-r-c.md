# Korrekturbundle 590 — vollständiger offener Rest M16-INTEGRATION-588.R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 590 — vollständiger offener Rest M16-INTEGRATION-588.R/C

Nativ geprüftes Fehler-Result:
`7a7852b33536cd5cb59920e71a799d4a72f0c37baa40de2d89c1eec83c299c97`,
HEAD `dd85dc712417ccc87e604d5b7563db8ebd1dbd23`, Dirty-Fingerprint
`9b0978451db564b8`. Bundle 589 schloss W nach 9530 bestandenen Tests ab.
R endete am 4. November 2026 um 18:12:52 UTC mit 9533 bestandenen Tests
und fünf Fehlern; C begann nicht. Snapshot und nativer Fortschrittsbeleg
entsprechen exakt dem angekündigten R-Stand. Der erfolgreiche Klärungs-
und W-Commit bleiben erhalten; nur R/C werden vollständig fortgeführt.

Vier Fehler stammen aus dem positiven Work-Pakettest: Sein Ausgabeordner
war zugleich Vorfahr des Work-Verzeichnisses. Die bestehende Sicherheits-
prüfung verweigert diese Überlappung korrekt. Der Test verlangt weiter die
Abweisung und verwendet danach einen eigenen externen Paketordner; Export,
Löschung der alten Work-Kopie, Restore, jede Phasengrenze, frische Autorität
und echte Migration samt Replay bleiben vollständig im Test.

Der historische Bundle-/Restore-Rundweg scheiterte beim Export mit
unsupported_schema_version. Die native Relationsreview-Beobachtung leitete
bereits qualifizierte unveränderliche Originale nochmals in den aktuellen
Datensatzvalidator. Sie akzeptiert jetzt ausschließlich die schon durch
LegacyArtifact/SourceRelations gebundenen Originale und prüft aktuelle
Datensätze unverändert. Alte Revieworiginale werden nicht als aktuelle
Reviewentscheidungen ausgewählt. Kanten mit historischen Endpunkten
behalten eine ausdrückliche fehlende aktuelle Kontextqualifikation.
Regressionen prüfen Originalbytes, historische Navigationskanten, fehlende
aktuelle Freigabe und weiterhin abgewiesene ungültige aktuelle Datensätze.

Keine neue Spezifikationsentscheidung: Q.5.3, Spezifikation 0.2.61 und
sämtliche aktiven Katalogbindungen bleiben unverändert. Beide offenen IDs
und implementation-Rollen behalten die vollständigen ursprünglichen
Pflichtauswahlen. Zusätzlich laufen die gesamten Relationsreview- und
Legacy-Manifestregressionen. R/C haben getrennte Gates der Gruppen 0/1.
C bleibt strukturell, mit bytegleichen R-Tests und allen 24935 verfügbaren
Tests als ungefilterter Pflichtauswahl. Dev führt keine Verhaltenstests aus.
M16 bleibt bis zum tatsächlichen erfolgreichen C-Commit und gebundenen
Vollsuite-Ergebnis offen; Produktstand 693/900. Keine Automatik-/Budgetänderung.
