# Repräsentation ohne Fachänderung – Entwicklungsstand 5.u.W

## Grenzen

Die Kandidaten-APIs aus 2.k erzeugen **Vorschläge im Speicher**, keine Schreibberechtigung.
Seit 5.u.W können reine `representation_normalize`-Pläne für aktuelle generische
Artefakte über die bestehende Zielprüfung und native Transaktionsengine laufen.
Der Host muss den vollständigen Projektbestand, alle erforderlichen Zielgates,
die expliziten Planfelder und eine echte Schreibberechtigung bereitstellen.
Revisionen, Fachwerte und Zeit-/Akteursmetadaten bleiben unverändert.
`specroad format` und `format --check` sind noch keine registrierten CLI-Befehle.

`normal_json_bytes(raw)` liest genau ein UTF-8-JSON-Objekt über den strikten Reader.
Die interne menschenlesbare Normalform verwendet zwei Leerzeichen Einrückung,
eine abschließende LF und auf jeder Objektebene nach Unicode-Codepoints sortierte
Schlüssel. Das ist bewusst nicht JCS: `canonical_*` bleibt die separate normative
Hashschnittstelle mit UTF-16-Schlüsselsortierung und eigener Zahlendarstellung.
Originale Stringwerte werden weder getrimmt noch nach NFC/NFD oder Zeilenenden
vereinheitlicht. Bereits vorhandene Audit- und Identitätsfelder bleiben erhalten.

## Bytegebundene Vorschläge

```python
from specroad.storage.project import ProjectSource
from specroad.storage.representation import (
    prepare_normalization, prepare_normalizations, check_normalization_current,
)

source = ProjectSource(project_root)
candidate = prepare_normalization(source, "specroad.json")
assert candidate.source_data == candidate.normalized_data
# Keine Veröffentlichung: beide Bytefassungen existieren nur im Kandidaten.
check_normalization_current(source, candidate)
```

`NormalizationCandidate` enthält die vollständigen Quell- und Zielbytes,
`expected_byte_sha256`, `result_byte_sha256` und einen vollständigen JCS-Werthash
`value_sha256`. Dieser ist **keine** Projektion der späteren semantischen Modellwurzel.
`change_required` wird anhand echter Bytegleichheit bestimmt. Die Daten-Properties
liefern unabhängige Objekte. Bereits normalisierte Daten erzeugen keinen weiteren
Änderungsbedarf. `require_current(raw)` prüft die exakten ursprünglichen Bytes und
weist auch eine inzwischen erfolgte semantisch gleichwertige Formatänderung zurück.

`prepare_normalizations` verarbeitet nur eine ausdrücklich übergebene Pfadmenge.
Doppelte/ungültige Pfade werden abgewiesen; ein fehlerhafter Eintrag ergibt keine
teilweise Erfolgsmenge. Alle Originalbytes werden nach dem Lesen erneut geprüft.
Das erkennt beobachtete Änderungen, ersetzt jedoch **keinen Lock und keinen atomaren
Mehrdateisnapshot**. Der Writer überprüft unmittelbar vor Veröffentlichung alle
Bedingungen unter der gemeinsamen Transaktionsgrenze erneut.

## Transaktionaler W-Ausschnitt

`prepare_change_target` und `assess_change_target` akzeptieren dieselbe reguläre
Operation mit `path`, `expected_byte_sha256` und `target_byte_sha256`. Der Plan
behält seine gewöhnliche Selbsthash-, Scope-, Actor-, Request- und Metadatenpolicy-
Bindung. Datei-/Artefaktvorbedingungen sowie sämtliche Zielgates bleiben aktiv.
Die Zielbytes werden aus den gebundenen Originalbytes neu berechnet; fremde
Zielbytes oder ein lediglich semantisch passender alter Dateistand genügen nicht.

Repräsentationsänderungen ergeben keine fachlichen `result_artifacts`, keinen
Lifecycle-Übergang und keine Revisionserhöhung. Modellwurzel und semantischer Diff
bleiben gleich. `assessment.representation` enthält die ausgewählten Pfade und
Byte-/Werthashes; `changed_paths` enthält nur tatsächlich andere Bytes.
Die gemeinsame Dry-run-Ausführung setzt deshalb `would_change` und bei
`fail_on_change=True` Code 1 auch bei unveränderter Modellwurzel. Bereits
normalisierte Bytes ergeben Code 0. Diese Vorschau erzeugt weder Lock, Journal,
Receipt noch Projekt-/Betriebsdateien.

Die normale `PublicationRequest` übergibt die geänderten Artefaktbytes an denselben
Journal-, Staging-, Publish-, Receipt- und Cleanup-Weg wie fachliche Änderungen.
Originalbytes bleiben als Before-Images erhalten. Native Recovery kann ein
vollständiges Byteziel abschließen oder eine unterbrochene Mehrdateinormalisierung
auf die exakten Originalbytes zurückführen, obwohl Basis- und Zielmodellwurzel
gleich sind. Es gibt keinen separaten Format-Schreibbackend.

