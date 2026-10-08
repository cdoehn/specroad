# Aufrufbezogene Preflightprofile – 6.a.W

Die bestehende Command Registry bestimmt das Profil des aktuellen Aufrufs.
`project_read` prüft vor dem Handler die ausgewählte Konfiguration gegen das
eingebaute Schema und beobachtet den aktiven Transaktionsbereich. Der Dry-Run
eines `project_write` benutzt dieselbe schreibfreie Prüfung. Beide Profile
verlangen eine aktuelle Projektauswahl in ihrem Command Contract.

Die Prüfung verwendet die Konfigurationsbytes, aus denen anschließend die
Optionswerte entstehen. Nach zwei übereinstimmenden Beobachtungen des
Betriebszustands müssen diese Bytes und die Rootbindung noch stimmen. Eine
geänderte Konfiguration oder unterschiedliche Betriebsbeobachtung ergibt
Code 6. Offene Transaktionen oder ungeklärte Writerzustände sperren den
Handler mit Code 5 und erhalten sämtliche Dateien. Schemafehler liefern
Code 3, unzulässige Pfade Code 7, tatsächliche I/O-Fehler Code 5.
Maschinenlesbare Fehlerdetails unter `summary.preflight` nennen den
Prüfbereich; sie behaupten weder Modellgültigkeit noch Schreibautorität.

CLI-Schreibweise, Alias und strukturierter Request durchlaufen diese
Vorbereitung. Ein gespeichertes Invocation-Objekt ersetzt beim nächsten
öffentlichen Aufruf weder die Rootauswahl noch den aktuellen Preflight.
Der eigentliche Handler bleibt für seine Fachprüfung und alle tatsächlich
benötigten Eingabe-/Ausgabepfade verantwortlich. Vor Veröffentlichung gelten
weiterhin die gebundenen Writer-/Lockprüfungen.

Bootstrap öffnet kein Projekt. Das vorhandene `project_metadata` kann
benötigte Konfiguration weiterhin ohne Modell- oder Journalprüfung lesen,
auch wenn ein normaler Modellaufruf gesperrt wäre. Der Startcheck öffnet
keine Artefakte, Anhänge, Gitdaten, Journalbodies, Cacheinhalte oder historische
Receipts. Die Verhaltensnachweise erfassen dafür echte Dateizugriffe und
verhindern Schreib-, Prozess- und Netzwerkversuche.

Der Volltest machte zusätzlich einen bisher reihenfolgeabhängigen Kaltstart
der kanonischen Schlüsselsortierung sichtbar: Ein erster UTF-16-Aufruf konnte
noch einen Standardcodec importieren. Die Sortierung ruft nun denselben
eingebauten Encoder direkt auf. Fachwerte und Byteordnung bleiben erhalten;
der Authoring-Nachweis ohne externe Zugriffe läuft zusätzlich in einem
frischen isolierten Prozess.

R bilanziert die tatsächlichen Konfigurationsbytes einschließlich der
Wiederprüfung und die UTF-8-Namen der flachen Betriebsbeobachtung gemeinsam.
Jede Phase enthält höchstens 1 MiB. Konfigurationsdateien werden durch die
bestehende sichere Deskriptorgrenze in Blöcken von höchstens 64 KiB gelesen;
kurze positive Reads setzen am erreichten Offset fort. Eine volle Phase führt
zum nächsten Bereich, nicht erneut zum Anfang derselben Lesepassage.
Notwendige unabhängige Wiederprüfungen besitzen eine eigene Leseidentität.
Dateigröße, Identität, Zeitstempel und Root werden danach erneut geprüft.

Der maschinenlesbare Preflight weist Gesamtbytes, Phasen und deren erste und
nächste Cursor aus. Bei zusätzlichen Phasen enthält er
`preflight_detail_required=true`; der Command-Envelope ergänzt SRV167/info.
Auch Metadaten-Diagnosen lesen ihre Konfiguration begrenzt. Die automatische
Recovery-Auswahl benutzt dieselbe Bilanz für Konfiguration und den benötigten
Pending-Deskriptor. Eine große gültige Policy wird nicht allein wegen ihrer
Größe mit Code 5 zurückgewiesen: Autorisierung, tatsächlicher Eigentümer und
Recoverybedarf bestimmen weiterhin das Ergebnis. Vollständige Recovery-Proofs
und deren verpflichtende Wiederprüfungen gehören zur anschließenden explizit
autorisierten Recovery-Phase.

Die aktive Enumeration stoppt vor dem nächsten Iteratorzugriff, sobald 16
aktive oder unklare Einträge eingeordnet sind. Dann ist die Inventarliste
konservativ unvollständig; bereits erkannter Recoverybedarf blockiert reguläre
Zugriffe. Die zweite Beobachtung prüft denselben begrenzten Bereich erneut.
Abgeschlossene Receipt-, Request-, Cache- und Auditverzeichnisse werden nicht
geöffnet oder aufgezählt. Der Verhaltensnachweis vergleicht die nativen Zugriffe
vor und nach Ergänzung von 5.000 historischen Dateien; der Prüfumfang bleibt
identisch. Weitere Nachweise decken exakte Bytegrenzen, kurze Reads, Änderungen
während des Lesens und die Erhaltung wirklicher Fehlerklassen ab.

Diese Detailfortsetzung bleibt innerhalb desselben Aufrufs. Sie erzeugt keinen
dauerhaften Work-Cursor und keinen Code 8. Das vollständige Konfigurations-JSON
wird weiterhin im Speicher interpretiert; die Phasengröße ist keine Zusage über
den gesamten Speicherbedarf. Persistente Work-Manifeste/Checkpoints nach Anhang P
und ihre Wiederaufnahme gehören zu 6.i–6.l. Ressourcenbudgets, reale
Write-/Recovery-/Root-Creation-Voraussetzungen und die weiteren öffentlichen
Projektbefehle bleiben ihren Implementierungspositionen zugeordnet.
`SR-REQ-0553`, `SR-REQ-0555` und `SR-REQ-0570` bleiben daher partiell; dieser Stand ist keine
Freigabe aller Profile oder der Runtime-/Plattformmatrix.
