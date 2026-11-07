# Anhang C – Szenario-/E2E-Zuordnung

Unveränderte fachliche Zuordnung; [Zentraler Fortschritt](../SpecRoad_Implementierungsplan.md). Zeitbezogene Übergabeangaben ersetzen den dortigen aktuellen Stand nicht.

## Anhang C – Szenario-/E2E-Zuordnung

Die Bezeichnungen und Identitäten stammen aus der Spezifikation. Alle Szenarien wachsen mit den genannten Features und werden in `20.b` gekoppelt abgenommen. Reine Ausgabeanteile werden gemäß TD-001 nicht automatisiert geprüft; insbesondere ist der originale Darstellungs-Bytevergleich in Szenario 0012 ausdrücklich ausgenommen.

| Szenario / E2E | Gegenstand | Führende Meilensteine |
|---|---|---|
| `SR-SCN-0001` / `SR-E2E-0001` | Projekt initialisieren | 1, 2, 7 |
| `SR-SCN-0002` / `SR-E2E-0002` | Anforderung erfassen | 2, 4, 7, 12 |
| `SR-SCN-0003` / `SR-E2E-0003` | Qualitätsfehler erkennen | 4 |
| `SR-SCN-0004` / `SR-E2E-0004` | Traceability erklären | 3, 8, 12 |
| `SR-SCN-0005` / `SR-E2E-0005` | Änderung vergleichen | 8, 10, 15, 17 |
| `SR-SCN-0006` / `SR-E2E-0006` | Release Readiness prüfen | 12, 13 |
| `SR-SCN-0007` / `SR-E2E-0007` | Evidence veraltet | 12 |
| `SR-SCN-0008` / `SR-E2E-0008` | Baseline erzeugen | 10 |
| `SR-SCN-0009` / `SR-E2E-0009` | KI-Vorschlag prüfen | 18 |
| `SR-SCN-0010` / `SR-E2E-0010` | KI-Vorschlag übernehmen | 5, 18 |
| `SR-SCN-0011` / `SR-E2E-0011` | CI-Gate | 1, 4 |
| `SR-SCN-0012` / `SR-E2E-0012` | Spezifikation rendern | 11; TD-001 |
| `SR-SCN-0013` / `SR-E2E-0013` | Chatbot-Sandbox-Roundtrip | 15, 18, 20 |
| `SR-SCN-0014` / `SR-E2E-0014` | Bestehendes Artefakt direkt bearbeiten | 5, 7 |
| `SR-SCN-0015` / `SR-E2E-0015` | Parallel neue Artefakte erzeugen | 2, 17 |
| `SR-SCN-0016` / `SR-E2E-0016` | Prozessabbruch wiederherstellen | 5 |
| `SR-SCN-0017` / `SR-E2E-0017` | Projekt migrieren | 16 |
| `SR-SCN-0018` / `SR-E2E-0018` | Suspect Relation prüfen | 7 |
| `SR-SCN-0019` / `SR-E2E-0019` | Dokument komponieren | 11; TD-001 |
| `SR-SCN-0020` / `SR-E2E-0020` | ReqIF austauschen | 14 |
| `SR-SCN-0021` / `SR-E2E-0021` | Testergebnisse übernehmen | 12 |
| `SR-SCN-0022` / `SR-E2E-0022` | Quellcode verknüpfen | 12 |
| `SR-SCN-0023` / `SR-E2E-0023` | Eigene Sicht erzeugen | 11; TD-001 |
| `SR-SCN-0024` / `SR-E2E-0024` | Branches semantisch mergen | 17 |
| `SR-SCN-0025` / `SR-E2E-0025` | Agent erkundet und wiederholt sicher | 1, 2, 5, 7, 18 |
| `SR-SCN-0026` / `SR-E2E-0026` | Produktkonfiguration ableiten | 9, 10, 11, 12, 13 |
| `SR-SCN-0027` / `SR-E2E-0027` | Unabhängige Aufrufe und Pfadwechsel | 1, 6 |
| `SR-SCN-0028` / `SR-E2E-0028` | Sandbox aus Sicherungsstand ersetzen | 6, 15 |
| `SR-SCN-0029` / `SR-E2E-0029` | Preflight bei Recoverybedarf | 5, 6 |
| `SR-SCN-0030` / `SR-E2E-0030` | Weiches Budget überschritten | 5, 6 |
| `SR-SCN-0031` / `SR-E2E-0031` | Cache fehlt oder ist veraltet | 6 |
| `SR-SCN-0032` / `SR-E2E-0032` | Umgebung und tatsächlicher Verbrauch | 6, 20 |
| `SR-SCN-0033` / `SR-E2E-0033` | Vollständig trotz weichem Budget | 6, 20 |
| `SR-SCN-0034` / `SR-E2E-0034` | Fortsetzung über mehrere Prompts | 6, 20 |
| `SR-SCN-0035` / `SR-E2E-0035` | Prompt und Actor bleiben kontrolliert | 6, 18 |
| `SR-SCN-0036` / `SR-E2E-0036` | Wiederholung und veränderte Zielbasis | 5, 6 |
| `SR-SCN-0037` / `SR-E2E-0037` | Historische Nachweise unverändert migrieren | 16 |
| `SR-SCN-0038` / `SR-E2E-0038` | Merge- und Proposal-Verträge durchgängig | 17, 18 |
| `SR-SCN-0039` / `SR-E2E-0039` | Mehrsprachig authoren | 2, 7, 11 |
| `SR-SCN-0040` / `SR-E2E-0040` | Sprachpolicy anwenden | 4, 11 |
| `SR-SCN-0041` / `SR-E2E-0041` | Sprachen tatsächlich erkennen | 19 |
| `SR-SCN-0042` / `SR-E2E-0042` | Unsicherheit und Fehlkennzeichnung | 19 |
| `SR-SCN-0043` / `SR-E2E-0043` | Mehrere Analyzer austauschen | 19 |
| `SR-SCN-0044` / `SR-E2E-0044` | Core ohne Zusatzpakete | 1, 19, 20 |
| `SR-SCN-0045` / `SR-E2E-0045` | Analyzerarbeit fortsetzen | 6, 19 |
| `SR-SCN-0046` / `SR-E2E-0046` | Entwurfsmetadaten migrieren | 4, 14, 16, 19 |
