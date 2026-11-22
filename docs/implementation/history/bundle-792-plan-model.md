# Bundle 792 — Planmodell und explizite Projektfähigkeit

22. November 2026. Quelle ist das native erfolgreiche Result mit SHA-256
`bc2af7a0de2ae4dbab8d4f21740398cf4d59889efbb896c3c9fe5cb01866a7b8`.
Es bestätigt ausschließlich den Dokumentationscommit IMPLEMENTATION-PLANS-791
mit 7.731 bestandenen Tests und sauberem Stand
`8ca0287085b3a0a7a68cb70033db3db4a02beef3`. Kein offener Korrekturpräfix.

Diese Stage: **21.a.R**. Fortschritt und Häkchen in ihrem Zielbestand gelten
jeweils erst nach ihrem eigenen erfolgreichen Apply-Gate und Commit.
Dev führt keine Testkörper, Fixtures oder Test-Unterprozesse aus: **tests_run=0**.
Reine Collection, Syntax-, Schemaform-, Paket- und passive Übergabeprüfungen
sind keine bestandene Verhaltensabnahme. Der historische 0.2-Migrationsvertrag
behält den geprüften Hash
`e844cb7008efd11ff58bd09c54e07822d7a22b540acc2164446fa12aa2ae4f36`.

## Vollständige Gruppe 21.a

- W registriert `implementation_plan`/`plan_entry` mit zufälligen 128-Bit-IDs,
  geschlossenen Feldschemas 0.3, gemeinsamem Metadaten-/Scopevertrag und genau
  einem Markdown-Dateiträger. Einträge besitzen keine eigene normative JSON-Datei.
  Native Modellprojekte ohne Plan behalten ihre vorhandenen Artefaktversionen.
  Ein Plan in einem alten Projekt verlangt explizit Migration; vorhandene
  Markdownquellen verlangen sichtbar den erst in 21.b vorgesehenen Parser.
- Der zusätzliche gerichtete Projektübergang 0.2 → 0.3 läuft durch den vorhandenen
  Migrationsplan, verifizierten Originalbackup und normalen Writer mit dessen
  Sperre, Markern, Receipts und nativen Zielprüfungen. Nur die ausdrücklich
  gelieferte Konfigurationsversion darf sich fachlich ändern; alle übrigen
  ursprünglichen Dateien sind geschützt. Keine implizite Konvertierung alter
  Baselines/Evidence, keine Review- oder Schreibfreigabe durch Planflags.
  Fehlende Dienste/Originale bleiben sperrend. Rückmigration wird nicht erfunden.
- Die tatsächlich fehlende Altanforderung `config show` erhält einen nativen
  lesenden Befehl für Projektkonfiguration, vollständige bekannte Defaults und
  Herkunftsketten einschließlich CLI-Overrides. Er lädt kein Artefaktmodell.
  Profile werden als Auswahl offengelegt; ihre Komposition ist kein behaupteter
  Befund dieses Metadatenbefehls. Beschädigte Artefakte blockieren ihn nicht.
- R prüft doppelte Artefakt-, Relations-, lokale Display- und Claim-IDs sowie
  Reservierungen gegen aktuelle und historische IDs. No-plan-Projekte mit 0.3
  können auch über die vorhandenen Snapshot-, Bundle- und Formatpfade gelesen
  werden. Die vorbereiteten Originalerhaltungstests umfassen verschachtelte
  Baselines und passed/failed/incomplete/skipped-Evidence. Modul und PYZ müssen
  dieselben Schemas liefern; synthetische Akteure sind keine menschlichen Reviews.
- C trennt die reine effektive Konfigurationsprojektion vom I/O-Handler und
  zentralisiert die unveränderte ursprüngliche Artefakttypmenge. Alle W/R-Tests
  bleiben bytegleich; Fachverhalten und Fehlersignale werden nicht verändert.

Die gemeinsame eingebaute Schemainterpretation unterstützt `uniqueItems` mit
JSON-Gleichheit für Kinder-/Contributorlisten. Unbekannte Schlüssel und ungültige
Keywordformen bleiben abgewiesen. Alte ausgegebene Schemas bleiben bytegleich;
nur der vorhandene Change-Plan-Vertrag ergänzt den neuen nativen Migrationsschritt.
Die passiven Apply-/Control-Planpfadkataloge erkennen M21; kein Dienst wird gestartet.

## Übernommener Altumfang

Die folgenden Katalogfälle behalten sämtliche bisherigen Fixture-/Testreferenzen.
Zusätzlich sind vorhandene vollständige Native-/Integrationsoracles und die neuen
Plan-/Konfigurationsfälle an ihre jeweiligen Fachgruppen gebunden. Alte Notizen
über damals noch fehlende Module bleiben als historische Aussagen erhalten;
sie sind kein Grund, vorhandene spätere Implementierung wegzulassen. Der Bericht
macht keinen neuen Erfolg aus einem alten grünen Result. Die Pflichtauswahl
umfasst auch direkte/indirekte Testhelferverbraucher und die betroffenen Writer-,
Migrations-, Modell-, Profil-, Scope- und Metadatenregressionen.

| Übernommene Fälle | Implementierung und gebundene Oracles |
|---|---|
| 0001–0003 | Native Bootstrap-/Abbruch-/Receiptfälle; Primärdokument und unveränderter Konfliktbestand |
| 0004–0008 | Rootauswahl, Konfigurationsfelder und Präfixe; aktuelle Modell-/Options-/Preflightfälle |
| 0009 | Neuer lesender Config-Befehl, Default-/Override-/Quellen- und No-model-Oracles |
| 0010, 0022–0025 | Bestehende Format-/Normalisierungs-CLI, transaktionale Zielbindung und echte Format-Roundtrips |
| 0011–0017 | Gemeinsame Ressourcen-/Schemas-/Originalformatleser und JCS; additiver Projektübergang und Plantypen |
| 0018–0020, 0037 | Namespaced Metadaten, Provenance/Relationsfelder, JCS-/Modellwurzel- und vollständige Modellgates |
| 0027–0029, 0031–0032 | Projekt-/Typpräfixe, aktuelle/historische Reservierung, native Identity-Indizes und Importpfade |
| 0033–0036 | Native Audit-/Change-/Merge-/Migrationsregeln; Originalrevisionen und unveränderte Historie |

Die aktive Restmatrix bleibt unverändert: Parser 21.b, Authoring 21.c,
Plan-Graph-/Coverageintegration 21.h und die weiteren konkret geplanten
Integrationsgruppen sind nicht durch Feldprojektionen ersetzt. 21.v bilanziert
alle Katalogreste; 21.w/x und 20.n liefern die aktuelle Gesamt-/Plattform-/Release-
Abnahme. Bereits vorhandene Schema-/Writerfunktionen bleiben verpflichtend.
Menschliche Reviews bleiben im bestätigten Schlussblock 19.t/y und 20.b/d/k/l/n.

Nach erfolgreichem 21.a.C sind **891/996** Produktpositionen abgeschlossen;
als nächstes folgt unverändert **21.b.W**, danach die übrige priorisierte Folge.
Es gibt keine neue normative Detailentscheidung und keinen Klärungscommit.
