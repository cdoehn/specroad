# AUDIT-VALIDATION-03.U – vollständige unabhängige Referenzbefunde

**Entscheidung vom 5. Oktober 2026: begrenzte Aggregationslücke bestätigt.**
Bei strukturell gültigen, eindeutig identifizierbaren Eingaben wird nur die erste
fehlende Relations- oder Feldreferenz diagnostiziert. Weitere unabhängige Fehler
derselben Referenzstufe fehlen. Das widerspricht der bereits zugesagten
Mehrfachfehlerabnahme von 4.p.R. Dagegen bleibt es richtig, Graph- und Fachgates
nach einer fehlgeschlagenen Struktur-/Referenzstufe zu sperren.

Die Untersuchung gehört zum aktiven
[Implementierungsplan](../implementation/SpecRoad_Implementierungsplan.md#audit-nacharbeiten).
Sie verändert keine Produktquelle, keinen Regressionstest und keine
Requirementbewertung. Produktstand 237/885 und die Sperre von 5.t.W bleiben
bestehen. Die drei U-Untersuchungen sind damit fachlich ausgewertet; als Nächstes
beginnen die konkretisierten Korrekturen mit AUDIT-VALIDATION-01.W.

## Bindung und Methode

- Result: `specroad-apply_Result_004435_1005_821734.zip`.
- Result-SHA-256: `0b7c4d31c0f9c68bb091292c2cbffdb98b8b56fbe7e4fa0dcc3c858b3d89f5bf`.
- Basiscommit: `06d514f4f413e3bb595b911be51a2fc06e4be947`.
- Spezifikations-SHA-256: `128fed57c038ab1af4a3bdbf70d65024c62f09f92866094caf802b8b807bca93`.
- Alle 1.451 Snapshotdateien stimmen bezüglich Git-Objektkennung, Größe,
  Dateityp, Ausführbarkeitsmodus und lokalen Bytes überein. Das Result ist sauber.
- [Reproduktionsprogramm](SpecRoad_AUDIT_VALIDATION_03_U_probe.py): zwölf Fälle
  mit vier parallelen, per `spawn` isolierten Workerprozessen.
- [Gebundene Beobachtungen](SpecRoad_AUDIT_VALIDATION_03_U_observations.json):
  vollständige Eingabewerte, Rohbyteabweichungen, Eingabehashes, Rückgaben und
  Probe-/Quellbindung.

Die Probe erstellt eigene temporäre Projekte mit echten Goal-, Component- und
Interfaceartefakten und verwendet das ausgelieferte `core@0.2.0`. Sie ruft
`RelationReferences`, `validate_model`, `assess_validation` und
`validate_project_read_only` auf. Keine zusätzliche Fachgateantwort wird
injiziert. Jede Modellbewertung wird mit umgekehrter Dokumentreihenfolge
wiederholt, um die Unabhängigkeit von der Lieferreihenfolge zu beobachten.

Zwei Gegenproben bewerten jeweils die unveränderten einzelnen Quellen, deren
Ziel auch im vollständigen Fixture fehlt. Ihre tatsächlich erzeugten Diagnosen
werden mit `assess_diagnostics` zusammengeführt. Das sind ausdrücklich andere,
kleinere Eingabemengen; daraus wird kein erfolgreicher Gesamtnachweis abgeleitet.
Eine weitere Gegenprobe isoliert eine tatsächlich typwidrige Relation mitsamt
ihrem vorhandenen Endpunkt, die hinter der ersten fehlenden Relation liegt.

## Beobachtete Mengen und Abbruchgrenzen

| Fixture | Unabhängig vorhandene Fehler | Tatsächliche öffentliche Diagnosemenge |
|---|---:|---|
| Vollständig geschlossener Graph mit sieben Artefakten, Relations- und Interfacefeldzielen | 0 | 0, Code 0, vollständige Prüfung. |
| Zwei Quellen mit jeweils einem fehlenden Relationsziel | 2 | Ein SRV020 für die erste Quelle, `/relations/0/target`, Code 3. |
| Eine Quelle mit zwei fehlenden Relationszielen | 2 | Nur der erste Relationspointer, Code 3. |
| Zwei Quellen verweisen auf dasselbe fehlende Ziel | 2 Fundstellen | Nur die erste Fundstelle; die zweite wird nicht erreicht. |
| Fehlendes Ziel und unabhängige typwidrige Relation | 2 | Nur SRV020; die isolierte zweite Quelle liefert tatsächlich SRV021. |
| Interface ohne beide Componentziele | 2 | Nur `/source_component`, SRV020; `/target_component` fehlt. |
| Fehlendes Relationsziel und zwei fehlende Interfacefeldziele | 3 | Nur das erste Relationsziel; die Feldreferenzprüfung wird nicht erreicht. |
| Zwei Dateien mit Parsefehlern | 2 | Beide SRV001, Code 3; nachgelagerte Abhängigkeitsprüfung gesperrt. |
| Zwei Artefakte mit je einem Schemafehler | 2 | Beide SRV002 mit Artefakt und `/title` beziehungsweise `/owner`, Code 3. |
| Zwei unbekannte angeforderte IDs bei ansonsten gültigem Modell | 2 | Beide SRV140, Code 3; keine erfundenen Quelldateien oder Pointer. |
| Zwei fehlende Relationsziele bei Auswahl nur der ersten Quelle | 2 im strukturellen Gesamtscope | Wieder nur die erste Fundstelle; Auswahl hebt den strukturellen Gesamtscope nicht auf. |
| Relationsquelle plus unlesbare mögliche Zieldatei | Nur Parsefehler sicher bewertbar | Ein SRV001; keine Behauptung, das noch unlesbare Ziel sei nachweislich nicht vorhanden. |

In allen zwölf Fällen stimmen öffentliche Projektbewertung und direkte
Modellbewertung vollständig überein. Umgekehrte Dokumentreihenfolge verändert
kein Assessment. Das beweist vorhandene Stabilität, aber keine Vollständigkeit
der erzeugten Referenzdiagnosen.

Bei zwei unabhängig fehlenden Quellen und beim gemeinsamen fehlenden Ziel
entstehen in den isolierten Gegenproben jeweils zwei echte SRV020-Fundstellen.
`assess_diagnostics` erhält beide, zählt zwei errors und bewahrt Code 3 sowie
den unvollständigen Status. Der Verlust entsteht somit vor der
Diagnoseaggregation; der Aggregator entfernt diese Befunde nicht nachträglich.
Auch die vorhandenen Summaryzahlen sind korrekt für die tatsächlich erzeugte
Menge. Die Reparatur muss die fehlenden Befunde erzeugen, nicht nur den Zähler
erhöhen oder zusätzliche Meldungen erfinden.

Alle Projektdateien, Verzeichnisse, Modi und Bytes bleiben unverändert. Es gab
keinen versuchten Produktwrite und keinen Prozess-/Netzwerkaufruf innerhalb der
beobachteten Produktfunktionen. Die Fixtures und Worker gehören ausschließlich
dem Untersuchungsprogramm. Die Beobachtungen sind historische Daten; es gibt
keinen neuen Regressionstest, der die fehlenden Diagnosen festschreibt.

## Vertrag und bestehende Nachweise

4.p.R verlangt ausdrücklich: „Unbekannte IDs und mehrere gleichzeitige Fehler
vollständig erhalten“. Seine Abnahme vergleicht Codes, Orte, Mengen und Status.
Eine Beschränkung auf bereits eingespeiste Testdiagnosen oder auf genau den
ersten Fehler innerhalb der Referenzstufe ist dort nicht festgelegt. Die
verbindliche Abnahme betrifft bereits vorhandene Validierung, nicht erst eine
spätere CLI oder das Diagnose-Spooling aus M6.

Die zugeordneten Requirements ergänzen diese Abnahme:

- SR-REQ-0087 und 0088 verlangen verfügbare Parsepositionen beziehungsweise
  Artefakt-ID und Feldpointer. Die vorhandenen positiven Gegenproben bleiben
  gültig; die zusätzliche Referenzfundstelle benötigt dieselbe Bindung.
- SR-REQ-0089–0091 definieren Diagnosefelder, Ursprung und Schwere. Sie erlauben
  keine erfundene Ersatzdiagnose für eine noch nicht geprüfte Abhängigkeit.
- SR-REQ-0092 verlangt stabile fachliche Reihenfolge. Ein stabil ausgewählter
  einzelner Fehler erfüllt nicht automatisch die zusätzliche Mengenabnahme.
- SR-REQ-0098 verlangt stabile Codes; fehlende Ziele und typwidrige Relationen
  sollen weiterhin SRV020 beziehungsweise SRV021 verwenden.
- SR-REQ-0099 verlangt die Zusammenfassung der tatsächlich geprüften Artefakte
  und Befunde. SR-VER-0007 verlangt passende maschinenlesbare Diagnosen.

Keines dieser einzelnen Requirements formuliert für sich ein unbegrenztes
Weiterrechnen trotz beschädigter Eingangsdaten. Die bestätigte Korrektur folgt
aus der konkreten Mehrfachfehlerzusage von 4.p.R für unabhängig bewertbare
Fundstellen bei erfüllten Strukturvoraussetzungen. Sie ist keine neue allgemeine
Pflicht, nach jedem Fehler beliebige nachgelagerte Gates auszuführen.

Alle acht zugeordneten SR-TC-Manifeste bleiben `partial` und werden in diesem
U-Bundle nicht hochgestuft. Ihre Voraussetzungen nennen explizite Diagnosedaten
und bereits geladene gebundene Modellberichte. Bestehende Tests wie
`test_two_parse_failures_are_both_retained`,
`test_parse_and_schema_failures_coexist`,
`test_all_unknown_selected_ids_are_reported_without_counting_them` und
`test_independent_gate_errors_are_all_retained` belegen diese funktionierenden
Teilumfänge. `test_graph_error_has_known_source_identity_from_bound_report`
prüft einen einzelnen Graphbefund. Diese Tests ersetzen keinen Nachweis mehrerer
unabhängiger fehlender Relations- und Feldziele in einem realen Modellbericht.

## Ursache und Korrekturgrenze

`graph/references.py::RelationReferences` baut einen vollständig aufgelösten
Relationswert auf. Bei der ersten fehlenden Zielidentität, typwidrigen Relation
oder anderen Integritätsverletzung wirft es einen `ModelError`.
`validation/core.py` übernimmt genau diesen Fehler und kehrt mit gesperrtem
`graph_and_semantics` zurück. Nach erfolgreichen Relationsreferenzen beendet
`validation/_model_checks.py::_foreign_edges` auch die Feldreferenzen beim
ersten fehlenden oder typwidrigen Ziel. Deshalb verschwinden weitere,
unabhängig prüfbare Fundstellen vor `assess_validation`.

Ein Konstruktor, der nur vollständige gültige Relationswerte erzeugen darf,
muss nicht plötzlich einen ungültigen Teilgraphen liefern. Die gemeinsame
Validierung benötigt stattdessen eine vollständige Beobachtung der sicher
bewertbaren Referenzfehler. Die strikte Konstruktorgrenze und die anschließende
Sperre der Graph-/Fachgates bleiben erhalten. Insbesondere werden aus
unlesbaren, schemawidrigen oder mehrdeutig identifizierten Eingaben keine
verlässlichen Zielmengen geraten.

## Bestätigte Nacharbeit

Der Plan erhält AUDIT-VALIDATION-03.W/R/C: zuerst alle unabhängig fehlenden
Relations- und Feldziele einer strukturell gültigen und eindeutig indexierbaren
Eingabemenge sammeln; anschließend gemischte Typ-/Identitätsfehler,
Mehrfachfundstellen, Auswahlgrenzen und deterministische Diagnosebindungen
absichern; danach Referenzbeobachtung und strikte Graphkonstruktion gemeinsam
strukturieren. Bei Referenzfehlern bleiben Graph- und Fachstufen gesperrt,
Code 3 erhalten und Schreib-/Freigaberechte falsch.

Die Reihenfolge nach diesem U-Result ist AUDIT-VALIDATION-01.W/R/C,
AUDIT-VALIDATION-02.W/R/C, dann AUDIT-VALIDATION-03.W/R/C. Keine Reparatur wird
vorab installiert oder durch eine dokumentierte U-Entscheidung als umgesetzt
ausgegeben.

Commit-Message dieses U-Bundles:
`docs(validation): record incomplete reference diagnostic sets`.
Erst das erfolgreiche Apply-Result bestätigt den U-Commit.
