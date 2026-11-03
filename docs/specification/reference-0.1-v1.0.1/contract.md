# SpecRoad 0.1-Referenzformat, Quellvertrag 1.0.1

## 1. Autorität, Herkunft und Geltungsanspruch

**REFERENCE-RELEASE-552**, ausdrückliche manuelle Nutzerentscheidung vom
3. November 2026: einmalige gemeinsame Übergabe der empfohlenen Klärung und
der nachfolgenden Plancommits. Version 1.0.1 schließt die Release-Auswahlbindung und die in Abschnitt 5.1
bezeichneten Speicherfeldlücken sowie die Proposal-Basis aus 5.2; Version 1.0.0 bleibt als historische Definition
bytegleich erhalten. Die gemeinsame ZIP ersetzt weder Commitgates noch
menschliche Reviews und ändert keinen Control-Zustand oder Budgetzähler.

**REFERENCE-SOURCE-551**, ausdrückliche Nutzerentscheidung vom 3. November
2026: „Wir legen ein neues Format fest“. Dieser Vertrag definiert **jetzt**
ein vollständiges, begrenztes Referenzformat für die geplante Migration.
Er rekonstruiert kein früher veröffentlichtes SpecRoad-Format und behauptet
weder externe Altkompatibilität noch eine historische Installation.
Die technischen Details konkretisieren diese Entscheidung gemäß
SPECROAD-DECISION-1; sie sind keine zusätzlichen menschlichen Produktreviews.

Identität: `contract_id=specroad-reference-0.1`, `contract_version=1.0.1`,
Datenetikett `schema_version=0.1.0`. Der vollständige Vertragsinhalt ist durch
die **Originalbyte-SHA-256 von manifest.json** gebunden. Das Manifest bindet
alle Schemas, diesen Text, die eingefrorene Grundlage, das Sprachregister,
das feste Quellprofil und die Sollvektoren. Das Manifest bindet sich nicht
selbst; die aktive Spezifikation bindet seinen Hash. Kein rollender Verweis
auf eine später geänderte 0.2-Spezifikation oder Implementierung ist zulässig.

Ein Quellprojekt muss die exakte Kennung und Version in
`specroad.json/source_contract` tragen. Das Etikett `0.1.0` allein genügt
nicht. Die Kennung wählt ausschließlich einen mitgelieferten Core-Vertrag;
sie ist kein Dateipfad, Importname, URL oder ausführbarer Provider. Ein
gefälschtes Kennungsobjekt ersetzt keine vollständige Validierung.
Andere Quellverträge werden weder geraten noch automatisch repariert.

Dieser Vertrag ist eine Daten- und Abnahmefestlegung, kein implementierter
Leser. Produktive Unterstützung verlangt zusätzlich die nativen M16-Gates
einschließlich Restore-Integration. Der aktuelle 0.2-Writer, `init`, bestehende
0.2-Projekte, Journal-/Work-Formate und deren Freigaben bleiben unverändert.
Ein allgemeiner 0.1-Writer oder eine Export-/Downgradefunktion entsteht nicht.

## 2. Vollständige Schemafamilie und eingefrorene Fachregeln

`artifact-types.json` nennt abschließend alle 28 Artefakttypen, Präfixe,
Verzeichnisse und zugehörigen **geschlossenen** Quellschemas. Jedes Artefakt
muss sein vollständiges Schema unter `schemas/artifacts/` erfüllen.
`schemas/project.json`, `schemas/profile.json`, `schemas/relation.json` und
`schemas/manifest-entry.json` ergänzen die Quellfamilie.
`schemas/change-plan.json` bindet zusätzlich den vollständigen geschlossenen
gespeicherten Plan mit den Quellidentitäten und -Locatoren; vollständige
Artefaktwerte darin erfüllen zusätzlich ihr jeweiliges Quellschema. Keine Prüfung nur
gemeinsamer Felder darf als vollständige Quellqualifikation gelten.
Die Schemas beschreiben lokale Felder; die folgenden globalen Regeln gehören
ebenso zum vollständigen Vertrag. Fehlende Pflichtfelder werden nie durch
Schema-`default`, Beispiele, UI-Vorgaben oder Projektionen ergänzt.

Die Datei `basis-0.2.48.md` ist die bytegenaue Spezifikation 0.2.48,
SHA-256 `15607c51272c8cb1c730a2bee1b28357d5d09f1f049946d82d8b9065d2ff67d6`.
Sie ist **bewusst gewählte heutige Entwurfsgrundlage**, kein historischer
0.1-Nachweis. Es gelten ihre unveränderten Feldsemantiken, Relationsmatrix,
SRX-Semantik, Pfadsicherheit, Referenz- und Zustandsregeln aus 9.1–9.7,
9.9, 10.1–10.5, 10.8–10.10, 10.12–10.15 sowie Anhängen B, H, I, J, K und L, soweit die
nachstehenden ausdrücklichen Quellregeln sie nicht ersetzen. Aktuelle
Betriebs-/CLI-Abläufe, Entwicklungsfreigaben und ihre historischen Blockaden
werden aus dieser eingefrorenen Kopie nicht erneut aktiviert.

Die lokalen Schemas wurden als Dokumentartefakte aus den an Apply-Commit
`e17c8276ecaf9cb83f188aac0a8f556481386b81` gebundenen vollständigen Domain- und
Record-Feldschemata abgeleitet. Ihre tatsächlich gespeicherten Bytes sind
maßgeblich; spätere Änderungen an Schemafabriken ändern diesen Vertrag nicht.
Aus dieser Herkunft folgt kein getesteter Quellleser. Bei einem Widerspruch
zwischen diesem Text und einem Quellschema gilt **keine erfolgreiche
Qualifikation**; der Vertrag muss versioniert korrigiert werden.

