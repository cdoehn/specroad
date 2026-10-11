# Relationsstatus und Profilbewertung

`specroad.authoring.relation_status.relation_status_report` liefert eine
schreibfreie, maschinenlesbare Projektion eines übergebenen `TargetModel`.
Das Modell wird vor der Auswertung aus seinen gebundenen Originalbytes erneut
aufgebaut. Der Bericht ist keine Beschaffung oder Authentifizierung einer
vollständigen Projekthistorie und noch kein registrierter CLI-Befehl.

## Profilvertrag

Das optionale Feld `relation_review_policy` eines `profile-v1`-Dokuments enthält
geschlossene Einträge mit `relation_types`, `maturities`, `status` und `severity`:

```json
{
  "relation_types": ["addresses", "verified_by"],
  "maturities": ["draft"],
  "status": "unreviewed",
  "severity": "info"
}
```

Mindestens ein bekannter Relationstyp ist erforderlich. Eine leere Reifegradliste
bezeichnet alle bekannten Reifegrade. Maßgeblich ist der Reifegrad des speichernden
Quellartefakts. Zulässig sind ausschließlich `unreviewed` und `suspect` sowie
`info`, `warning` und `error`. Überschneidende Zellen innerhalb eines einzelnen
Profils sind Fehler, auch wenn die Werte gleich wären.

Die geordnete Profilkette bestimmt den Vorrang: Spätere Profile überschreiben
frühere Bewertungen. Ein später global gesetztes `SRV025` beziehungsweise
`SRV026` gilt auch für früher spezifisch belegte Zellen. Innerhalb desselben
Profils ist eine spezifische Zelle vorrangig vor dem globalen Override.
Ohne passende Zelle gilt der effektive globale Override, sonst `warning`.
`invalid` bleibt immer `error`; `current` erzeugt keine Statusdiagnose.

Die aufgelösten Zellen und Originalressourcen sind im effektiven Profilhash
gebunden. Ohne solche Einträge entsteht kein zusätzliches Mergefeld; bestehende
Profile und ihre bisherigen Hashprojektionen bleiben erhalten.

## Berichtsvertrag

`relation-status-v1` enthält nach Quell-ID und Relations-ID geordnete Zeilen,
den effektiven Profilbezug, typisierte Diagnosen und deren Fehlerentscheidung.
Der optionale Artefaktfilter erfasst ein- und ausgehende Relationen. Ein unbekanntes
Artefakt ist ein Fehler; vorhandene Artefakte ohne Relation ergeben eine leere
Auswahl. Das gesamte übergebene Inventar wird vor der Filterung geprüft.

Jede Zeile enthält die bestehenden Statusfelder, Relationstyp, Quellreifegrad,
Severity, aktuelle Endpunktrevisionen und Artefakt-/Kontexthashes. `selected_review`
bezeichnet das nach Anhang J maßgebliche aktuelle Review. `latest_review` enthält
das zeitlich neueste historische Review; bei Gleichstand entscheidet dieselbe
lexikografische Review-ID-Regel. Ein neueres unpassendes Review verdrängt kein
passendes Review. Fehlende optionale Angaben alter passiver Records bleiben `null`.

`changes_since_latest_review` nennt abweichende Relations- oder Kontexthashes.
Audit- und reine Revisionsänderungen bleiben sichtbar, machen ein Review aber
nicht selbständig `suspect`. Ein fehlender Zielendpunkt wird als `null` ausgewiesen.

`required_repair` unterscheidet erstmaliges menschliches Review, erneute Prüfung
des geänderten Kontexts, Auflösung einer Ablehnung mit neuem menschlichen Review
und strukturelle Reparatur vor einem Review. `current` erfordert keine
Relationsreparatur. Diese Daten führen keine Reparatur, keinen Write und keine
Wiederfreigabe aus. `strict` und `fail_on` ändern ausschließlich die
Fehlerentscheidung, nicht die aus dem Profil bestimmte Severity.

Die vollständige CLI-/Envelope-Integration und authentische aktuelle
Projekt-/Historienbeschaffung bleiben gesondert nachzuweisen. Die W-Abnahme
belegt den hier beschriebenen gebundenen API-Ausschnitt; eine Produktfreigabe
oder vollständige Erfüllung von SR-REQ-0281/SR-REQ-0282 wird nicht behauptet.
