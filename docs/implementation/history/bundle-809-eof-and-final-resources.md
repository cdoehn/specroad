# Bundle 809 — EOF-Korrektur und finale Ressourcenpflicht

24. November 2026. Quelle ist das native Fehler-Result
`7bfd2cdad0160861b8b88cd2be5a57b72999ed36c1a4fee259053b13d149d0f8`.
In Bundle 808 bestanden sämtliche **27.104 ausgewählten Tests**. Erst der
anschließende Git-Check vor dem Commit lehnte neue Leerzeilen am Dateiende in
`force_outcome.py`, `force_report.py` und `force_target.py` ab. Kein Timeout,
kein Testfehler, kein neuer Commit. 21.d.W/R bleiben erfolgreich, ausschließlich
21.d.C mit originaler implementation-Rolle und Commitnachricht bleibt offen.

Die Reparatur entfernt die überzähligen abschließenden Leerzeilen in genau
diesen drei Dateien. Statisch
bleiben die Python-ASTs identisch; weder Fachverhalten noch W/R-Tests ändern sich.
Die vorherige Paketprüfung hatte nur die Korrektur gegen den schmutzigen
Result-Snapshot verglichen und damit die schon enthaltenen C-Leerzeilen
übersehen. Jetzt wird zusätzlich der gesamte künftige Commit gegen den letzten
committeten Snapshot einschließlich neuer Dateien auf Whitespacefehler geprüft.

Rohbyteänderungen erzeugen trotzdem einen anderen Corebuild. Daher wird zugleich
die bereits ausdrücklich beauftragte [Aufschiebung neuer Ressourcenmessungen](../decisions/resource-final-809.md)
nach Spezifikation 2.5.9 umgesetzt. Keine weitere Messung läuft in Dev. Die
vollständig abgeschlossenen 807-Messungen und alle alten Originale bleiben
bytegleich; sie gelten ausschließlich für die damaligen Builds. Der neue
Zwischenstand erhält den offenen Status deferred, keinen Messpass. Ein nativer
Check vor dem Verhaltenstestgate verlangt spätestens bei 20.n die echten
bestandenen Daten genau des finalen Builds, auch ohne Policy-Marker. Finaler
Planfortschritt und ein expliziter Finalcheck verlangen dieselbe aktuelle Bindung.
Ungültige Belege können durch Deferral nicht zum Erfolg werden. Separate §14-
Budgets, menschliche Reviews und Releaseentscheidungen bleiben offen.

Neue kleine Regressionen decken offene Zwischenbelege, endgültige Stages und
Planstände, explizite finale Prüfung, erhaltene historische Bytes, falsche/
fehlende Bindungen und fehlerhafte Policys ab. Eine echte kleine native CLI-
Integration belegt, dass das Finale ohne Messbeleg noch vor dem Verhaltenstest-
Runner stoppt. Alle vorhandenen Pflichtfälle, Original-ID-Nummern und W/R-
Oracles bleiben erhalten. Keine Skips, keine neue Klärungsstage, keine Dienste.

Der vorbereitete Zähler 900/996 und der folgende Schritt 21.e.W gelten erst
nach erfolgreichem eigenen Apply-Gate und Commit. Die 27.104 alten Erfolge
sind kein Testnachweis für die geänderten Bytes. Dev führt keine Testkörper,
Fixtures oder Test-Unterprozesse aus. Statische Kontrolle, reine Collection
und native Bundlevalidierung sind nur Vorbereitung. Das automatische Apply-
Gate ist ausdrücklich beauftragt; Control bleibt pausiert. Nach Übergabe
endet der Dev-Turn ohne eigene Apply-/Resultschleife.
