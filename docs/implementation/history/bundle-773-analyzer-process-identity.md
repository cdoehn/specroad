# Bundle 773 — Prozessidentität der Ressourcenbelege korrigieren

Das native Result von Bundle 772 meldet `incomplete_process_set` in
`test_measured_full_adapter_stays_within_total_cpu_and_memory_limits`:
8160 Tests bestanden, ein Test fehlgeschlagen, kein Commit. Der erhaltene
Arbeitsbaum ist exakt der angekündigte W-Zustand. Maßgebliches Fehler-Result:
`d897225e45b77e656251e0e4628fb868133a6dc3650c62113c865203048927f3`.

Die Schlussinventare von run-3/run-4 etikettieren den Parent als `worker`.
Der archivierte v1-Beobachter übernimmt ein solches letztes Cmdline-Label
auch ohne RSS-Probe. Die getrennten Parent-/Workerbelege, PID/Startticks,
Abstammung und alle tatsächlichen RSS-Proben erlauben die eindeutige
Zuordnung. Die Auswertung prüft diese Belege zusammen; sie verändert keine
Rohdaten, Originalskripte, Ressourcenwerte oder Grenzwerte.

Der vollständige offene Präfix bleibt `19.v.W`, `19.v.R`, `19.v.C`, jeweils
Rolle `implementation` und eigene ursprüngliche Planmessage. `correction_of`
bindet genau den alten Plan und diesen Rest. Keine neue Detailklärung,
keine erfolgreiche Stage wiederholen und keinen Endstand vorab installieren.
W stellt die belegte Prozessauswertung her; R ergänzt Gegenbeispiele für
unvollständige/fremde Identitäten, Wrapper und Proben; C trennt weiterhin nur
die unveränderten Byte-/Hashleser. Tests und Messdaten bleiben zwischen R/C
bytegleich, die Funktions-ASTs gleich.

Jede Stage braucht ihr eigenes Apply-Gate aus gefilterter fälliger N=3-Gruppe
plus vollständiger begründeter Pflichtauswahl. Dev führt keine Verhaltenstests
aus. Die Planwerte 862/863/864 gelten erst nach Gate und Commit; bestätigte
Ausgangsbasis bleibt 861/918 aus Bundle 771. Danach folgt 19.w.W. 19.t und die
menschlichen Korpusreviews bleiben bis vor 19.y offen. Diese Korrektur ist
keine neue Performancebeobachtung und keine Releasefreigabe.
