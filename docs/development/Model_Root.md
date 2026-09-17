# Modellwurzel und Projektbindung (2.p)

## Verwendung und Nachweisgrenze

`capture_model_inputs(source, resource_paths, attachments=...)` liest eine
**explizite** Ressourcenmenge unter einem bereits gebundenen `ProjectSource`.
`assemble_model_manifest` verbindet diese Ressourcen mit einem Scope Descriptor,
der semantischen Projektkonfiguration und einer **explizit übergebenen**
semantischen Profilprojektion. `prepare_model_root` verbindet Lesen, Zusammenbau
und erneute Byteprüfung. Diese API führt keine versteckte vollständige Inventur aus.

Der zurückgegebene SHA-256 ist tatsächlich der Hash der kanonischen Manifestbytes.
`validation_scope=manifest_inputs_only`, `closure_verified=false`,
`profile_composition_verified=false` und `atomic_snapshot=false` bleiben jedoch
explizit. Ein Hash beweist weder Vollständigkeit noch Freigabe. Der spätere
Scope-/Profilkern muss vollständige Mengen und effektive Policies liefern;
Transaktionen prüfen die Basis zusätzlich unter ihrem Lock. Insbesondere ist ein
`project`-Descriptor allein kein Nachweis einer vollständigen Archivclosure.

Derzeit unterstützt sind unkonfigurierte `project`, `specification` und `explicit`
Descriptorformen. Andere Scopearten werden ausdrücklich zurückgewiesen, nicht
auf einen anderen Umfang reduziert. Die vollständige Scopelogik folgt in
Meilenstein 3. Auch Einzeldokument-, Query- und Variantenauflösung werden dort
implementiert. Kein CLI-Befehl wird hier als bereits fertig ausgegeben.

## Hashdomänen

Artefakte werden nach UTF-8-IDs sortiert; Ressourcen nach Identität und Version;
Anhänge nach sicherem relativem Pfad. Normative JSON-Ressourcen verwenden ihren
vollen JCS-Hash, einschließlich Auditwerten. Anhänge binden Pfad, Medientyp,
Byte-Länge und Bytehash. Konfiguration wird **nur einmal als semantische
Projektion** gebunden, niemals zusätzlich über den rohen specroad.json-Bytehash.

Scope-Hash: JCS/SHA-256 des Projektbezugs, Descriptors, der geordneten Ressourcen,
Boundary References und Konfigurations-/Profilhashes. Modellmanifest:
`model_manifest_version=model-manifest-v1`, diese Werte und `scope_sha256`.
Seine vollständigen JCS-Bytes bilden die Modellwurzel. Diese Grundlagen-API
ändert keine bereits gespeicherten Baseline-/Legacy-Hashes.

Die Profilprojektion ist ein erforderliches Datenargument. Es wird keine
Profilkomposition erfunden. Eine explizite leere Projektion für eine Testfixture
ist kein Beleg dafür, dass ein produktives Projekt ohne Coreprofil gültig wäre.
Versionierte Dateiresourcen deklarieren `<kind>_id` und `<kind>_version` oder `version`; widersprüchliche
Doppelangaben werden abgewiesen. Namen
werden nicht aus Dateinamen geraten. Weitere Schemavarianten gehören zum
späteren tatsächlich definierten Ressourcenschema.

## Fachliche und betriebliche Werte

CLI-Locale, generierter Ausgabepfad, automatische Recovery-Auslösung sowie
bekannte weiche Mengen-/Rechenziele sind keine Hashbestandteile. Harte Parser-/
Strukturgrenzen, fachliche Tracetiefe, Query-Paginationdefault, Freigabepolicies,
Inhaltssprache, Registerbindung, Paketversionen und SRX-Präzision bleiben gebunden.
Unklassifizierte Ressourcenlimits werden zurückgewiesen, nicht geraten.

Bekannte normative Defaults für Query-Pagination und SRX-Arithmetik werden
materialisiert. Weitere effektive Profil-/CLI-Policies müssen zuvor vom
zuständigen Resolver bereitgestellt werden. Extensions werden nicht rekursiv
nach vermeintlich betrieblichen Schlüsseln gefiltert: sie bleiben normative Daten.

## Lokale Lesebindung

Projekt-ID, konkreter Root und dessen Dateiidentität müssen für alle Ressourcen
übereinstimmen. Diese lokale Herkunftsprüfung ist **kein Bestandteil** des
portablen Hashes. Eine identische Projektkopie erhält deshalb dieselbe Modellwurzel,
aber die alte Lesebeobachtung berechtigt nicht zum Zugriff auf die Kopie.
Alle ausgewählten Originalbytes werden vor Rückgabe erneut geprüft; erkannte
Änderungen führen zum Fehler. Das ersetzt keinen atomaren Mehrdatei-Snapshot.

Testfallzuordnungen bleiben partiell. Keine Ausgabe-, Dokumentations- oder
Layouttests; fachliche Manifeste und Hashdomänen sind maschinenlesbare Verträge.
Keine neue Laufzeitabhängigkeit, keine Projekt- oder Cachewrites, keine
Netzwerkanfrage und keine Ausführung von Profil-/Extensiondaten.

## Boundary References und Endprüfung

Partielle, ausdrücklich übergebene Boundary References binden Quelle,
Relations-ID soweit vorhanden, Relationstyp, Zieltyp, Ziel-ID, Grund und
Ursprungszielhash. Geordnet wird nach den UTF-8-Bytes des Tupels
(source_id, relation_id oder leer, target_id). Duplikate, fehlende enthaltene
Quellen, bereits enthaltene Ziele und Boundaries im closed-Scope sind Fehler.
Starke Beziehungen werden nicht als schwache Boundary ausgegeben.
`boundary_relationships_verified=false` bleibt jedoch ausdrücklich: Existenz
und genaue Übereinstimmung mit echten Kanten sind Aufgabe des Scopekerns,
keine aus einem Inputhash ableitbare Eigenschaft.

Konfigurierte Register werden über den vorhandenen Offline-Registerlader an
Date und Inhalt gebunden. Beschädigte oder fehlende Originale führen zum
Fehler statt zum automatischen Ersatz. Nach dem Manifestzusammenbau werden
sämtliche ausgewählten Originaldateien nochmals geprüft. Dies erkennt
beobachtete Änderungen, bietet jedoch keine atomare Lesetransaktion.
