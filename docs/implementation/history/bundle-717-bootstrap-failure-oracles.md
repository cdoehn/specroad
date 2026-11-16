# Bundle 717 — Init-Abbruchoracles und vollständiger Rest 18.v.R/C

## Belegter Ausgangspunkt

Result 716 mit SHA-256 `77353bfe4c82b9d48b44aadd89f3df6f21161c24f06dd3f60a6849d098d4c331`
bestätigt `18.v.W`, Commit `e0eebf6d4aa948ec6c59824416d07fc62df5c8fd`,
und damit 772/918. Sein natives Gate zählt 12.872 logische Tests;
die Pytest-Ausgabe zählt 12.873 bestandene Ausführungen einschließlich einer
spekulativen Kopie. Danach scheiterte `18.v.R` mit drei Fehlern und
13.051 bestandenen Tests. R ist installiert, aber nicht committed;
C wurde nicht ausgebracht.

Die Korrektur bindet die vollständigen erhaltenen Vorherbytes und den
Commitplan `f0a75345a929f9d43b1dcc506aedddc2b4d28f6a59097c402127c0c95e925705`.
Der exakte offene Rest `18.v.R`, `18.v.C` und beide Rollen `implementation`
bleiben erhalten. Der erfolgreiche W-Commit wird nicht wiederholt.
Keine neue Klärung und keine zusätzliche Planstufe werden angehängt.
Spezifikation 0.2.91, aktive Katalogbindungen und stabile Testnummern bleiben
unverändert; der bestehende Vertrag wird umgesetzt, nicht neu ausgelegt.

## Ursache und Korrektur

Die drei Varianten `staged`, `published`, `reused` von
`test_rollback_does_not_remove_foreign_bytes_added_during_failure` erwarteten
noch Konfliktcode 6. Der Test injiziert jedoch ausdrücklich einen echten
`OSError` während der Publikation. Spezifikation 11.8 ordnet I/O-Fehler Code 5
zu. Die bereits bestätigte C.2.2-Regel und SR-REQ-0003/0480 verlangen ab
Schutzbeginn, den tatsächlichen Teilbestand gesperrt zu erhalten, ohne
Rücknahme oder Vervollständigung. Der native Fehler ist daher korrekt.

Die Oracles prüfen jetzt Exit 5, den typisierten Grund
`bootstrap_publication_interrupted` und `mutation_possible=true`.
Sie weisen nach, dass die tatsächliche Fehlergrenze erreicht wurde,
die fremden Bytes und README erhalten sind, das vorbereitete Journal
bestehen bleibt und keine fertige `specroad.json` veröffentlicht wird.
Die Bootstrapbeobachtung muss den beschädigten, manuell wiederherzustellenden
Zustand melden. Wiederholtes Init und normale Validierung müssen Code 5
liefern, ohne Schreibversuch oder Änderung des vollständigen Bestands
unter dem Elternverzeichnis einschließlich Dateiidentitäten.
Die bisherigen Testkennungen bleiben aus Gründen der stabilen Abnahme erhalten.

## Getrennte Stufen und Abnahme

R enthält den vollständigen ursprünglichen R-Zustand einschließlich aller
Sicherheits-, Abbruch- und v2-Belegfälle sowie dieser Oraclekorrektur.
C führt die ursprüngliche strukturelle Bereinigung vollständig fort;
Tests, Tools und Verifikation bleiben gegenüber R bytegleich.
Alle drei real fehlgeschlagenen Fälle, ihre vollständige Testdatei,
alle weiteren geänderten Tests, transitive Verbraucher und die gesamte
bisherige Pflichtauswahl bleiben vor beiden Commits verpflichtend.
Jede Stage hat genau ihr eigenes Gate aus fälliger gefilterter N=3-Gruppe
plus ungefilterter Pflichtauswahl; erst danach Commit und nächster Zustand.

Dieser Snapshot ist `18.v.R`; sein prospektiver Zielwert ist
773/918, nächster Plancommit `18.v.C`.
Diese Zielwerte gelten erst nach dem eigenen erfolgreichen Apply-Gate und Commit.
In Dev erfolgen ausschließlich Syntaxprüfung, statische Prüfung, reine
Collection und native Paketvalidierung, keine Testkörper oder Fixtures.
Diese Vorbereitung ist kein Apply-, Vollsuite- oder Release-Erfolgsnachweis.
Lokale Betriebsdaten, Konfigurationen und Zugangsdaten gehören nicht zum Bundle.
