# Explizite Requirement-Verbindlichkeit – 2.m

Grundlage: Spezifikation 0.2.7, Anhang S.1–S.3 und SR-REQ-0066–0076,
0651–0653, 0656. Zielrelease bleibt 0.2.0. Dies ist keine Releasefreigabe.

## Gemeinsame Vorbereitung

`specroad.model.requirement.prepare_requirement` bereitet im Speicher einen
neuen Requirement-Entwurf vor. Der Aufrufer liefert Felder, eine bereits
gewählte `ArtifactIdentity`, einen `Actor` und `UtcTimestamp`. Die Identität
muss eine neue `random128-v1`-Requirement-ID sein. Der Baustein reserviert diese
ID nicht und behauptet keine vollständige Kollisionsinventur.

`language`, `normative_force`, `statement`, Anforderungstyp, Priorität und
Kritikalität werden materialisiert. `maturity=draft`, Revision 1 und identische
Erstellungs-/Änderungsauditwerte werden aus den expliziten Eingaben aufgebaut.
Zustandsangaben bleiben Deklarationen, keine Evidence für erfolgreiche Umsetzung.
Keine Dateierzeugung, keine automatische Uhr-, Benutzer-, Locale- oder
Detektorerkennung, keine Freigabe und keine Work-/Transaktionsoperation.

`fields` enthält die fachlichen Eingaben, nicht ID, Audit oder Reifegrad.
Geschützte Felder werden nicht still überschrieben: schon ihr Vorhandensein
wird als `reserved_requirement_field` zurückgewiesen. Ausdrückliche Argumente
`language` und `normative_force` sind gleichwertige Eingabequellen. Bei einer
abweichenden Angabe im Feldobjekt entsteht `requirement_input_conflict` mit dem
betroffenen JSON Pointer. Ein späterer CLI-Adapter muss diesen Eingabekonflikt
auf Exitcode 2 abbilden. Hier wird noch kein CLI-Fachbefehl eingeführt.

Ein fehlendes `language` darf ausschließlich aus der übergebenen typisierten
`ProjectConfiguration.language_policy.default_language` ergänzt werden.
Ein ausdrücklich leeres oder nullwertiges Feld ist kein fehlendes Feld und
wird nicht durch den Default repariert. `default_locale` ist kein Sprachdefault.
Die Herkunft wird in `language_source` als `input`, `argument` oder
`project_default` ausgewiesen; `force_source` besitzt keinen Default-Zustand.
Der spätere Writer muss die Projektkonfiguration unter seinem Lock erneut binden.

## Bedeutung ist kein Textumbau

`NormativeForce` hat genau `must`, `must_not`, `should`, `may`.
`requirement_meaning` liefert die explizite Einheit aus Sprache, Verbindlichkeit
und unverändertem Sachverhalt. `must_not` negiert keinen Satz automatisch.
Ein modalwortfreier Indikativsatz kann ein `must`-Requirement sein; ein `may`
kann die Planungspriorität `mandatory` tragen. Weder Typ, Kritikalität, Keywords
noch Analyzerdaten bestimmen die Verpflichtungsart.

`should` verlangt ab dem Entwurf nichtleere Abweichungsbedingungen und eine
Autorität in der vorhandenen Text-/Actor-Datenform. Eine solche Angabe stellt
keine Authentifizierung, genehmigte Abweichung oder bestandene Verifikation dar.

## Laden und strukturierte Semantik

`specroad.storage.requirement.RequirementArtifact` bewahrt die gelesenen Bytes
und historischen Auditwerte. `read_requirement` verwendet die bestehenden
Projekt-, Pfad- und ID-Prüfungen; fehlende gespeicherte Metadaten werden niemals
aus Defaults ergänzt. Abgeleitete Datenobjekte sind unabhängige Kopien.

Alle bestehenden strukturierten Semantikfelder bleiben erhalten. Der gesondert
aufrufbare `RequirementDuration` unterstützt nichtnegative ISO-Designatorformen
(zum Beispiel `PT0.5S`, `P2W`) und Mengenobjekte `{value, unit}` mit bekannten
UCUM-Zeitatomen. Es gibt keine Umrechnung, Textanalyse oder implizite Einheit.
Nicht unterstützte Einheitenausdrücke werden als `unsupported_duration_unit`
zurückgewiesen, nicht pauschal als ungültiges UCUM bezeichnet.

Dieser bewusst begrenzte Baustein ist **kein vollständiger UCUM-Parser**. Freie
Semantikobjekte werden nicht allein wegen eines Feldnamens umgedeutet oder als
vollständig duration-validiert ausgegeben. Vollständige profilgebundene
Zeit-/Einheitenprüfung und zusätzliche zulässige Repräsentationen bleiben in
SR-TC-0076 offen. Referenzen zur Implementierungsprüfung:

- UCUM-Spezifikation, Zeitatome und Präfixe: https://ucum.org/ucum
- Vergleich für ISO-Designatorformen: https://www.w3.org/TR/xmlschema-2/#duration

Die W3C-Form ist eine Teilmenge der ISO-Repräsentationen; insbesondere findet
keine Gleichsetzung von Kalendermonaten mit einer konstanten Sekundenanzahl statt.

## Grenzen

`validation_scope=requirement_fields_only` bestätigt keine vollständige
Requirement-Freigabe. Die vollständige BCP-47-/Registerklassifikation folgt in
2.n. Menschliches Inhaltsreview, Profil-/Graphregeln, Writer-Locks, ID-Reservierung
und CLI-/Import-/Migrationsworkflows folgen in ihren vorgesehenen Schritten.
Für eine Migration ist das byteerhaltende Laden von Originalen von einer
regulären neuen Entwurfserzeugung zu unterscheiden; der neue Konstruktor setzt
keinen alten Datensatz heimlich auf Revision 1 zurück.

Verhaltenstests prüfen Daten, Konflikte, Fehler, Isolation und portable Aufrufe;
keine Darstellungs-, Dokumentations- oder Farbtests. Die vorhandene CLI und die
parallelisierte Testinfrastruktur bleiben unverändert. Die lokale Probe ersetzt
keine Zielsystem- oder vollständige CPython-Matrix-Abnahme.
