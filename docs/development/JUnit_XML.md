# JUnit-XML lesen (12.f.W/R/C)

`specroad.verification.JUnitDocument(raw)` liest ein vollständiges XML-Dokument
aus ausdrücklich übergebenen `bytes`. Es öffnet keine Datei und startet weder
Tests noch einen Unterprozess. Die globale Import-CLI, Testcase-Mappings,
Evidence-Kandidaten und deren Veröffentlichung folgen in eigenen Planschritten.

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
Sie sind Teilnachweise zu `SR-TC-0324` und `SR-TC-0334`; Mapping, globale
Import-CLI, Veröffentlichung und ReqIF-Anbindung sind noch nicht abgedeckt.

Der interne Reader `storage/_xml_reader.py` bündelt Eingabeprüfung,
Parserkonfiguration, Sicherheitszähler, verbotene XML-Konstrukte und
Fehlerübersetzung. Er liefert ausschließlich sicherheitsgeprüfte Ereignisse an
vertrauenswürdigen Adaptercode. Dessen Start-Callback erhält eine Ablehnungsfunktion
mit der aktuellen Parserposition; der Parser selbst bleibt intern.
`verification/junit.py` hält das JUnit-Kernprofil, den eigenen Ergebnisbaum und
die unveränderten öffentlichen Wert-, Limit- und Fehlertypen. So kann der
spätere ReqIF-Adapter denselben XML-Lesekern nutzen, ohne JUnit-Strukturregeln
zu übernehmen. Dies implementiert noch keinen ReqIF-Import.
