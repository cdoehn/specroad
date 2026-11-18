# Bundle 737 — Proposal-Work: Buildkonflikt und vollständiges Fehlerresultat

Das native Result mit SHA-256
`90858e5b477334ade328bc1ce9cc79341ef3ccff2b8d3bd191f1655b2614faca`
bestätigt `18.o.W` als Commit
`2008a0f0b97f32ea83a0fab1652d37ce3baa2986` mit 11.167 bestandenen Tests,
darunter 5.455 Pflichtfälle. Der bestätigte Produktfortschritt ist 790/918.
Das anschließende R-Gate meldet 2 fehlgeschlagene und 11.201 bestandene Tests;
R blieb uncommitted erhalten, C wurde nicht ausgebracht.

Beim Öffnen vorhandener Workdaten wurde der aktuelle Runtimebuild als
angebliche gespeicherte Buildbindung an den vollständigen Decoder übergeben.
Eine gültige Arbeit mit anderem Build scheiterte dadurch als ungültiges
Manifest mit Code 3 vor der eigentlichen Kompatibilitätsprüfung. Die Korrektur
prüft die gesamte erfasste Kette samt Referenzen, Objekten, Manifesten,
Generationen und Abschlussdaten zunächst gegen ihre gespeicherte Buildbindung.
Erst nach dieser vollständigen Datenprüfung vergleicht sie den gespeicherten
Build mit der aktuellen Runtime und weist den Konflikt mit Code 6 und
`incompatible_runtime_build` ab. Keine Umbindung oder Fortsetzung mit fremdem
Build; ungültige Daten werden nicht pauschal als Kompatibilitätskonflikt
umgedeutet. Die bestehende native Root-/Sperr-/Identitätsprüfung bleibt erhalten.

Der zweite Fehler lag im Oracle: unveränderliche interne Ergebnisdaten enthalten
Tupel, während der native JSON-Bericht Listen enthält. Der Test vergleicht nun
die vollständige öffentliche `as_dict()`-Projektion exakt mit dem gespeicherten
Bericht. Code 3, abgeschlossener Workzustand, fehlgeschlagene Gesamtvalidierung,
nichtleere Diagnostik und unveränderte Projektbytes bleiben Pflicht.
Der vorhandene Buildkonfliktfall prüft zusätzlich öffentliche Status- und
Resumeaufrufe sowie unveränderte Workbytes nach jeder Ablehnung.

Der vollständige offene Rest bleibt `18.o.R`, `18.o.C`, beide mit Rolle
`implementation` und unveränderten Commitnachrichten. Erfolgreiches W und
frühere Klärung werden nicht wiederholt. Alle Vorherbytes einschließlich des
erhaltenen R-Arbeitsstands sind an dieses Result gebunden. Die Korrektur gilt
in beiden Zielständen; C übernimmt die R-Testbytes exakt und behält seine
rein strukturelle Extraktion. Keine neue Spezifikationsentscheidung oder
Budgetänderung. Sämtliche bisherigen Pflichtdateien und die vollständige
betroffene Proposal-/Work-/Transport-/Migrations-/Mergeabnahme bleiben Pflicht.

Dev führt ausschließlich Syntax-, statische, reine Collection- und native
Paket-/Fortsetzungsprüfungen aus. Kein Testkörper oder Fixture läuft in Dev.
Jede Stage benötigt ihr eigenes Apply-Gate vor dem Commit. Die nachfolgende
Gruppe 18.p bleibt vollständig offen: Ihr öffentlicher Änderungsdialog samt
Überarbeitung und erneuter echter Freigabe wird nicht durch eine verkürzte
Zusatzstage vorweggenommen.

Ziel erst nach dem eigenen erfolgreichen Gate dieser Stage: **18.o.R**, **791/918**, danach **18.o.C**.
