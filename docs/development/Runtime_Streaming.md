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

## Betriebliche Blocker

`specroad.runtime.payload_hashing.fingerprint_file_outcome` verwendet denselben
Guard und Hashkernel. Es liefert `payload-hash-outcome-v1` mit `state=completed`,
`exit_code=0` und dem vollständigen Fingerprint oder `state=blocked`, `exit_code=5`
und `fingerprint=null`. Der bisherige Adapter `controlled.fingerprint_file`
behält seinen nativen Ausnahmevertrag. Das neue API ist eine ausdrückliche
Einbettungsschnittstelle und noch kein zusätzlicher CLI-Befehl.

Der Blocker nennt `blocked_reason`, `failed_stage`, den bekannten nativen Errno
und `required_action`. `transfer` nennt nur wirklich begonnene
`buffer_attempts_bytes` und die tatsächlich reservierten `reserved_buffer_bytes`.
Eine erfolgreich gewählte kleinere Alternative erzeugt keinen Blocker.
Eine erst nach erfolgreichem Hashing scheiternde Quellprüfung liefert ebenfalls
keinen Fingerprint. Sicherheitsfehler und unerwartete Programmierfehler werden
nicht in Ressourcenmangel umgedeutet.

Nur nach erfolglosem Versuch des einzelnen Pufferbytes ist
`minimum_failed_buffer_bytes=1`. Für nicht weiter teilbare Initialisierungs-,
Read- oder Guard-Schritte bleibt das erforderliche RAM-Minimum unbekannt.
Das Code-5-Ergebnis benennt die tatsächliche Verweigerung, nicht eine
automatische Auftragsgrößengrenze. Ein weiches Speicherziel allein verweigert
keinen noch ausführbaren kleinen Hash.

Nach einem abgebrochenen Read wird kein Teilhash zurückgegeben und kein
automatischer Retry vorgenommen. Die Quelle könnte schon vorgerückt sein.
Ein neuer Aufruf benötigt zuerst die Abhilfe und eine neue vollständige
Eingabeprüfung; `checkpoint=null` behauptet keine dauerhafte Fortsetzung.
Der Hashpfad schreibt weder Projektdateien noch Journale, Before Images oder
Checkpoints. Er entfernt keine vorhandenen Daten zur Speicherbeschaffung.
Native Fehlertexte und Dateinamen bleiben außerhalb des Blockerberichts.

Die R-Fälle prüfen neben markierten Injektionen reale Rechte- und
Dateideskriptorverweigerungen in eigenen isolierten Prozessen. Ein injizierter
unteilbarer Initialisierer provoziert dort außerdem eine reale abgewiesene
Allokation unter der Prozessgrenze. Diese Fixture ist kein Nachweis des
tatsächlichen Speicherbedarfs von SHA-256. Der Produktcode verändert keine
Betriebssystemlimits. Die Quellverträge sind
[Python MemoryError](https://docs.python.org/3.14/builtins/exceptions.html#MemoryError),
[Python resource](https://docs.python.org/3.14/library/resource.html#resource.setrlimit)
und [Linux getrlimit](https://man7.org/linux/man-pages/man2/getrlimit.2.html).

Ein Blockerbericht setzt voraus, dass der Host den weiteren Interpreterlauf
zulässt. Ein nicht abfangbarer Prozessabbruch ist kein berichteter Pythonfehler.
Der Adapter ersetzt noch nicht alle Archiv-, Import- und Snapshotpfade.
Bekannte Hostgrenzen, Stagingkapazität, Kontrollreserven und persistente
Fortsetzung benötigen ihre weiteren Bindungen; 0583 und 0584 bleiben Teilnachweise.
