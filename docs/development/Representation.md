# Repräsentation ohne Fachänderung – Entwicklungsstand 2.k

## Grenzen

Die APIs dieses Schritts erzeugen **Vorschläge im Speicher**, keine Schreibberechtigung.
`specroad format`, `format --check`, vollständige Ressourceninventur und die Ausführung
von `representation_normalize` im Change Plan werden hier nicht vorgezogen. Die
Transaktionsengine wird in Meilenstein 5 aufgebaut; Fachbefehle integrieren sie später.
Es werden keine Projektdateien, Revisionen, Akteure oder Zeitwerte geschrieben.

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
Mehrdateisnapshot**. Ein späterer Writer muss unmittelbar vor Veröffentlichung alle
Bedingungen unter der gemeinsamen Transaktionsgrenze erneut überprüfen.

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

Die normale vollständige Prüfung verwendet unverändert pytest-xdist; der
Clean-Schritt erhält zusätzlich einen seriellen Lauf und Nachweisvergleich.
Keine neuen Core- oder Entwicklungsabhängigkeiten. Ein erfolgreiches lokales
Entwicklungs-Resultat ist keine Zielsystem-, Python-Matrix- oder Releasefreigabe.