Abschließende Abweichungen gegenüber der eingefrorenen Grundlage:

| Bereich | Quellregel |
|---|---|
| Normative Artefakte | `schema_version=0.1.0`; `id_scheme` ist nicht gespeichert und als Top-Level-Feld unzulässig. |
| Artefaktidentitäten und typisierte Artefaktverweise | `<PROJECT>-<TYPE>-<NNNN>`, exakt vier Dezimalziffern einschließlich `0000`; Präfix, Typ und Speicherpfad müssen übereinstimmen. Random128-IDs gehören nicht zu diesem Quellformat. |
| Requirements | `language` und `normative_force` fehlen ausdrücklich und sind unzulässig. Beide werden erst durch das autorisierte Migrationsmapping geliefert. Alle übrigen Pflicht-/Optionsfelder bleiben gemäß Quellschema bestehen. |
| Andere Artefakte | Explizite Sprachfelder bleiben erhalten; insbesondere Document und Term verlangen weiterhin ihre eigene Sprache. Aus dieser Sprache oder `default_locale` wird keine Requirement-Sprache abgeleitet. |
| Beziehungen | Kein gespeichertes `relation_id` oder `id_scheme`. Relation ist das vollständige Objekt gemäß Quellschema; ihre Position im Originalarray gehört zur Herkunft. |
| Typisierte Relationsverweise | Statt einer REL-ID wird ein Locator `{source_id,index}` verwendet; `index` ist die ursprüngliche nullbasierte Position. Ein typisiertes `relation_id`-Feld heißt dabei `relation_locator`, ein typisiertes `relation_ids`-Array entsprechend `relation_locators`. Das gilt auch für gespeicherte Pläne/Projektionen; andere Strukturfelder und deren Verbindlichkeit bleiben bestehen. Opaque Text-/Extensionswerte werden nicht rekursiv umgeschrieben. |
| Relationsreviews | Das Feld `relation_locator` ersetzt `relation_id`; Endpoint-IDs, Revisionen, Vollhashes, Reviewzeit und `context_hash_algorithm=reference01-relation-context-v1` sind Pflicht. |
| Evidence | `context_hash_algorithm=reference01-verification-context-v1` ist Pflicht; ursprüngliche Subject-Vollhashes und Kontextwerte bleiben getrennt. |
| Baselines und Source-Modellwurzel | Vollständiger Projekt-Snapshot und Algorithmus aus Abschnitt 6; keine rückwirkende Anwendung der 0.2-Modellwurzel. |
| Source-Projektkonfiguration und Ressourcen | Ausschließlich die vollständigen geschlossenen Quellschemas und das eine feste Profil aus Abschnitt 3. |

Die Snapshot-Sonderregel ersetzt die Modellwurzel und den gespeicherten
Baseline-Scope. Andere passive Wertobjekte, etwa ein Waiver-Scope oder eine
Configuration-Auflösung, behalten die ausdrücklich eingefrorenen Regeln aus
10.8/10.10. Sie werden nicht allein wegen ähnlich benannter Felder als
Source-Snapshot umgedeutet. Ein Produktstand-Hash in `run_context` bindet
weiterhin die Prüfeingänge nach 10.5.1, nicht die SpecRoad-Modellwurzel.

Globale Quellvalidierung prüft Typ-/Präfixkonsistenz, Projektzugehörigkeit,
eindeutige IDs und Pfade, Auflösung sämtlicher starker typisierter Referenzen,
Relationsmatrix, Besitz-/Containment-/Vererbungszyklen und Kardinalitäten aus
der Grundlage. Symmetrische Relationen stehen genau einmal an der nach
Artefakt-ID-UTF-8-Bytes kleineren Seite. Gleiche `(source,type,target)`-Kanten
sind in diesem Referenzformat nicht mehrfach zulässig; unterschiedliche Typen
bleiben verschieden. `contains` verlangt `position`; andere Typen verbieten
dieses Feld. Bei gleicher Position entscheidet die Ziel-ID, nicht eine
erfundene aktuelle Relations-ID. Arrays werden bei der Migration nicht sortiert.

Die fachlichen Zustandsbedingungen bleiben wirksam, mit einer ausdrücklichen
Quellgrenze: Ein Requirement kann ohne Zielsprach-/Verbindlichkeitsangabe
quellgültig sein, auch mit gespeichertem `approved`. Daraus folgt **keine**
aktuelle 0.2-Freigabe. Andere Struktur-, Herkunfts-, Review- und Integritäts-
bedingungen werden nicht ausgenommen. Gespeicherte negative Ergebnisse sind
keine Strukturfehler und keine positiven Abnahmen. Herkunft eines behaupteten
menschlichen Reviews wird nicht durch Formatgültigkeit bewiesen.

## 3. Projektlayout, Ressourcen und JSON-Werte

Genau eine Konfiguration liegt im Root unter `specroad.json`. Ihre geschlossene
Feldmenge steht vollständig in `schemas/project.json`. `project_id` ist ein
nichtleerer, NUL-freier stabiler String; daraus wird keine UUID abgeleitet.
`id_prefix` folgt `[A-Z][A-Z0-9]{1,7}`. Die vier `managed_paths` sind in dieser
Reihenfolge `spec`, `profiles`, `rules`, `mappings`; `generated_path=generated`.
Artefakte liegen unter `spec/<Verzeichnis>/<ID>.json` gemäß Typentabelle.
Genau ein Document hat `document_role=primary_specification`.

