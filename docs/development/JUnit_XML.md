# JUnit-XML lesen (12.f.W/R/C)

`specroad.verification.JUnitDocument(raw)` liest ein vollständiges XML-Dokument
aus ausdrücklich übergebenen `bytes`. Es öffnet keine Datei und startet weder
Tests noch einen Unterprozess. 12.g.W ergänzt die unten beschriebene explizite
Zuordnung zu Evidence-Kandidaten. Globale Import-CLI und Veröffentlichung
folgen in eigenen Planschritten.

```python
from specroad.verification import JUnitDocument, JUnitLimits

document = JUnitDocument(report_bytes, limits=JUnitLimits(max_depth=32))
parsed = document.data
original = document.source_bytes
original_sha256 = document.sha256
```

Das Ergebnis ist ein eigenes Wertobjekt. `data` liefert jeweils neue veränderbare
JSON-Daten; Änderungen daran verändern das Dokument nicht. `source` bindet Größe
und SHA-256 der unveränderten Eingangsbytes. `format_version` ist `junit-core-v1`.
Ein boolescher Erfolgsgebrauch des Dokuments ist unzulässig: ein gelesener Bericht
beweist weder einen authentischen Testlauf noch bestandene Verifikation.

Der Lesekern unterstützt XML 1.0 und die ausdrücklich zugelassenen
Encoding-Namen `UTF-8`, `UTF-16`, `UTF-16LE`, `UTF-16BE`, `ISO-8859-1`,
`US-ASCII` und `ASCII`, ohne Beachtung der Groß-/Kleinschreibung.
Die XML-Deklaration darf fehlen; die Byteerkennung bleibt beim Parser.
Andere Namen, auch alternative Codec-Aliase, werden vor dem Rückgriff auf
Pythons erweiterbare Codec-Suche als `unsupported_xml_encoding` abgelehnt.
Der Reader interpretiert das nicht namensraumqualifizierte Kernprofil aus
Spezifikation D.4:

- Wurzel `testsuites` oder `testsuite`; unter `testsuites` stehen `testsuite`.
- Eine `testsuite` enthält weitere `testsuite`, `testcase`, `system-out` oder
  `system-err`. Ein `testcase` enthält `failure`, `error`, `skipped`,
  `system-out` oder `system-err`.
- Die Attribute `name`, `classname`, `file`, `line`, `time`, `timestamp`,
  `tests`, `failures`, `errors` und `skipped` bleiben Strings. Gemeldete Summen
  werden nicht als überprüfte Zählwerte übernommen und nicht repariert.
- Knoten enthalten `tag`, `attributes`, direkt zugehörigen `text` und geordnete
  `children`. XML-normalisierte Zeichen, CDATA und vordefinierte/numerische
  Zeichenreferenzen bleiben Daten. Mehrere Ergebnis-Kindelemente bleiben erhalten;
  fachliche Auswahl und Konfliktauswertung erfolgen erst im Mapping.
- Unbekannte Elemente einschließlich ihrer Unterbäume werden nicht normativ
  interpretiert. `ignored_elements` zählt diese Elemente; `ignored_attributes`
  zählt unbekannte Attribute der übernommenen Knoten. Ihr Original bleibt in
  `source_bytes` für einen später ausdrücklich gewählten Anhang erhalten.
  Gleichnamige Elemente in fremden Namespaces werden nicht zu Kernknoten.

Die harten Grenzen gelten für **ein XML-Dokument**, einschließlich ignorierter
Erweiterungen. Sie sind keine Grenze der gesamten Importmenge und kein weiches
Arbeitsbudget. Ein Host kann sie mit `JUnitLimits` verkleinern, niemals vergrößern:

| Grenze | Maximum |
|---|---:|
| Originalbytes | 4.194.304 |
| Elementtiefe, Wurzel = 1 | 64 |
| Elemente insgesamt | 10.000 |
| Unicode-Zeichen in Text, Attributwerten, Kommentaren und Namespace-URIs zusammen | 1.048.576 |
| Attribute je Element, einschließlich Namespace-Deklarationen | 64 |
| expandierter Element-/Attributname sowie Namespace-Präfix/-URI in Zeichen | 256 |
| expandierte Element- und Attributnamen zusammen, `max_expanded_name_chars` | 1.048.576 |

