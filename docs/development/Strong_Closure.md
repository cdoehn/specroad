# Starke Closure – Entwicklungsgrenze

Schritt 3.g berechnet den kleinsten Fixpunkt starker Beziehungen und explizit
gebundener Ressourcen auf dem bereits eingeführten `ScopeSeeds`-/`ScopeSeedInputs`-
Vertrag. Produktdateien werden weder gelesen noch geschrieben; es gibt keine
Netzwerk-, Plugin-, Shell- oder Cacheoperation.

## Eingaben und Verantwortung

`ClosureBindings(inventory, uses=..., current_reviews=..., attachments=...)`
bindet die Beobachtungen an die exakten Originalbytes der Quellartefakte sowie
die Ressourcenversionen und Hashes des gelieferten Inventars. `ClosureNode`
trennt Artefakt- und Ressourcenidentitäten. Ein Ressourcenname ist kein Pfad,
der vom Algorithmus geöffnet wird.

`uses` enthält für jede erreichte Quelle ihre tatsächlich verwendeten Ressourcen.
Ein explizites leeres Tupel bedeutet: Der zuständige Resolver hat keine solche
Abhängigkeit gefunden. Eine fehlende Zuordnung ist dagegen ein Fehler. Dieselbe
Regel gilt für `current_reviews`: Der spätere Reviewdienst muss pro enthaltener
Relation die tatsächlich aktuellen Reviews liefern. Gespeichertes `approved`
oder ein gleichlautendes `relation_id` allein ist kein Frischenachweis.
Diese API prüft Zuordnung und Datenbindung, nicht die Echtheit dieser Beobachtung.

Die Bestimmung von Profilverwendung, Regel-/Mappingkomposition, tatsächlicher
Reviewfrische und atomarer Inventur wird nicht durch eine leere Standardannahme
ersetzt. Testhilfen dürfen explizit leere Zuordnungen aus ihren bekannten
synthetischen Fixtures erzeugen; diese Hilfen sind kein Produktresolver.

Evidence-Subjects, nichtleere Test-IDs in `verification.evidence_slots`,
referenzierte Evidence-Anhänge und die expliziten Archiveinträge erreichter
Baselines werden an ihren definierten Datenpositionen ausgewertet. Historische
Evidence-Hashes werden nicht gegen heutige Artefakte als Erfolgsbedingung geprüft:
stale Evidence verliert dadurch nicht ihre notwendige Subject-Referenz.
Freitext, `extensions` und beliebige dort enthaltene IDs/Pfade bleiben passive Daten.

Ein Anhang wird über den vollständig beobachteten Descriptor zugeordnet: Pfad,
Medientyp, Byteanzahl und SHA-256 müssen mit seiner gespeicherten Deklaration
übereinstimmen. Der vorgelagerte Anhangsreader prüft die tatsächlichen Bytes;
der Closure-Algorithmus öffnet sie nicht erneut.

## Ergebnis

`resolve_strong_closure(seeds, bindings)` enthält jede stark erreichbare Quelle
genau einmal. Pro Iteration wird die kleinste offene Ressourcenidentität nach
UTF-8-Bytes verarbeitet. Wieder erreichte Identitäten werden dedupliziert;
auch zyklische Abhängigkeiten terminieren, ohne einen Zyklus ungeprüft als
zulässige `refines`-/Dokumenthierarchie freizugeben. Die separate Hierarchieprüfung
bleibt erforderlich. `rejected` und `retired` werden nicht ausgesiebt.

Das Ergebnis ist **strong_closure_over_supplied_bindings** und ausdrücklich
**closure_complete=false**, **atomic_snapshot=false**. Noch nicht behandelte
schwache Relationen stehen unter `pending_weak_relations`; es gibt hier weder
Boundary References noch einen vollständigen Scope- oder Modellhash. Die
Originalreihenfolge gebundener Query-Seeds bleibt erhalten. Fachliche
Konfigurationsfilter benötigen weiterhin ihren eigenen Resolver; sie werden
nicht still ignoriert. Kontrollartefakte werden im specification-Scope bereits
als Sicherheitsvorbedingung zurückgewiesen; die vollständige Diagnoseanbindung
und kombinierte Policy-Abnahme aus 3.i bleiben offen.

Die Hashbindung ist kein digitaler Herkunftsbeweis. Eine erneute Auswertung
benötigt frische Beobachtungen aus den zuständigen Diensten. Die reine
Berechnung erteilt keine Review-, Release-, Schreib- oder Transaktionsfreigabe.

## Tests

Verhaltenstests prüfen tatsächliche Mengen, Datenbindungen, Fehlzustände,
Deduplizierung und erhaltene Eingabedaten, nicht menschliche Ausgaben. Der
parallele Entwicklungsstandard und die serielle Vergleichsprüfung bleiben
unverändert. Keine Test-/Suite-Timeouts, keine übersprungenen Pflichtprüfungen.

## Ergänzte Robustheit und Wiederprüfung

Das Ergebnis enthält je ausgewähltem Artefakt den kanonischen JSON-Hash,
je anderer Ressource deren gelieferte Versions- und Hashbindung sowie die
vollständigen Anhangsdeskriptoren. `observation_sha256` bindet diese Beobachtung,
ist aber ausdrücklich nicht der spätere normative Scope-Hash. Die Datenansicht
liefert unabhängige Kopien und enthält keine ursprünglichen Fachtexte.

`require_strong_closure_current(old, seeds, fresh_bindings, query_page=...)`
berechnet erneut aus den frisch gelieferten Beobachtungen. Änderungen der
Quelle, Versionsbindung, Ressourcennutzung oder Reviewauswahl machen das alte
Ergebnis ungültig. Bei einem aktuellen Fehler wird niemals das alte erfolgreiche
Ergebnis ersatzweise verwendet. Die Funktion liest selbst keine Dateien: Der
Aufrufer muss die Eingaben vorher durch die zuständigen Reader erneuern.

Query-Scopes verlangen den tatsächlichen gebundenen `QuerySeedPage`; ein frei
konstruiertes Seed-Objekt allein wird nicht als Queryergebnis akzeptiert. Dies
ist weiterhin keine eigene Query- oder SRX-Engine. Aktuelle Reviews müssen neben
ihrer Relationszuordnung auch ihren gespeicherten Feldvertrag erfüllen. Dadurch
wird noch keine Reviewfrische oder Echtheit attestiert.

## Interne Arbeitsmenge

Die offene Menge, die besuchten Identitäten und die Verarbeitungsfolge sind in
einer separaten identitätsbasierten Arbeitsliste gekapselt. Die kleinste offene
UTF-8-Identität wird über einen Heap gewählt. Abhängigkeitsregeln kennen keine
Heapdetails; Verhalten, Fehler, ausgewählte Mengen und Hashverträge bleiben
unverändert. Diese Strukturgrenze ist für den späteren fortsetzbaren Workdienst
vorgesehen, implementiert aber noch keine Checkpointdatei oder Wiederaufnahme.