`profiles/core-reference01.json` muss dem JSON-Wert von `core-profile.json`
entsprechen; zulässige JSON-Formatierung darf abweichen. Die einzige aktive
Profilkennung ist `core-reference01@1.0.0`. Ihre Semantik sind genau die
Quellschemas und globalen Regeln dieses Vertrags; sie lädt keinen Code nach.
Es gibt in Version 1 dieses **neu entworfenen** Formats keine weiteren
Profil-, Rule-, Mapping- oder Sprachpaket-Ressourcen. Die Verzeichnisse
`rules/` und `mappings/` dürfen leer sein. Zusätzliche normative Ressourcen
werden als nicht unterstütztes Quellformat abgewiesen, nicht gelöscht oder
als harmlose Anhänge verborgen. Dies beschränkt ausschließlich den neu
gewählten Referenzvertrag; es ändert keine bestehende 0.2-Fähigkeit.
Ein späterer zusätzlicher Quellressourcentyp erfordert eine neue Vertragsversion.

Gültige namespaced Extensions bleiben in ihrer vollständigen JSON-Struktur
erhalten, ohne Interpretation als Schema, Plugin oder Ausführungsanweisung.
Namespaces bestehen aus mindestens zwei durch Punkte getrennten, nichtleeren
Komponenten ohne Whitespace, Punkt oder Steuerzeichen; zulässige Unicode-
Komponenten werden nicht auf ASCII beschränkt. Externe Identitäten binden
`source_system`, `source_document` und `external_id`; dieses Tripel ist pro
Array eindeutig. Optional sind `external_revision` und `extensions`.
Importherkunft enthält entweder alle fünf Felder `mapping_id`,
`last_imported_projection_sha256`, `last_source_projection_sha256`,
`last_source_payload_sha256`, `imported_at` oder keines davon.
Diese Metadaten bleiben passive Herkunftswerte; ihre gespeicherte Mapping-ID
fordert keinen Codeimport oder nachträglich erfundene lokale Mappingressource.
Unbekannte Top-Level-Felder sind unzulässig. Quellprojekte werden ohne Fetch,
Import aus Projektdateien, Remote-Resolver oder optionale Pakete gelesen.

JSON ist UTF-8 ohne BOM, ohne doppelte Schlüssel, NaN/Infinity, unpaarige
Surrogate oder nachfolgende Fremddaten. Zahlen müssen ohne Verlust im
RFC-8785/I-JSON-Bereich kanonisierbar sein; übergroße Integer werden nicht
gerundet. JSON-Whitespace einschließlich CRLF ist zulässig, Originalbytes
werden separat behalten. Keine Unicode-Normalisierung von Fachwerten.
Datums-/Akteursformen folgen den Quellschemas und den UTC-Regeln der Grundlage.
Sprachfelder werden gegen das hier bytegebundene `language-registry.txt`
geprüft; es gibt keinen Download und keine Bindung an das Host-Locale.
`default_locale` ist eine Darstellungsvorgabe und keine Migrationsautorität.

Alle Projekt-/Archiv-/Anhangspfade sind relative POSIX-Pfade ohne leere,
Punkt- oder Elternsegmente, Backslash, NUL oder absoluten Root. Symlinks,
Geräte und andere Spezialdateien sind als Quellressourcen unzulässig.
NFC-/Casefold-Pfadkollisionen werden abgewiesen; Originalnamen werden nicht
still umbenannt. Sicherheits- und I/O-Fehler bleiben eigenständige Fehler.
`.git`, `.specroad`, Cache, Locks, Journale und unreferenzierte generierte
Ausgaben sind kein normativer Quellbestand. Ein explizit gebundener generierter
Code-Payload folgt dagegen den Original-/Manifestregeln aus Abschnitt 6. Aktive/unklare Vorgänge werden nicht übergangen;
der Migrations-Preflight muss einen abgeschlossenen Quellstand verlangen.
Unreferenzierte zusätzliche nichtnormative Dateien dürfen vollständig
gesichert werden, erzeugen aber keine Modell- oder Gültigkeitsaussage.

## 4. Zustände, Unveränderbarkeit und Originalclosure

Die Zustands-/Maturity-Paare der Grundlage 9.6 gelten einschließlich
`recorded/approved` für Evidence und Relationsreviews sowie `sealed/approved`
für Baselines. Andere Kombinationen sind unzulässig. Proposals behalten
ihre dort vollständige Statusmatrix. Im neu definierten Referenzformat sind
`applied`, `rejected` und `stale` **abgeschlossene und unveränderbare**
Proposal-Fassungen. Bei `rejected`/`stale` bleibt ein etwaiger neuer Versuch
eine gesonderte Fassung; bestehende Originalbytes werden nicht reaktiviert.
Alle übrigen gültigen Proposal-Zustände sind als Ausgangsmaterial veränderbar;
ihre alten Reviews autorisieren keine geänderten 0.2-Planbytes.

Nach vollständiger Qualifikation klassifiziert der Leser:

- `immutable_legacy`: jede Evidence, Baseline und jeder Relationsreview sowie
  jedes abgeschlossene Proposal nach obiger Regel;
- `mutable`: übrige Quellartefakte, Projektkonfiguration und festes Quellprofil;
- `referenced_payload`: erforderliche Originalanhänge und Archivobjekte.

Diese Klassifikation ist kein Schreibrecht. Gleiche IDs mit unterschiedlichen
Originalbytes innerhalb desselben aktuellen Bestands sind Konflikte. Eine
archivierte ältere Revision darf im gebundenen historischen Snapshot daneben
existieren; sie ersetzt nie den aktuellen Bestand durch ID-Gleichheit.
Für unveränderbare Ressourcen bleiben **alle** Originalbytes, IDs, Schema-
Versionen, Revisionen, Metadaten und historischen Hashwerte unverändert.