Jede Namespace-Deklaration zählt einmal zum Attributbudget ihres Elements,
auch ein leerer Default-Namespace. Geerbte Bindungen zählen dort nicht erneut.
Das Namensgesamtbudget zählt jeden Start-Elementnamen und jeden gewöhnlichen
Attributnamen, einschließlich Wiederholungen und ignorierter Erweiterungen.
Bei qualifizierten Namen zählen URI, ein Trennzeichen und lokaler Name.
End-Tags werden nicht erneut gezählt. Namespace-URIs unterliegen zusätzlich
bei jeder Deklaration dem Textbudget. So können kurze Präfixe das Gesamtbudget
nicht durch expandierte Namen umgehen.

Vor dem Parse wird die Bytegrenze geprüft. Der Parser verarbeitet den begrenzten
Eingang in einem abschließenden Aufruf und deaktiviert keine eingebauten
Schutzmechanismen. DTDs und Entity-Deklarationen werden über Parser-Handler
abgewiesen, auch bei UTF-16. Parameter-Entity-Verarbeitung ist ausgeschaltet.
Es gibt keinen externen Resolver. XSD-Schemaverweise, Schema-/XInclude-Elemente
und Processing Instructions werden abgewiesen; XML-Deklarationen sind zulässig.

`XmlImportError` besitzt `reason`, `exit_code` und die Diagnosekennung `SRV083`.
Fehlerhafte Syntax oder nicht unterstützte Kernstruktur ergeben Code 3,
verletzte Sicherheitsgrenzen Code 7 und unzulässige Limitparameter Code 2.
Verfügbare Parserpositionen sind Byteindex, Zeile und Spalte des Originalinputs.
Diagnosen enthalten keine kopierten XML-Inhalte oder Zieladressen.

