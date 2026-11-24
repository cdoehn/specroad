# Bundle 811 — Messaufschiebung als eigener Commit

24. November 2026. Quelle ist der saubere native Abschluss 810:
`efde049bd468cef14fe4ba6b7a9b11ee036905d37193205758b96c5920aa308f`.
21.d.C ist als `d7ede332a34085c04c86bfe723104a9e30f414bf` abgeschlossen.
Dieser OFF-PLAN-Commit übernimmt ausschließlich die zuvor separat gesicherten
Messpolicy-, Runner-, Test- und Dokumentänderungen aus 809. Der C-Produktstand
und seine Tests werden nicht erneut geändert. Die 809-Vorbereitung scheiterte
vor Beginn der Testkörper; sie ist kein erfolgreicher Verhaltensnachweis.

Spezifikation 2.5.9 setzt den ausdrücklichen Nutzerauftrag um: neue CPU-/RSS-
Referenzmessungen bis zum tatsächlichen Entwicklungsabschluss aufschieben.
Der native Build behält seine eigene Identität. Fehlende Zwischenbelege sind
`deferred` mit offener finaler Verpflichtung; ungültige Belege bleiben Fehler.
Der Abschluss 20.n und finaler Planfortschritt verlangen wieder bestandene
Belege genau des finalen Builds, unabhängig von Rotation und Laufzeitfilter.
Andere Ressourcenbudgets und menschliche Reviews bleiben eigene Pflichtabnahmen.

Die 22 neuen vorbereiteten Verhaltensfälle prüfen insbesondere fehlende und
falsch gebundene Belege, beide finalen Aktivierungswege, vollständige Planbindung
und den tatsächlichen nativen Ressourcencheck vor dem Verhaltenstestlauf.
Statische Prüfung und reine Collection führen keine Testkörper aus.
Das eigene Apply-Gate entscheidet erst über den Commit. Historische Messbelege,
Testnummern und vorherige Commits bleiben erhalten. Keine neue Messung, kein
Control-Start, keine CI und kein Budgetreset werden durch die Übergabe ausgelöst.

Produktfortschritt bleibt 900/996; nächster Produktpunkt ist 21.e.W.