Closure startet beim vollständigen aktuellen normativen Bestand und folgt
allen durch Schema/Fachvertrag typisierten Referenzen: Artefaktziele,
Evidence-Subjects und Anhangsdeskriptoren, Proposal-Basen/Pläne/Reviews,
Relationsreview-Endpunkte, Konfigurationen und Baseline-Snapshot-Einträge.
Historische Bindungen werden anhand des vollständigen Tupels aus ID,
Revision und Quell-Vollhash in einem passenden vollständig qualifizierten
Snapshot aufgelöst, nicht gegen einen heutigen gleichnamigen Datensatz.
Ein ausdrücklich gespeicherter Modellwurzel-/Baselinebezug grenzt die Suche
zusätzlich auf genau diesen Snapshot ein. Ohne solchen Bezug sind nur der
aktuelle Quellstand und die über Baseline-Manifeste erreichbaren historischen
Snapshots zulässige Originalquellen. Ein unverändertes Objekt darf in mehreren
Snapshots vorkommen; alle gebundenen Originalbytevarianten bleiben erhalten.
Gleiche Inhaltsadresse mit widersprechendem Inhalt ist ein Integritätsfehler,
kein Auswahlheuristikfall. Unregistrierte Archivdateien ersetzen keinen Beleg.
Frühere unveränderbare Nachweise in Baselines und deren weitere Snapshot-
Objekte werden transitiv geprüft. Aktive Snapshotbesuche erkennen Archivzyklen;
bereits vollständig geprüfte identische Inhalte werden dedupliziert.

Anhangsdeskriptoren enthalten `path`, `media_type`, `size`, `sha256` nach der
Grundlage. Größe und Bytehash müssen tatsächlichen Bytes entsprechen.
Code-Referenzen auf eine historische Fassung benötigen zu `file_sha256`
passende eingebettete Archivbytes; ein Git-Commit-Label allein ist kein
verfügbarer Payload. Lebende lokale Codepfade werden an ihre tatsächlichen
Bytes gebunden. Es gibt keinen Checkout-/Netzwerkfallback. Ein externer
Locator ohne eingebetteten Inhalt bleibt ein Locator und wird nicht zu
einem verifizierten Original hochgestuft. Text oder beliebige Strings in
Extensions werden nicht als versteckte Dateiverweise interpretiert.

Ein fehlendes Original, ein Größen-/Hashwiderspruch oder eine unaufgelöste
verpflichtende historische Bindung verhindert vollständige Qualifikation.
Nichts davon darf durch eine 0.2-Projektion, leere Ersatzdatei oder heutige
Hashformel ergänzt werden. Zusätzlich vorhandene Archivobjekte dürfen
erhalten bleiben, begründen aber keine fehlende Manifestreferenz.

## 5. Exakte Hashdomänen und Relationsherkunft

Alle Hashes sind vollständige kleingeschriebene SHA-256-Werte.
`J(value)` bezeichnet genau RFC-8785-UTF-8 ohne abschließende Newline.
Es gibt keine Locale-abhängige Sortierung und keine Unicode-Normalisierung.

| Kennung/Verwendung | Exakte Eingabe von SHA-256 |
|---|---|
| `reference01-original-bytes-v1` | Tatsächlich gespeicherte Dateibytes, einschließlich Whitespace und Newlines. |
| `reference01-full-jcs-v1` | `J(vollständiger gespeicherter JSON-Wert)`; kein Feld wird entfernt. |
| `reference01-relation-content-v1` | `J(vollständiges ursprüngliches Relationsobjekt)`; seine Arrayposition gehört zusätzlich zum Locator. |
| `reference01-relation-context-v1` | `J(P(Artefakt))` mit der nachstehend exakt definierten Projektion P. |
| `reference01-verification-context-v1` | `J(P(Artefakt))` mit derselben P; der Verwendungszweck und Algorithmus werden im jeweiligen Nachweis gebunden. |
| `reference01-proposal-basis-v1` | `J(B)` mit der geschlossenen Spezifikationsprojektion aus Abschnitt 5.2. |
| `reference01-model-root-v1` | `J(M)` mit der vollständigen Manifestprojektion aus Abschnitt 6. |

P entfernt ausschließlich die vorhandenen **Top-Level-Felder** `revision`,
`created_at`, `created_by`, `updated_at`, `updated_by`, `maturity`,
`implementation_status`, `verification_plan_status`, `verification_waiver`,
`relations`, `tags` und die vier Spezialstatusfelder `proposal_status`,
`evidence_state`, `baseline_state`, `review_state`. Alle anderen tatsächlich
vorhandenen Felder samt vollständigen verschachtelten Werten bleiben erhalten.
Kein Default und kein Entfernen gleichnamiger verschachtelter Extensionsfelder.
Die zwei Kontextkennungen haben absichtlich dieselben Projektionsbytes, aber
unterschiedliche Verwendungsbindung; sie sind **keine** Zusage, mit einem
gegenwärtigen 0.2-Kontexthash kompatibel zu sein.

Evidence bindet ihre ursprünglichen Subjects mit Quell-Vollhash und
Quell-Kontexthash. Relationsreviews binden den Locator, beide ursprünglichen
Endpoint-IDs/-Revisionen/-Vollhashes, ihre P-Kontexte und den vollständigen
Quellrelationshash. Der Locator muss im gebundenen Originalarray existieren;
seine `source_id` muss dem Review-Endpunkt entsprechen, und das ursprüngliche
Relationsziel muss die gespeicherte `target_id` sein. Alle gespeicherten Werte
werden nach genau diesen Regeln
geprüft. Ein alter gültiger Nachweis wird nach Zieltransformation nicht
automatisch aktuell; Q.4 verlangt weiterhin `migration_context_unverified`
und neue Zielnachweise. Bloß synthetische Beispielakteure sind keine echten
Human-Review-Nachweise.

