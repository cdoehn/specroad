# Ressourcenbeobachter v2

`benchmark.py.gz` ersetzt ausschließlich den v1-Beobachter. `prepare.py.gz`,
`parent.py.gz` und `worker.py.gz` aus `../measured_v1/` bleiben bytegleich.
Die alten Skripte und Messbelege bleiben erhalten.

Ein eigener Prozess kann zwischen RSS-Baumaufnahme und Umfeldprüfung starten.
v2 prüft deshalb seine aktuelle Elternkette bis zur aufgezeichneten Identität
des Messwrappers. PID, Eltern-PID und Startzeit müssen bei erneuter Prüfung
übereinstimmen. Verschwundene, wiederverwendete, umgehängte oder unaufklärbare
Prozesse werden nicht aus der Fremdlastprüfung ausgenommen. Gleiche
Prozessnamen begründen keine Zugehörigkeit. Der Vorabcheck hat keinen Wrapper.

Workload, Warm-up, fünf Messläufe, CPU-/RSS-Erfassung, Grenzwerte und die native
Belegprüfung bleiben unverändert. Ein früher zurückgewiesener Lauf wird dadurch
nicht nachträglich gültig; neue Belege benötigen eine neue vollständige Messung.
