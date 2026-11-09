# Bundle 650 — geordnete Proposal-Änderungen

9. November 2026. Quelle ist das vollständige erfolgreiche Result
`bacb3d5687775b50d759d3c3c5c3112f1e1b5af471fdd6b6fac7b3c28116a9a9`, Base-Commit
`2c806cfb6c5bf81d345f0718edc1e1c3e4242b6e`.
Es belegt 18.b.R mit 9.165 und 18.b.C mit 9.272 bestandenen ausgewählten
Tests sowie einen sauberen Abschluss. Damit sind 735/900 Planpositionen
bestätigt. Diese bereits erfolgreichen Commits werden nicht wiederholt.

Die bestehende Spezifikation 10.3.1, 11.10 und R-06 bestimmt Identitäten,
Zuordnung und Positionsregeln vollständig. Keine neue Detailklärung und
keine Budgetänderung. Das Bundle enthält ausschließlich die drei aufeinander
aufbauenden Implementierungsstufen 18.c.W, 18.c.R und 18.c.C.

## Umsetzung und Grenzen

`ProposalChanges` übernimmt einen vollständigen nativen Proposalentwurf und
ordnet Operationen und Erläuterungen gemeinsam. Add vergibt eine eindeutige
CHG-ID mit dem bestehenden random128-v1-Token, hängt standardmäßig an oder
fügt am angegebenen nullbasierten Index ein. Get, Update, Remove und Move
adressieren die stabile ID. Move entfernt zuerst und fügt in die Restliste
ein; gleiche Position erhält den gebundenen Plan ohne neue ID. Jede Änderung
besitzt eigene unveränderliche Werte; Aufrufermutationen verändern keine Quelle.

Jeder Aufruf verlangt einen vollständigen nativen Zielplan. Seine Operations-
folge muss genau der angeforderten Änderung entsprechen, seine Basis bleibt
gleich. Unbeteiligte Operationen und ihre Erläuterungen bleiben erhalten.
Ergebnisartefakte, Planhash und Wurzel werden nicht still aus dem Quellplan
als neues Ergebnis übernommen. Die Strukturprüfung des nativen Plans ersetzt
keine Prüfung eines lebenden Zielmodells. Der Integrationsfall rekonstruiert
beide echten Ziele zweier nicht kommutativer Änderungen über den nativen Fold.

Der Wert bleibt deklarative Vorbereitung ohne Schreib- oder Reviewbefugnis.
Er erzeugt keine neue gespeicherte Proposalrevision und keinen öffentlichen
CLI-/Writerabschluss. Revisionsführung, Lifecycle und öffentliche Integration
bleiben den folgenden 18.d/18.e- und M18-Integrationspositionen zugeordnet;
die betroffenen Requirement-Kataloge führen diese Grenze ausdrücklich als
`partial`. Es gibt keine neue Spezifikationsausnahme oder verkürzte Abnahme.

## Getrennte Abnahmen

- W: vollständige append/insert/move-Funktionen, ID-basierte Einzelbearbeitung,
  Grundgrenzen, native Plan-/Basisbindung und nicht kommutative Zielrekonstruktion.
- R: komplette Positionsmatrix, leere/einelementige Folgen, Wiederholungen,
  fehlerhafte Positionen und IDs, Kollisionsfolge und Entropiefehler. Ungültige
  Plan-/Herkunftsdaten scheitern vor der ID-Vergabe; alle W-Fälle bleiben Pflicht.
- C: eigenständige Identitätsprüfung/-vergabe ohne Arraypositionen oder
  menschliche Nummerierung. Verhalten, Fehlerverträge und R-Tests bleiben gleich.

Vorbereiteter R-Zustand: Die Fortschrittswerte gelten erst nach dem
erfolgreichen eigenen Apply-Gate und Commit. C ist zu diesem Zeitpunkt weiterhin offen.

Die gemeinsame Pflichtauswahl umfasst neue/geänderte Tests und Proposal-Daten,
Basis, lesenden Restore-Kern, Change-Pläne, Fold, Metadaten, Lifecycle und
Identitäts-/Schema-Regressionen. Jede Stage erhält ihre eigene gefilterte
N=3-Auswahl plus ungefilterte Pflichtunion vor dem Commit. Neue Testnummern
werden ausschließlich angehängt. Dev führt keine Verhaltenstests aus;
Collection, Syntax- und native Paketvalidierung sind keine Apply-Erfolge.
Nach der atomaren Übergabe endet dieser Entwicklungsauftrag.