Proposal-Inhaltshash und Reviewtuple folgen der eingefrorenen Grundlage
10.3, angewendet auf die tatsächlichen Quellwerte. Geschlossene gespeicherte
Change Plans folgen 10.1/K mit den typisierten Quellidentitäten/-Locatoren
und der Proposal-Basiswurzel aus 5.2 (einschließlich `expected_result`). Gespeicherter Planinhalt ist inert:
Lesen und Originalerhalt führen weder Operationen noch einen alten Apply aus.
Eine alte Planfreigabe erlaubt keine nachträgliche 0.2-Planumdeutung.

Die neue 0.2-Relations-ID wird ausschließlich nach dem unveränderten Q.3
aus `J(["specroad-relation-migration-0.1-to-0.2-v1", project_id,
source_artifact_id, original_zero_based_array_index, original_relation_json])`
abgeleitet. Die ersten 16 SHA-256-Bytes werden als vorzeichenloser Big-Endian-
Wert mit exakt 26 Crockford-Zeichen, führend mit Nullzeichen aufgefüllt,
kodiert; Alphabet `0123456789ABCDEFGHJKMNPQRSTVWXYZ`, Präfix `REL-`.
Arrayposition, ursprüngliche Relation und Projektbindung dürfen davor nicht
normalisiert, umsortiert oder durch eine Zielprojektion ersetzt werden.
Verschiedene Eingaben mit derselben ID sind ein Konflikt, keine Umbenennung.

### 5.1 Geschlossene gespeicherte Quellwerte in 1.0.1

Bei der Implementierung zeigte die Prüfung der eingefrorenen Grundlage zwei
weitere reine Feldlücken. H.2 definiert den Auswahlhash, aber keine genaue
Ankerfeldmenge; 10.3 definiert Bindungen und Übergänge, jedoch keine vollständige
persistierte Review-/Kontrollzeile. Vor dem Leser konkretisiert
REFERENCE-RELEASE-552 deshalb auch diese Felder gemäß SPECROAD-DECISION-1.
Das ist eine heutige Entwurfsentscheidung, keine historische Behauptung.

`code_ref.anchor` ist genau eine der geschlossenen Varianten
`{kind:"line_range",start_line,end_line,encoding}` (positive 1-basierte,
inklusive Zeilen; H.2-Dekodierung, CRLF/CR zu LF, UTF-8-Auswahlhash) oder
`{kind:"byte_range",start_offset,end_offset}` (nullbasierte halboffene
Bytepositionen, unveränderte Auswahlbytes). Endpositionen müssen innerhalb
der gebundenen Originaldatei liegen und mindestens der Startposition
entsprechen. Es gibt keine Heuristik für beliebige Ankerobjekte, keinen
Symbolresolver und keine automatische Relokation oder Source-Umschreibung.

Proposal-Reviews sind exakt `{binding,reviewer,reviewed_at,observed_revision,
decision}`. `binding` enthält genau `proposal_id`, `content_revision`,
`content_sha256`, `base_model_root_sha256`, `change_plan_sha256` nach 10.3.
Die Entscheidung ist `approved`, `rejected` oder `withdrawn`. Akteur und UTC
folgen den bestehenden Formen. `observed_revision` bindet eine tatsächliche
vorherige Originalrevision desselben Proposals aus der zulässigen Closure.
Alte Bindungen bleiben gespeichert; sie autorisieren keinen anderen Inhalt.

Kontrollzeilen enthalten genau `binding`, `actor`, `occurred_at`,
`observed_revision`, `from`, `to`, `reason`, `result_sha256` und
`result_bytes_base64`. Die Originalbytes des gespeicherten Prüfergebnisses
sind strikt Base64-kodiert, nichtleer und an ihren vollständigen Bytehash
gebunden. Die Übergänge, atomare Startfolge, Metadaten und Originalrevisionen
folgen weiter 10.3/K. Die gespeicherten Berichte sind historische Daten;
Hash- oder Formatgültigkeit ersetzt keine eingebauten Prüfungen, echte
Reviewauthentifizierung oder aktuelle Apply-Autorisierung. Der Reader erteilt
keine Freigabe aus dem Inhalt eines solchen Berichts.

Die geschlossenen Schemas binden diese Feldmengen. Positive Abnahmen umfassen
beide Ankerarten, ursprüngliche Zeilenenden, historische Reviewtupel und
unveränderte Kontrollresultatbytes. Negative Abnahmen umfassen Mehrdeutigkeit,
unbekannte Felder, falsche Positionen, fehlende Originalrevisionen, gebrochene
Tupel, ungültige Übergänge und manipulierte Resultatbytes. Die Freigabe- und
Provenienzgates bleiben zusätzlich erforderlich; keine neue Adapterautorität
oder neue Runtime-Registrierung wird durch diese Feldfestlegung geschaffen.

### 5.2 Geschlossene Proposal-Basis ohne Selbstreferenz

Die bisherige Projektwurzel aus Abschnitt 6 enthält Proposal- und Baseline-
Records. Sie eignet sich nicht als Proposal-Basis: Das eigene Proposal würde
seinen Inhaltshash mittelbar selbst binden. Ungeprüfte behauptete Wurzeln und
das Umetikettieren zu einem aktuellen 0.2-Modell werden verworfen. Die kleinste
konsistente Lösung konkretisiert die schon in 10.3 verlangte kontrollfreie
Spezifikationsbasis als eigene, ausschließlich quellbezogene Hashdomäne.