Der W-Ausschnitt weist doppelte Pfade, gemischte fachliche/Normalisierungsoperationen
und den noch nicht unterstützten Ressourcen-Schreibbereich vollständig zurück.
In 5.u.R folgen `specroad.json`, Profile, Regeln, Mappings und die zulässigen
veränderbaren Spezialartefakte samt Schutz ihrer Endstände. Ihre geänderten
Bytebindungen müssen auch Rücklesen, Konfigurationsfrische und Recovery abdecken.
Die bereits vorhandene schreibfreie Kandidaten-API behält ihren größeren
Dateiumfang; dies ist noch keine transaktionale Freigabe dieses Gesamtumfangs.

## Schutzbereich aus Spezifikation 10.17

Zulässig sind nur aktuelle JSON-Ressourcen: `specroad.json`, Profile, Regeln,
Mappings und veränderbare Artefakte. Pfad- und Projektidentität werden über den
bestehenden `ProjectSource` gebunden. Archive, Anhänge, das konfigurierte
`generated_path`, Betriebsdaten und nicht verwaltete Pfade werden nicht normalisiert.

Recorded Evidence und Relationsreviews sowie sealed Baselines bleiben unverändert.
Dasselbe gilt für Proposals in `applied`, `rejected` und `stale`. Fehlende,
unbekannte oder mit `maturity` widersprüchliche Spezialzustände werden nicht als
veränderbar angenommen. Für Artefakte werden gemeinsame Identität/Pfadfelder und
für die Spezialtypen die bereits vorhandenen Record-Feldverträge geprüft. Profile,
Regeln und Mappings erhalten hier nur Syntax-/Versionsprüfung; eine vollständige
Schema-/Graph-/Profilfreigabe wird nicht behauptet.

## Generierte Ansichten sind keine Modellquelle

`GeneratedView(payload_bytes, format=...)` kennzeichnet erste JSON-, Markdown-,
HTML- und Textansichten als generiert/nicht normativ. Das Eingabepayload bleibt
bytegenau erhalten; Text-Zeilenenden werden nur in der separaten Ansicht nach LF
überführt. JSON trägt die ausgewählten Daten in einem eigenen nicht normativen
Envelope. Die Rolle ist nicht durch gleichnamige Felder im Payload überschreibbar.
Andere Formate werden nicht vorgetäuscht; sie brauchen ihre späteren Adapter.

Text und HTML sind bereits gerenderte Inhalte. Dieser Adapter ist weder ein
HTML-Sanitizer noch die spätere Dokument-Renderingengine. Er öffnet und führt keine
Referenzen aus und schreibt keine Dateien.

Die Kennzeichnung ist **keine Authentifizierung**. Schutz vor Rückimport entsteht
aus vertrauenswürdigen Pfadklassen und Ressourcenschemas: `generated_path` ist kein
normativer Eingangsbereich, der View-Wert ist kein akzeptierter Rohdaten-Input und
der JSON-Envelope ist kein normatives Artefakt-/Konfigurationsobjekt. Ein bewusstes
manuelles Herauskopieren und Neuanlegen von Inhalten außerhalb dieser API kann eine
passive Markierung nicht verhindern. Die späteren Importbefehle müssen dieselbe
Quellenpolitik beibehalten und dürfen keine Ansichten still zurückimportieren.

## Verhaltenstests und Nachweise

Die Testmodule `test_representation.py` und `test_representation_right.py` prüfen
Wert-/Hash-/Revisionsgleichheit, Originaltext-UTF-8, Ablehnungen, Frische,
Bytebindungen, fehlende Schreibeffekte und verschobene portable Distributionen.
Es gibt keine automatisierten Einrückungs-, Schlüsselreihenfolgen-, Header-,
HTML-/Markdown- oder Dokumentationstests. Die sichtbare Normalform und Kennzeichnung
unterliegen TD-001. SR-TC-0021 bleibt daher ohne künstlichen automatisierten Pass.

`test_normalization_target.py` und `test_normalization_transactions.py` ergänzen
25 Fälle zu direkten/gespeicherten Plänen, unveränderten Vollwerten, Bytehash-
Konflikten, wirklicher Schreibfreiheit, vollständigen Zielgates, nativen Receipts,
Stagingmanipulation und Completion/Rollback bei gleicher semantischer Wurzel.
Die Anforderungsmanifeste bleiben hinsichtlich CLI und Gesamtumfang ausdrücklich
partiell; die noch ausstehende Schutzbereichsvervollständigung wird nicht als
erledigte Produktabnahme ausgegeben.

Für die Testausführung gilt die lokale `AGENTS.md`; die technische Anleitung
steht in [Testing.md](Testing.md).
Keine neuen Core- oder Entwicklungsabhängigkeiten. Ein erfolgreiches lokales
Entwicklungs-Resultat ist keine Zielsystem-, Python-Matrix- oder Releasefreigabe.
