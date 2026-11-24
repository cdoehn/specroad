# RESOURCE-FINAL-809 — Ressourcenabnahme am endgültigen Build

24. November 2026. Dies setzt den ausdrücklichen Nutzerauftrag um, die noch
laufenden Messungen von Bundle 807 abzuschließen, danach neue Ressourcen-
messungen bis zum Entwicklungsabschluss aufzuschieben und erst dann nötigenfalls
zu optimieren. Keine delegierte neue Detailklärung und kein Budgetverbrauch.
Normativ ist Spezifikation 2.5.9; Grenzwerte und Verfahren bleiben §14/T.10.

Weiterhin jeden Zwischenbuild zu messen widerspräche dem Auftrag. Alte Belege
auf neue Hashes umzuschreiben wäre falsch. Daher hält eine kleine versionierte
Policy die finale Verpflichtung offen; der vorhandene reine Nachweisprüfer
bleibt unverändert. Ein fehlender Zwischenbeleg wird offen als aufgeschoben
geführt. Die finale Stage oder ein abgeschlossener Plan schaltet automatisch
auf strikte aktuelle Buildbindung um, unabhängig von N=3 oder Laufzeitfilter.
Ungültige vorgelegte Belege sind weiterhin Fehler; eine bestandene finale
Messung ist keine Produkt- oder menschliche Freigabe.

Die zunächst mit der C-Korrektur vorbereitete Umstellung wurde in 809 nicht
durch Verhaltenstests abgenommen und nicht committed. Nach dem gesondert
beauftragten manuellen Abschluss von 21.d.C wird sie in Bundle 811 als eigener
OFF-PLAN-Commit mit eigenem Apply-Gate umgesetzt. Der abgeschlossene C-Commit
wird weder wiederholt noch erweitert. Neue Core-Produktänderungen folgen erst
nach diesem ausdrücklich beauftragten Policy-Schritt. Keine Testwiederholung
des alten C-Gates und keine neue Zwischenbuild-Messung.

20.i/20.j behalten Werkzeuge, Fixtures und fachliche Prüfungen; ihre tatsächlichen
Ressourcenabnahmen bleiben bis 20.n offen. Dort sind alle zurückgestellten
§14-/T.10-Nachweise am aktuellen Endstand zu führen. Die Analyzer-Policy löst
keine übrige Ressourcenpflicht, keinen menschlichen Review und keine Release-
freigabe ein. Fehlende Belege erlauben keinen Abschluss. Nur endgültige Builds,
keine nachträgliche Vermessung aller verworfenen Zwischenbuilds.