Der Basis-Scope ist exakt
`{scope_version:"scope-v1",scope_kind:"specification",selector:{},configuration_id:null,closure_profile:"core-closure-v1",boundary_policy:"closed"}`.
Aus einem vollständig qualifizierten Source-Snapshot werden seine
Konfiguration, sein festes Profil, alle Artefakte außer `proposal` und
`baseline` sowie die von den verbleibenden Artefakten benötigten Original-
Payloads gewählt. Ein Pflichtverweis dieser Artefakte auf einen ausgeschlossenen
Kontrollrecord verhindert eine geschlossene Proposal-Basis; er wird nicht
still entfernt. Kein Archivobjekt wird zusätzlich als eigener Basiseintrag
aufgenommen. Payloads stehen unter ihrem ursprünglichen logischen Pfad.
Die Pfadsortierung und die Rootzeilenprojektion sind genau die aus Abschnitt 6.

Die exakte Hashpräimage B lautet
`{algorithm:"reference01-proposal-basis-v1",project_id:<Quellprojekt-ID>,scope_descriptor:<Basis-Scope oben>,entries:<gewählte Rootzeilen>}`.
`Proposal.base.model_root_sha256`, die identische Planbasis und die erwartete
Planergebniswurzel verwenden `SHA256(J(B))`. Die vollständige Projektwurzel
und Baselinewurzeln bleiben ausschließlich in der Domäne aus Abschnitt 6.
Kontrollhistorien und zusätzliche Baselines verändern B nicht; Änderungen
an den enthaltenen Original-Fachwerten, Revisionen oder Payloads dagegen schon.
`vectors/proposal-basis.json` enthält eine unabhängig berechnete Präimage
und ihren Sollhash für das minimale Referenzprojekt.

Jede gespeicherte Proposal-Basis muss aus tatsächlichen Originalen des aktuellen
oder eines manifestgebundenen historischen Snapshots rekonstruierbar sein.
Ein unregistrierter Blob oder der Hash allein genügt nicht. Preconditions
werden ausschließlich gegen diese Basis geprüft; gespeicherte Operationen
bleiben inert. Ein leeres Operationsarray verlangt dieselbe Ergebniswurzel.
Ein später geänderter Projektstand darf ein älteres Proposal unverändert
bewahren, sofern dessen ursprüngliche Basis erreichbar bleibt. Die Inventur
weist dann `basis_matches_observed_snapshot=false` aus; die gespeicherte
Statusangabe wird nicht umgeschrieben und gewährt keine aktuelle Freigabe.
Auch ein passender Hash authentifiziert keine menschliche Entscheidung und
ersetzt keinen ausgeführten Check, Zielplan oder Apply. Die ursprünglichen
Revisionen und Kontroll-/Reviewbindungen bleiben zusätzlich Pflicht.

## 6. Vollständiger Snapshot und Baselinealgorithmus

Dieses neue Referenzformat definiert ausschließlich **geschlossene,
unkonfigurierte Projekt-Snapshots**. Das Scope-Objekt lautet exakt:

```json
{"scope_version":"reference01-scope-v1","scope_kind":"project","selector":{},"configuration_id":null,"boundary_policy":"closed"}
```

Ein vollständiges Snapshotmanifest ist eine nach relativen Pfad-UTF-8-Bytes
sortierte Liste ohne doppelte oder kollidierende Pfade. Jede Zeile erfüllt
`schemas/manifest-entry.json`: exakt `path`, `role`, `artifact_id`, `revision`,
`media_type`, `size`, `byte_sha256`, `canonical_sha256`.
`role` ist `configuration`, `profile`, `artifact` oder `attachment`.
Artefakte binden ID und positive Revision; andere Rollen setzen beide auf
`null`. Für normative JSON-Ressourcen ist `media_type=application/json`
und `canonical_sha256` der volle JCS-Hash. Für opaque Payloads ist
`canonical_sha256=null`; Typ, Größe und Originalbytehash bleiben gebunden.
Eine als Anhang gespeicherte JSON-Datei wird nicht allein durch ihren
Medientyp zur normativen Ressource; die Rolle bestimmt die Hashprojektion.

Der Snapshot enthält genau die vollständige Konfiguration, das feste Profil,
alle Artefakte seines erfassten Projektstands und alle dafür erforderlichen
Anhangspfade. Genau ein Primary-Document ist enthalten. Nichtnormative
Betriebsdateien und unreferenzierte Fremddateien einschließlich generierter
Ausgaben gehören nicht zu dieser Modellwurzel. Ausdrücklich durch einen
Code-Ref gebundene generierte Dateien sind hingegen erforderliche Original-
Payloads: Ihre tatsächlichen Bytes stehen unter dem logischen Pfad im Manifest;
sie werden weder ausgeführt noch regeneriert. Die gesonderte vollständige Quellsicherung
nach 16.d bleibt erforderlich und darf auch solche zusätzlichen Dateien
nicht still verlieren. Ein manifestierter Teilbestand darf keinen vollen
Projekt-Snapshot behaupten.

Für jede normative JSON-Zeile entsteht eine Rootzeile durch Entfernen von
`size` und `byte_sha256`; alle anderen Felder bleiben enthalten. Für jede
Attachment-Zeile bleiben **sämtliche** Felder einschließlich
`canonical_sha256=null` erhalten. Reihenfolge bleibt die Pfadsortierung.
Die exakte Rootprojektion M ist:

```text
{algorithm: "reference01-model-root-v1", project_id: <Quellprojekt-ID>,
 scope_descriptor: <exaktes Scope-Objekt oben>, entries: <Rootzeilen>}
```

`model_root_sha256=SHA256(J(M))`. Eine reine JSON-Whitespaceänderung ändert
den Originalbytehash, aber nicht diese semantische Modellwurzel. Binärbytes,
Fachwerte, Pfade, IDs, Revisionen und Profil-/Konfigurationswerte bleiben
wirksam. Es gibt keinen selbstreferenziellen Hash über eine Baseline, die
gerade ihre eigene Erzeugung beschreibt.

