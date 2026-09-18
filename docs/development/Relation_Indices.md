# Eingehende und ausgehende Relationsindizes

Planschritt: **3.e.W / 3.e.R / 3.e.C**. Anforderung: **SR-REQ-0582**.

## Öffentliche Bausteine

`specroad.graph.indices.RelationIndex` baut aus `RelationReferences` beide
Adjazenzrichtungen auf. Das Objekt beschreibt nur seinen ausdrücklich
übergebenen Datenbestand (`supplied_relation_set_only`). Es kann die
Vollständigkeit eines Projekts nicht aus einem Flag, einem Zeitstempel oder
einem einzelnen geladenen Zielartefakt ableiten.

Für eine aktuelle projektbezogene Anfrage:

```python
from specroad.storage.project import ProjectSource
from specroad.storage.relation_index import (
    build_project_relation_index, read_project_relation_views,
)

source = ProjectSource(project_directory)
prior = build_project_relation_index(source)
result = read_project_relation_views(
    source, selected_artifact_id, direction="incoming", index=prior,
)
reference = read_project_relation_views(
    source, selected_artifact_id, direction="incoming", strategy="scan",
)
assert result == reference
```

Beide Lesewege verwenden vollständige aktuelle Artefaktquellen. `scan` benötigt
keinen Adjazenzindex. Die Auswahl der zurückgegebenen Artefakt-ID schränkt nur
das Ergebnis ein, niemals die eingelesenen Quellen. Eine vollständige Anfrage
liefert alle zutreffenden Beziehungen, nicht nur eine Anzeigeseite.

## Vollständigkeit und Aktualität

Der Reader ermittelt alle als Artefakte klassifizierten JSON-Dateien der
konfigurierten aktuellen normativen Verzeichnisse. Dazu gehören auch dort
liegende stillgelegte Artefakte. Archivobjekte, unreferenzierte Anhänge,
generierte Dateien und Betriebsdaten sind keine aktuellen Relationsquellen.
Profile und Regeln sind getrennte Ressourcen, keine impliziten Artefaktkanten.

Jede Quelle wird unter der vorhandenen Projekt-/Pfad-/Identitätsgrenze gelesen.
Relationsfelder, Zielauflösung, Quell-/Zielmatrix, globale Relationskennungen
und kanonische Speicherung symmetrischer Beziehungen werden geprüft. Eine
kaputte oder unlesbare unselektierte Quelldatei macht die Anfrage ungültig;
es wird kein angeblich vollständiges Teilergebnis zurückgegeben.

Die Bindung enthält Projekt-ID, lokalen Root und dessen Identität, die
ursprünglichen Konfigurationsbytes als SHA-256 sowie die vollständige geordnete
Liste relativer Quelldateinamen mit SHA-256. Ihr Hash ist ausdrücklich **kein
Modellwurzelhash** und keine Signatur. Lokale Geräte-/Inodewerte werden im
Hashdokument als Dezimalstrings kodiert, damit große Betriebssystemwerte nicht
auf Binary64 gerundet werden.

Die erfassten Bytes und Dateimengen werden nochmals vor Rückgabe geprüft.
Hinzukommende Quellen, gelöschte Quellen, geänderte Inhalte und veränderte
Konfigurationen können nicht durch den alten Index verdeckt werden. Gleiche
Dateigröße und gleicher Änderungszeitstempel reichen nicht als Frischenachweis.
Ein vorhandenes `ProjectSource` mit geänderter Konfiguration schlägt fehl; ein
neuer Aufruf kann einen frischen Reader ausdrücklich erzeugen.

## Cache ist nur ein Hinweis

`index` akzeptiert einen zuvor erzeugten `ProjectRelationIndex`, einen reinen
`RelationIndex` oder `None`. Andere Objekte, insbesondere JSON mit einem
behaupteten `complete: true`, werden nicht als Nachweis akzeptiert.

Nur ein inhaltlich exakt zur frisch erfassten vollständigen Quellbeobachtung
passender, lokal gebundener Projektindex wird wiederverwendet. Ein alter,
fremder oder nicht projektgebundener Teilindex wird aus den aktuellen Quellen
neu aufgebaut. Ungültige aktuelle Quelldaten erlauben keinen Rückgriff auf
frühere Erfolgsdaten. Indexobjekte und Eingabedateien werden dabei nicht verändert.

Dieser Schritt definiert **kein persistentes Cacheformat** und erzeugt keine
Cachedateien. Deshalb ändert auch das Löschen bestehender Cacheeinträge die
fachlichen Ergebnisse nicht. Die vollständige Dateisichtung bleibt bewusst
notwendig: Eine künftig schnellere Validierung benötigt einen eigenen,
nachweislich vollständigen Aktualitätsvertrag. Es gibt keinen mtime-only-Schnellweg
und keine Behauptung, diese Grundimplementierung sei bereits eine inkrementelle
Indexengine.

## Richtung und Identität

`incoming`/`outgoing` beziehen sich auf die physische Speicherrichtung. `both`
vereinigt die Sichten. Die berechnete Gegenrichtung erhält dieselbe Relations-ID,
`inverse=True` und `normative=False`. Bei `supersedes` heißt die Gegenansicht
`superseded_by`. Symmetrische Beziehungen werden von beiden Endpunkten sichtbar,
aber nicht ein zweites Mal normativ gespeichert. Anzeigenamen und externe
Kennungen ersetzen niemals Artefakt-IDs.

## Grenzen und Tests

`coverage_scope=current_project_artifacts` gilt ausschließlich für die
beobachteten aktuellen Artefaktquellen. `atomic_snapshot=False` bleibt explizit:
Wiederholte Leseprüfungen ersetzen weder einen Mehrdatei-Snapshot noch einen
Transaktionslock. Nach Rückgabe können sich Dateien erneut ändern. Der
projektbezogene Reader prüft deshalb bei jedem neuen Aufruf frisch; das alte
Indexobjekt allein ist keine aktuelle Lese- oder Schreibberechtigung.

Noch keine vollständige Scope-Closure, automatische Lebenszyklus-/Reviewfreigabe,
CLI-Anbindung, Profilprüfung oder persistente Indexverwaltung. Der spätere
Scope- und Authoring-Code muss diese Bausteine ausdrücklich nutzen. SR-REQ-0582
bleibt deshalb im Anforderungskatalog teilweise umgesetzt, nicht pauschal bestanden.

Die neuen Verhaltenstests prüfen selektive Zielabfragen auf vollständigen
Quellen, unabhängigen Scan, Teilindizes, verlorene Cacheeinträge, späte und
entfernte Quellen, nachgestellte Änderungen, unsichere Pfade, Quelldatenfehler,
Originalbyte-Erhalt und verschobene Modul-/Zipapp-Distributionen. Tests verwenden
ausschließlich eigene temporäre Projekte; keine Darstellungs-/Dokumentationstests.
Die bestehende parallele Entwicklungs-Testpolicy bleibt unverändert.
