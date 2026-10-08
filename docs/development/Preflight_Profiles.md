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

W bindet die bestehende Root-/Optionsauswahl und den schreibfreien
Transaktionscheck zusammen. Die gemeinsame Metadatenbilanz, große
Konfigurationen und die vollständige Begrenzung historischer Namensräume
gehören zu 6.a.R. Fortsetzbare Detailphasen, Ressourcenbudgets, reale
Write-/Recovery-/Root-Creation-Voraussetzungen und die weiteren öffentlichen
Projektbefehle bleiben ihren Implementierungspositionen zugeordnet.
`SR-REQ-0553` und `SR-REQ-0555` bleiben daher partiell; dieser Stand ist keine
Freigabe aller Profile oder der Runtime-/Plattformmatrix.