Eine Baseline hält das vollständige Manifest des **vor ihrer Erzeugung**
beobachteten Quellstands, Scope, `project_id`, `model_root_algorithm`,
`model_root_sha256`, `profiles=["core-reference01@1.0.0"]` und ihren
regulären Quellrecord. Ihr eigener Record ist in ihrem Snapshot ausgeschlossen;
frühere bereits vorhandene Baselines sind enthalten. Falsch behauptete
Selbstreferenz oder zyklische Snapshot-Abhängigkeiten sind unzulässig.
`configuration_hash` ist, falls vorhanden, `null`.

Zu jeder Manifestzeile werden die **originalen Dateibytes** unter
`archive/objects/<erste-zwei-hex>/<byte_sha256>` gespeichert. Der Dateiname
bindet SHA-256 dieser Bytes. Anders als beim heutigen 0.2-Objektaufbau wird
für diesen ausdrücklich neuen Quellalgorithmus nicht vorab umformatiert.
Identische Objekte dürfen dedupliziert werden; vorhandene andere Bytes unter
derselben Adresse sind ein Fehler. Historische Baseline-Records in diesen
Objekten werden mit ihren eigenen Manifesten transitiv geprüft. Eine
Baseline belegt die Integrität des deklarierten Snapshots, nicht automatisch
seine externe Herkunft oder einen echten früheren menschlichen Review.

Für Code- und Prose-Payloads ohne eigenen Evidence-Anhangsdeskriptor gilt
`media_type=application/octet-stream`; Größe und Bytehash werden aus den
gebundenen Originalen bestimmt. Ein vorhandener gleichnamiger Deskriptor
behält seinen Medientyp, muss aber dieselben Bytes und dieselbe Größe binden.
Die sicheren lokalen Attachmentverweise der eingefrorenen Markdown-Semantik
gehören ebenfalls zur vollständigen Closure. Externe Source-Locators bleiben Locator;
kein Netzwerkaufruf, Renderer oder Source-Code wird dabei ausgeführt.

### 6.1 Explizite Release-Auswahl in Vertragsversion 1.0.1

Für `baseline_kind=release` sind `release_id` und `verification_evaluation`
Pflicht. `release_id` bezeichnet genau ein Release-Artefakt im vollständig
qualifizierten **gebundenen historischen Snapshot**. Dessen Manifestzeile
bindet die tatsächliche Revision und den vollständigen Quell-JCS-Hash.
Gleicher Name, heutiger Bestand oder identische Evaluationsdaten eines
anderen Release ersetzen diese Bindung nicht. Ohne ID wird nie die erste,
einzige oder scheinbar passende Release ausgewählt.

`verification_evaluation` muss den vollständigen eingefrorenen Vertrag
10.5.1 erfüllen und als JSON-Wert exakt mit
`Release.readiness_policy.verification_evaluation` übereinstimmen. Der Scope
für die Release-Auswertung wird eindeutig als
`{scope_version:"scope-v1",scope_kind:"release",selector:{release_id:<ID>},configuration_id:null,closure_profile:"core-closure-v1",boundary_policy:"closed"}`
gebildet. Er ist von dem unverändert vollständigen Projekt-Snapshot-Scope
zu unterscheiden. Eine abweichende konfigurierte Release-Auswertung ist in
diesem unkonfigurierten Source-Snapshot unzulässig. Es gibt keine zusätzliche
`release_selection`-Manifestrolle, keine Scope-Ersetzung und keine Auswahl
anhand einer Evaluationskennung. Mehrere Releases dürfen denselben gültigen
Evaluationswert besitzen; nur die explizite ID entscheidet.

Bei `baseline_kind=working` ist `release_id` verboten. Eine dort vorhandene
passive `verification_evaluation` muss ebenfalls 10.5.1 erfüllen, erteilt
aber keine Release-Zuordnung. Die gespeicherten Readiness-/Evidence-Verträge
der Grundlage bleiben zusätzlich erforderlich, mit den expliziten
Quellhashdomänen; ohne erforderliche Nachweise gibt es keine Releasefreigabe.
Strukturelle Source-Qualifikation und Integrität authentifizieren weder
synthetische Reviewer noch eine aktuelle menschliche Entscheidung. Der
Source-Leser darf keine neue Releasefreigabe oder aktuelle 0.2-Readiness
behaupten. Unveränderte historische Nachweise bleiben erhalten.

`vectors/release-binding.json` beschreibt positive und negative
Auswahlbindungen als unabhängige Sollbedingungen. Dies sind bewusst keine
vollständigen positiven Releasefreigaben; die vollständige 16.b-Abnahme muss
die vorhandenen Review-/Evidence-Verträge zusätzlich tatsächlich prüfen.
Der Arbeitsbaseline-Vektor erfindet keine solche Freigabe.

## 7. Zielmigration, Unterstützung und Fehlergrenzen

Die spätere Migration verwendet ein getrenntes Source-Modell. Sie darf
0.1-Originale weder durch Ersetzen des Versionsstrings im aktuellen Loader
qualifizieren noch mit dem aktuellen Writer zurückschreiben.
Ein migriertes veränderbares Artefakt behält seine ID und erhält
`id_scheme=legacy-sequential-v1`. Relations-IDs folgen Abschnitt 5/Q.3.
Revision, Akteur und UTC-Zeit folgen K.4. Inhaltlich veränderte Freigaben und
Proposals folgen den bestehenden Invalidierungsregeln; keine neue Approval
entsteht aus Formatvalidierung oder einem vorhandenen alten Status.