Die Implementierung nutzt ausschließlich die Python-Standardbibliothek.
Technische Grundlage sind die [Expat-Handler und Parse-API](https://docs.python.org/3/library/pyexpat.html).
Die Encoding-Grenze berücksichtigt auch
[CPythons Unknown-Encoding-Handler](https://github.com/python/cpython/blob/3.10/Modules/pyexpat.c)
und die [Reihenfolge der XML-Deklarationsbehandlung in Expat](https://github.com/libexpat/libexpat/blob/R_2_7_3/expat/lib/xmlparse.c).
Die W-/R-Nachweise bleiben die unveränderten Verhaltensorakel für 12.f.C.
Sie sind Teilnachweise zu `SR-TC-0324` und `SR-TC-0334`; das Mapping besitzt
separate Nachweise. Globale Import-CLI, Veröffentlichung und ReqIF-Anbindung
sind noch nicht abgedeckt.

Der interne Reader `storage/_xml_reader.py` bündelt Eingabeprüfung,
Parserkonfiguration, Sicherheitszähler, verbotene XML-Konstrukte und
Fehlerübersetzung. Er liefert ausschließlich sicherheitsgeprüfte Ereignisse an
vertrauenswürdigen Adaptercode. Dessen Start-Callback erhält eine Ablehnungsfunktion
mit der aktuellen Parserposition; der Parser selbst bleibt intern.
`verification/junit.py` hält das JUnit-Kernprofil, den eigenen Ergebnisbaum und
die unveränderten öffentlichen Wert-, Limit- und Fehlertypen. So kann der
spätere ReqIF-Adapter denselben XML-Lesekern nutzen, ohne JUnit-Strukturregeln
zu übernehmen. Dies implementiert noch keinen ReqIF-Import.

## Explizites Mapping und Kandidaten (12.g.W)

`JUnitMapping(raw)` liest eigene UTF-8-JSON-Bytes mit genau diesen Feldern:

```json
{
  "format_version": "junit-mapping-v1",
  "identity_fields": ["classname", "name", "file"],
  "bindings": [
    {
      "identity": {"classname": "suite.A", "name": "accepts", "file": "tests/a.py"},
      "target_id": "SR-TEST-00000000000000000000000000"
    }
  ]
}
```

`identity_fields` ist eine nichtleere, duplikatfreie Auswahl aus `classname`,
`name` und `file`. Jede Zeile enthält exakt diese Identitätsfelder als nichtleere
Strings und eine Ziel-ID. Verglichen werden die vom XML-Parser gelieferten
Zeichen exakt: keine Pfadnormalisierung, keine Groß-/Kleinschreibungsanpassung,
kein Entfernen von Leerzeichen, kein zusammengesetzter Trennzeichenstring.
Fehlend und leer werden nicht durch Werte aus der Suite ersetzt.
Mappingdateien dürfen höchstens 4 MiB und 10.000 Zeilen enthalten.
Unbekannte Felder, doppelte JSON-Schlüssel und doppelte Mappingidentitäten
werden abgewiesen. `sha256` bindet den kanonischen Mappinginhalt;
`source_bytes` erhält auch die ursprüngliche JSON-Formatierung.

```python
from specroad.verification import JUnitDocument, JUnitMapping, map_junit_candidates

mapped = map_junit_candidates(
    JUnitDocument(report_bytes),
    JUnitMapping(mapping_bytes),
    targets=[test_or_verification_record],
)
candidates = mapped.data["candidates"]
```

`targets` enthält ausdrücklich übergebene `VerificationTest`- oder
`VerificationContract`-Werte. Jede Mapping-Ziel-ID muss darin genau einmal
vorhanden sein. Titel, Anzeigenamen und die `test_identity` eines Testartefakts
ersetzen keine explizite Mappingzeile. Die Auflösung prüft ausschließlich
übergebene Werte; sie belegt weder das Projektinventar noch einen
`verified_by`-Bezug, Pflichtslot oder externen Testlauf.

Jeder Kern-Testcase ergibt in Dokumentreihenfolge einen Kandidaten mit
Ordinalzahl ab 0, JSON-Pointer im Parserbaum, gewählter Identität und gebundener
Ziel-ID, Zieltyp, Revision sowie Roh- und kanonischem Zielhash. Unterschiedliche
Testcases können dasselbe Ziel nennen und bleiben einzelne Beobachtungen.
Ergebnis-Kindelemente werden so klassifiziert:

| Beobachtung direkt im Testcase | `junit_outcome` | vorgeschlagenes `result` |
|---|---|---|
| kein `failure`, `error` oder `skipped` | `passed` | `passed` |
| ein oder mehrere `failure` | `failure` | `failed` |
| ein oder mehrere `error` | `error` | `failed` |
| ein oder mehrere `skipped` | `skipped` | `skipped` |

Eine Mischung verschiedener Ergebnisarten wird im W-Schritt abgewiesen.
Gemeldete Summen, Zeiten und Ausgabetexte begründen kein Ergebnis; leere Suites
erzeugen keine Kandidaten. Unbekannte Erweiterungen bleiben nach D.4 außerhalb
des normativen Kernprofils. Ein vorgeschlagenes `passed` ist lediglich die
Klassifikation der explizit gemappten Kernbeobachtung, keine Verifikationsfreigabe.

Fehlende Identitätsfelder, ungemappte Testcases, wiederholte gewählte Schlüssel
und unbekannte Ziel-IDs brechen diese erste Auflösung vollständig ab.
`JUnitMappingError` liefert `reason`, Pointer, `code=SRV090` und `exit_code=3`;
JSON-/native Artefaktfehler behalten ihre bestehenden `ModelError`-Verträge.
Es wird kein Teilimport veröffentlicht.

Das eigene unveränderbare Ergebnis `JUnitCandidates` bindet Originalgröße und
SHA-256, Parserprofil, kanonischen und ursprünglichen Mappinghash. `data` liefert
jeweils neue Daten; boolesche Erfolgsverwendung ist verboten. Alle Angaben zu
Testausführung, gespeicherter Evidence, Laufbindung, Projektprüfung,
Gesamtverifikation, Schreibberechtigung und Freigabe bleiben ausdrücklich falsch.
Es gibt keine Datei-, Netzwerk-, Uhrzeit-, Zufalls- oder Prozesszugriffe.

Der W-Aufruf behält diesen strikten Vertrag. Die ergänzende Analyse aus
12.g.R unterstützt externe Identifier und vollständige getrennte Diagnosen.
Originalanhänge, Importpolicy, Provenienzergänzung und atomare Evidence-Erzeugung
folgen in 12.i/12.j; fehlende Producer-, Run-, Subject- oder Konfigurationsdaten
werden hier nicht erfunden. `SR-TC-0334` und `SR-TC-0335` bleiben Teilnachweise.

## Vollständige Zuordnungsanalyse (12.g.R)

`analyze_junit_candidates(document, mapping, targets=..., external_identifiers=...)`
liefert ein eigenes `JUnitMappingAnalysis`-Wertobjekt. Der Aufruf akzeptiert
entweder das unveränderte strikte `JUnitMapping` oder `JUnitMappingRules` aus
eigenen JSON-Bytes:

```json
{
  "format_version": "junit-mapping-rules-v1",
  "identity_fields": ["classname", "name", "file", "external_id"],
  "bindings": [
    {
      "identity": {
        "classname": "suite.A",
        "name": "accepts",
        "file": "tests/a.py",
        "external_id": "producer:case-7"
      },
      "target_id": "SR-TEST-00000000000000000000000000"
    }
  ]
}
```

Die Regelstruktur behält die drei geschlossenen Top-Level-Felder des W-Mappings
und dessen Byte-/Zeilengrenzen. Sie erlaubt zusätzlich `external_id` in jeder
nichtleeren Kombination der vier Identitätsfelder. Mehrfache Mappingzeilen für
denselben Schlüssel werden für die Diagnose erhalten; auch zwei identische
Zeilen bestimmen keinen willkürlichen ersten oder letzten Gewinner.
`JUnitMapping` und `map_junit_candidates` bleiben die strikte W-Schnittstelle
mit unveränderten W-Ergebnissen und Fehlerverträgen.

Externe Identifier stammen ausschließlich aus einem ausdrücklich übergebenen
`JUnitExternalIdentifiers`-Wert mit diesen eigenen JSON-Bytes:

```json
{
  "format_version": "junit-external-identifiers-v1",
  "source_sha256": "<SHA-256 der unveränderten XML-Originalbytes>",
  "entries": [
    {"testcase_index": 0, "external_id": "producer:case-7"}
  ]
}
```

Die Ordinalzahlen beginnen bei 0 und zählen ausschließlich Kern-Testcases in
Dokumentreihenfolge, einschließlich verschachtelter Suites. Ignorierte
Erweiterungen zählen nicht mit. Ein Index darf nur einmal vorkommen und muss
ein tatsächliches Vorkommen bezeichnen. Die Begleitdatei darf unvollständig
sein; fehlende Werte werden für die betroffenen Testcases diagnostiziert.
Jeder Identifier ist ein nichtleerer, exakt verglichener String. Wiederholte
Identifier an unterschiedlichen Vorkommen sind zulässig, ergeben bei einem
zu groben gewählten Schlüssel aber eine Mehrdeutigkeit.

Der Originalhash ist exakt gebunden: andere XML-Bytes benötigen eine neue
Begleitdatei, auch bei gleichem Parserbaum, anderer Formatierung oder anderem
Encoding. Die Begleitdatei hat maximal 4 MiB und 10.000 Einträge; Indexwerte
sind Ganzzahlen von 0 bis 9.999, keine booleschen Werte. Veraltete Hashes,
fremde Indizes, doppelte Einträge oder unzulässige Typen ergeben
`JUnitMappingError`/SRV090, Code 3. Wenn `external_id` ausgewählt ist, ist der
typisierte Eingang erforderlich; ohne dieses Feld wird eine trotzdem
übergebene Begleitdatei abgewiesen. Weder XML-Erweiterungen noch
`test_identity.external_id` eines Zielartefakts werden automatisch ausgewertet.
Das schränkt D.4 nicht ein und erweitert das XML-Kernprofil nicht.

```python
from specroad.verification import (
    JUnitDocument, JUnitMappingRules, JUnitExternalIdentifiers,
    analyze_junit_candidates,
)

analysis = analyze_junit_candidates(
    JUnitDocument(report_bytes),
    JUnitMappingRules(rule_bytes),
    targets=[test_or_verification_record],
    external_identifiers=JUnitExternalIdentifiers(identifier_bytes),
).data
```

Das Ergebnisformat `junit-mapping-analysis-v1` umfasst:

- `observations`: jedes Kernvorkommen mit Ordinalzahl, Parserpointer, gewählter
  Identität, vollständigem Class-/Name-/File-/External-ID-Kontext und allen
  direkt beobachteten Ergebnisarten. Fehlende Werte bleiben `null`, leere
  Strings bleiben leer.
- `candidates`: nur eindeutig zugeordnete, widerspruchsfreie Vorkommen mit
  demselben Kandidatenvertrag wie W. Die Ordinalzahlen bleiben die ursprünglichen
  Vorkommensnummern; ein ausgelassener Kandidat nummeriert spätere nicht um.
- `diagnostics`: jede Diagnose mit `category`, `reason`, `code`, `severity`,
  betroffenen `testcase_indexes`, `mapping_indexes` und `missing_fields`.
  Die Indizes sind sortiert. Ein leeres Testcase-Array kennzeichnet eine auch
  ohne Vorkommen ungültige oder mehrdeutige Mappingzeile.
- `rejected_testcase_indexes`: vollständige Menge der Vorkommen ohne Kandidat.
  Jedes davon ist mindestens einer Diagnose zugeordnet.
- `targets`: die tatsächlich geprüften übergebenen Zielbindungen, nach ID
  sortiert. Original- und Mappingbindung entsprechen W; `external_identifiers`
  ist entweder `null` oder `{sha256, size, source_sha256}` der Begleitdatei,
  wobei `sha256` ihren kanonischen Inhalt und `source_sha256` ihre Rohbytes bindet.

| Kategorie | Bedingungen und Gründe | Diagnose |
|---|---|---|
| `unmapped` | `junit_testcase_identity_missing`, `junit_testcase_unmapped`, `junit_mapping_target_not_found` | SRV043, warning |
| `ambiguous` | `junit_mapping_ambiguous`, `duplicate_junit_testcase_identity` | SRV043, warning |
| `contradictory` | `conflicting_junit_testcase_outcomes`, `conflicting_junit_testcase_results` | SRV090, error |

Mehrere Problemaspekte bleiben getrennt sichtbar, beispielsweise eine fehlende
Identität und gleichzeitig gemischte Ergebnisarten. Ungültige Ziel-IDs in
ungenutzten Zeilen verschwinden nicht. Diagnosen kopieren keine Ergebnistexte,
externen Identifier oder fremden Ziel-IDs; Indizes verweisen auf die expliziten
gebundenen Eingaben. Große Gruppen gleicher Schlüssel erzeugen gruppierte
Diagnosen, keine quadratische Liste paarweiser Konflikte.

Jeder mehrfach beobachtete gewählte Schlüssel bleibt mehrdeutig, auch bei
gleichem Ergebnis. Unterschiedliche Ergebnisse desselben vollständigen
Class-/Name-/File-/External-ID-Kontexts sind zusätzlich widersprüchlich.
Unterschiedliche Kontexte bei zu grobem Schlüssel sind dagegen mehrdeutig,
ohne sie allein deshalb zu widersprüchlichen Ergebnissen desselben Tests zu
erklären. Eine ausdrücklich gewählte feinere Kombination kann sie trennen.
Verschiedene eindeutige Testcases zum gleichen Ziel bleiben getrennte Messungen;
die spätere Pflicht-/Laufaggregation wird hier nicht vorweggenommen.

`mapping_complete` bedeutet ausschließlich, dass keine Zuordnungsdiagnosen
vorliegen, auch bei einem leeren Bericht. Es ist kein Erfolg eines Testlaufs.
`import_policy_applied` und sämtliche Autoritäts-/Ausführungsflags aus W bleiben
falsch. Die Analyse entscheidet weder `abort_import` noch
`skip_invalid_with_diagnostic` und veröffentlicht keine Teilmenge.
Format-/Syntax- und Sicherheitsfehler liefern weiterhin keinen Teilbericht.
Eigentum, boolesches Verbot und Seitenwirkungsfreiheit gelten wie bei W.

## Interne Trennung (12.g.C)

`verification/_junit_mapping_inputs.py` enthält die begrenzten JSON-Leser für
Mapping und externe Identifier sowie die Projektion des geprüften Parserbaums
auf Testcase-Vorkommen, Identitäten, Kontexte und Ergebnisarten. Es kennt keine
nativen Ziele, Evidence-Zuordnung oder Importentscheidung.

`verification/junit_mapping.py` hält die öffentlichen Wert- und Fehlertypen an
ihren bisherigen Importpfaden. Dort liegen die gemeinsame Prüfung der expliziten
nativen Ziele sowie die getrennten W- und R-Zuordnungen mit ihren unveränderten
Fehlern, Kandidaten und Diagnosen. Reihenfolge, Original-/Mapping-/Zielhashes,
Byte- und Zeilengrenzen, Ownership und die passiven Seiteneffektgrenzen bleiben
erhalten. W-/R-Tests und feste Testnummern werden durch die Bereinigung nicht
geändert.
