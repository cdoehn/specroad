# Begrenztes Payloadhashing

Der explizite Adapter `specroad.runtime.controlled.fingerprint_file` verwendet
den bestehenden Projekt-/Dateiguard und ein aktives Verbrauchsfenster. Er
reserviert einmal höchstens 65.536 Payloadbytes und liest mit `FileIO.readinto`
in Views desselben Puffers. Kurze Reads zählen nur ihre tatsächlichen Bytes;
SHA-256 und Ergebnisgröße bleiben unabhängig von der gewählten Puffergröße.
Nach jeweils 64 KiB liegt weiterhin ein Kontrollpunkt vor dem nächsten Read.

Ein `block_size` von 1 bis 1.048.576 ist wie bisher zulässig; der kontrollierte
Adapter reserviert und liest dennoch höchstens 64 KiB. Bei einem `MemoryError`
der Reservierung wird die Kapazität vor dem ersten Payloadread halbiert, bis
eine Allokation gelingt oder auch ein einzelnes Byte scheitert. Der Versuch
endet dann mit dem tatsächlichen Fehler. Ein Fehler nach einem Read wird nicht
automatisch wiederholt, weil die Eingabe bereits vorgerückt sein kann.

Die Reservierung ist ein tatsächlicher kleiner Allokationsversuch, keine
Schätzung nach Dateigröße und keine Zusage späterer Hostverfügbarkeit. Die
reservierten Payloadbytes werden als eigene aktive Registrierung verbucht;
Python-Objektkosten, RSS, Betriebssystempuffer und Hostquota folgen daraus nicht.
Beim Abschluss oder Fehler wird diese aktive Registrierung aufgehoben.

Der vorhandene Guard öffnet, prüft und schließt den Deskriptor. `FileIO` übernimmt
ihn mit `closefd=False`; keine zweite Pfadöffnung ersetzt die ursprüngliche
Bindung. Der Reader darf seine temporäre View weder behalten noch nach der
Rückgabe ändern. [Python FileIO](https://docs.python.org/3.14/library/io.html#io.FileIO)
beschreibt den Deskriptorvertrag und
[Python memoryview](https://docs.python.org/3.14/builtins/stdtypes.html#memoryview)
den kopierfreien Zugriff auf vorhandene Puffer.

Die W-Abnahme umfasst eigene 32-MiB-Dateien mit 64-KiB- und 4-KiB-Puffern,
vollständige unabhängig berechnete Hashes und das gemessene Python-
Allokationsfenster des Aufrufs. Diese Messung ist kein gesamter RSS-Benchmark.
Simulierte Allokationsfehler sind als Injektionen gekennzeichnet.

Konkrete Blockerberichte für reale Host-/Rechtefehler und nicht teilbare
Mindestoperationen folgen im R-Schritt. Der Adapter ersetzt noch nicht alle
Archiv-, Import- und Snapshotpfade. Bekannte Hostgrenzen, Stagingkapazität,
Kontrollreserven und persistente Fortsetzung benötigen ihre weiteren Bindungen;
0583 und 0584 bleiben Teilnachweise.