Für jedes veränderbare Requirement ist das explizite Mapping nach S.7 nötig:
ID, erwarteter alter Vollhash, Zielsprache, Zielverbindlichkeit und geprüfter
Zielsachverhalt. Die Referenzformatentscheidung selbst erteilt **keine**
inhaltliche Mappingfreigabe. Fehlende Sprache/Verbindlichkeit wird nicht aus
Text, Priorität, Host-Locale oder einem anderen Artefakt abgeleitet. Pflicht-
angaben der aktuellen Zielkonfiguration, Zielprofile und Sprachressourcen
müssen ebenfalls explizit gebunden sein; die feste Source-Profilkennung wird
nicht als vorhandenes Zielprofil ausgegeben. Fehlende Zielangaben bleiben
sichtbare Planblocker, während die unabhängig gültige Quellinventur möglich ist.

Unveränderbare Records bleiben in ihrem ursprünglichen Format und erhalten
ausschließlich die Manifest-/Navigationsprojektion aus Q.2–Q.4. Die
Source-Vertragskennung/-version und der volle Manifesthash werden in
`migration_provenance` gebunden; die Legacy-Reader-ID ist
`specroad.reference01.v1_0_1`. `source_model_root_sha256` verwendet Abschnitt 6.
Die 0.2-Modellwurzel bindet weiterhin `legacy-original-bytes-v1`, Originalhash
und Legacy-Manifest. Eine spätere Verification alter Baselines verwendet
deren gespeicherten Source-Algorithmus, nicht den neuen Zielalgorithmus.

Nicht unterstützte oder fehlende Vertragskennung, lokale Schemafehler,
Identitäts-/Zustandswidersprüche, fehlende Closure und Hashfehler verhindern
jede positive vollständige Source-Qualifikation. Maschinenlesbare Gründe
sind mindestens `source_contract_required`, `unsupported_source_contract`,
`source_schema_invalid`, `source_identity_conflict`, `source_state_invalid`,
`source_resource_unsupported`, `source_closure_incomplete`,
`source_payload_missing`, `source_hash_mismatch` und `source_snapshot_cycle`.
Die spätere CLI ordnet sie den bestehenden Fehlerklassen zu; Format-/
Validierungsfehler bleiben Code 3, Sicherheits-/I/O- und stale Fehler werden
nicht in ein erfolgreiches Teilergebnis oder einen anderen Fehler umgedeutet.

Eine generische Downgradezusage entsteht nicht. Rückwege benötigen weiterhin
eigene vollständige Implementierung, Vorbedingungen und Verlustfreiheits-
nachweise nach 12.20.1. Ein Source-Vertrag ist kein automatisch inverser
0.2-Transformator. Ohne fertigen nativen Pfad bleibt das produktive Register
unverändert und Restore weist das Format weiter sicher ab.

## 8. Normative Vektoren und vollständige offene Abnahmen

`vectors.json` bindet echte gespeicherte Beispiele und erwartete Fachwerte:
eine vollständige minimale Source-Projektstruktur, ihre vollständige Inventur
und Modellwurzel, einen versiegelten Arbeitsbaseline-Record mit tatsächlichen
Archivoriginalen, unveränderbare Klassifikationsfälle, Original-/JCS-Hash-
trennung, unveränderte Unicodewerte, Q.3-Relationsableitung und eine explizit
gemappte Requirement-Transformation. Erwartete Zielbytes liegen separat vor;
sie werden im späteren Test nicht aus dem zu prüfenden Transformator erzeugt.
Die beiden primitiven JSON-Hashvektoren sind ausdrücklich **keine** gültigen
Artefakte. Klassifikationszeilen sind Sollbedingungen, keine vollständigen
positiven Recordfixtures. Akteure, Zeiten und Freigabeeingaben sind synthetisch.

Dies sind normative Eingabe-/Ergebnisvektoren, keine beobachtete Evidence.
Schema-/Referenzbindung und Paketprüfung dürfen nicht als bestandenes
Reader-, Migrations-, Restore- oder Releasegate ausgegeben werden.
Die vollständige 16.b-Abnahme ergänzt gültige Fachfixtures für **alle 28
Typen**, alle Spezialzustände, jede verpflichtende Referenzart sowie weitere
historische Generationen. Sie beobachtet unveränderte Originalbytes und
keine Schreib-, Codeimport-, Prozess- oder Netzwerknebenwirkungen.

R umfasst unbekannte/fehlende Kennungen, fremde 0.1-Labels, falsche Typen,
fehlende Pflichtfelder, Dubletten, ungültige UTC-/Sprachwerte, JSON-/Unicode-
Grenzen, unerlaubte Ressourcen, ID-/Pfadkonflikte, unklare Zustände, Symlinks,
fehlende und veränderte Payloads, transitive Baselinefehler, Zyklen sowie
gleichnamige heutige und historische Revisionen. Fehler erhalten Originale.
Native Core-/PYZ-Parität wird ohne optionales Paket und ohne aktuelle
Source-Writerfähigkeit nachgewiesen. C trennt Reader, Inventur, Bindungen
und spätere Projektionen bei unveränderten W-/R-Oracles.

Die weiteren M16-Gates bleiben vollständig erforderlich: read-only Planung,
vollständige verifizierte Quellsicherung, autorisierte Sprach-/Fachzuordnung,
deterministische Relationsmigration, verlustfreie Originalerhaltung,
Legacy-Manifest und Hashdomänen, aktuelle Zielvalidierung, Work/Transaktion,
Wiederholung sowie Restore-/CLI-Integration. Q.0 ist durch diesen Vertrag
fachlich konkretisiert; **16.b.W und alle Implementierungsnachweise bleiben
offen**, bis ihre tatsächlichen Apply-Gates und Commits vorliegen.
