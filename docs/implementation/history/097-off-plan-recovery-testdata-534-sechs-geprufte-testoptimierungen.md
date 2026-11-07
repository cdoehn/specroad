# OFF-PLAN RECOVERY-TESTDATA-534 — sechs geprüfte Testoptimierungen

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN RECOVERY-TESTDATA-534 — sechs geprüfte Testoptimierungen

Ausdrücklicher Nutzerauftrag vom 1. November 2026: die fünf analysierten
Registry-Verkleinerungen und die Wiederverwendung der Writer-Kontrollspuren
zusammen lokal vorbereiten. Quelle ist das erfolgreiche, saubere Result von
Bundle 533, `specroad-apply_Result_075934_1101_61403b.zip`, SHA-256
`eed8bde3296ca54658bcfb0bd45c062b8efb0c419cd4a1bd83eb4da63dc7dc1b`,
Abschlusscommit `a0efb049c4dff94ea7f1deafe80f8eccd527d04a`.

Die kleinen, nativ geprüften synthetischen Registries aus RECOVERY-FIXTURE-533
werden ausdrücklich in den Schemafehler-, Work-Ergebnis-, Work-Ausführungs-/
Fortschritts-/Owner-/Bindungs-, Proposal-Historien- und nativen Restore-Crash-/
I/O-/Dateitests gewählt. Geteilte Helfer erhalten optionale Parameter; ihre
bisherigen Standardaufrufe bleiben erhalten. Beide geänderten Projektdateien,
Originaljournale, native Proposal-Prüfungen, Fehlerstellen, Fortschritt und
sämtliche fachlichen Assertions bleiben bestehen.

Die Multi-Writer-Kontrollspur wird pro Worker und Modullauf einmal nativ
erzeugt; die drei Recovery-Kontrollspuren werden je Szenario bei Bedarf erzeugt.
Nur unveränderliche JSON-Ereignisbeschreibungen werden wiederverwendet, jeder
Aufrufer erhält eigene dekodierte Daten. Jeder eigentliche Crashfall erzeugt
weiterhin sein eigenes Projekt und führt alle bisherigen Prozessabbrüche aus.
Die vollständigen vier Recovery-Gruppen und ihre Abbruchstellen bleiben erhalten.

**Lokale Abnahme abgeschlossen:** 760 Tests aus 25 vollständigen Testdateien,
Exit 0, CPython 3.14.4, vier worksteal-Worker, ungefiltert. Pytest-Laufzeit
**2748.0 Sekunden (45 Minuten 48 Sekunden)**; Abschluss
`2026-11-01T11:29:46.145168+00:00`. Alle 2.280 Setup-/Call-/Teardown-Phasen sind in
der bestehenden Exchange-Messhistorie gültig gespeichert (Lauf 56).
Vollständige Collection: 22.718 unveränderte Testidentitäten, gültiger Katalog,
keine ausgeführten Testkörper bei der Collection. Der Quellstand ist seit
dieser Abnahme unverändert. Kein Wiederholungslauf und kein zusätzlicher
Dev-Volltest für die Paketierung; dies ist ein gezielter Teiltestnachweis.

**Gemessene Wirkung der sechs Bereiche** (Setup + Call + Teardown, jeweils eine
Nachkommastelle; Summen sind addierte Einzeltestzeiten, keine parallele Wandzeit):

| Bereich | Tests | Summe historisch (s) | Summe aktuell (s) | längster Test historisch → aktuell (s) |
|---|---:|---:|---:|---:|
| Schemafehler | 6 | 8502.8 | 1016.9 | 5278.8 → 643.0 |
| Work-Ergebnisse | 14 | 10917.0 | 508.9 | 1798.8 → 65.0 |
| Work-Ausführung, Fortschritt, Owner, Bindung | 148 | 16401.4 | 584.0 | 677.1 → 31.4 |
| Proposal-Historie, Abschluss, Restore | 42 | 8682.5 | 266.2 | 752.7 → 33.2 |
| Native Restore-Crash-, I/O- und Dateifälle | 191 | 9920.6 | 671.5 | 203.3 → 47.3 |
| Writer-Kontrollspuren | 27 | 4264.8 | 1764.0 | 385.8 → 151.3 |

Die historischen Werte stammen aus den jeweils neuesten gültigen Versuchen
vor der Änderung; Originalversuche, Quellbindungen und Historie bleiben erhalten.
Andere Workerzahl und unbekannte damalige Rechnerlast: **kein kontrollierter
Benchmark, keine garantierte Beschleunigungsquote**. Der teure Altstand wurde
nicht erneut ausgeführt. Die unveränderten Planning-Work-Regressionsfälle können
weiterhin lange dauern (im aktuellen Lauf maximal 836.0 Sekunden); dieser
Auftrag verändert dafür weder Produktimplementierung noch Prüfaussagen.

Quellbindung der Abnahme: `7a2475e8a4111e66d8c3b3d8556aad21df4649bb9f31a550d29f831fbf3acb67`.
Katalogdatei-SHA-256: `7e9852f94cebb97d1a2491c6f7651c21184d7e495163be3a36b2428068027231`.
Auswahlbericht-SHA-256: `9f68c7a9357f0c74477d0609a4f6067fb9b117887f6f4df9e4056288e3358dea`.
Beobachtungs-SHA-256: `c6009f27346fe408ce6bb26f2248160d60a8f2fc7901b2280092fef7fb8f1c38`.
Zeitvergleich-SHA-256: `06a277555591fba4b9200e0771f35849a6e1f5ea5539ee601b3eed1f6078d30a`.

Der anschließende ausdrückliche Nutzerauftrag liefert genau einen technischen
OFF-PLAN-Commit über PatchHarbor. Apply verwendet unverändert die fällige
N=3-Gruppe **2** (Commitsequenz **245**) mit einem erst vor Teststart erfassten
aktuellen Messsnapshot. Aus der vollständig gültig gemessenen aktuellen
Testmenge entfallen die langsamsten `floor(N/5)` Tests; neue oder ungültig
gemessene Tests bleiben zugelassen. Danach wird nur die verbleibende fällige
Gruppe parallel geprüft. Keine feste Ausschlussliste, kein zusätzlicher Volltest,
keine CI, keine Änderung an Control oder Watcher. Nur nach erfolgreichem Gate
erzeugt Apply den Commit und setzt den Bundle-Abschlussmarker.

Commit: `OFF-PLAN RECOVERY-TESTDATA-534 perf(tests): Sechs Recovery-Testaufbauten beschleunigen`.
Apply-Abschluss RECOVERY-TESTDATA-534: fällige Gruppe bestanden; Bundle 534 abgeschlossen.

Produktcode, Spezifikation, Distributionsregistry, Testkatalog, Testnummern,
historische Baseline, Testrotation und Ausschlussregeln bleiben byteidentisch.
Produktfortschritt bleibt **655/900**, nächster Produktcommit **15.n.R**.
Kein offener Produktplanschritt wird durch diese Testoptimierung abgeschlossen.
