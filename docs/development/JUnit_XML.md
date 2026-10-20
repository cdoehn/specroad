# JUnit-XML lesen (12.f.W)

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

Der W-Lesekern unterstützt XML 1.0 und die von CPythons Expat erkannten
XML-Encodings. Er interpretiert das nicht namensraumqualifizierte Kernprofil aus
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
| Attribute je Element, ohne Namespace-Deklarationen | 64 |
| expandierter Element-/Attributname sowie Namespace-Präfix/-URI in Zeichen | 256 |

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
Der W-Nachweis ist ein Teilnachweis zu `SR-TC-0324` und `SR-TC-0334`.
Weitere Robustheitsfälle in 12.f.R und die gemeinsame XML-Struktur für ReqIF
in 12.f.C bleiben getrennte Arbeitsschritte.
