# Bundle 761 — verzögerte Modellladung und Worker-Lebensdauer

19. November 2026. Das native Quell-Result mit SHA-256
`849c623ac7db577c3c94c969ef64db3daaf1a25d4cfcea2c95e9da9668b63cd9`
bestätigt 19.l.W/R/C mit **22069**, **22115** und **22120** bestandenen Tests.
Der saubere Abschlusscommit ist `1eb37f579499161f67860fcc14e6c62109f0d12f`.
Damit sind **837/918** Positionen bestätigt; es gibt keinen offenen Korrekturrest.

## Vollständige Folge 19.m.W/R/C

W besitzt das Modell ausschließlich innerhalb des expliziten Workeraufrufs.
Ein Besitzer lädt es verzögert höchstens einmal, merkt auch eine fehlgeschlagene
Initialisierung und gibt seinen Verweis beim Verlassen wieder frei. Ausschließlich
der exakte bekannte Descriptor kann diesen Pfad wählen. Externe Descriptors
bleiben Daten und behalten ihren eigenen vollständigen offenen Bericht.
Der Loader verwendet py3langid 0.4.0, prüft die Original-Modellbytes gegen den
bereits durch 19.k gebundenen Hash und dekodiert genau diese geprüften Bytes.
Er ruft weder die globale Upstream-Instanz noch dessen CLI auf.

R prüft das Modell vor dem Lesen als reguläre Datei und verweigert Links und
Spezialdateien. Der isolierte Worker startet in einer eigenen POSIX-Sitzung;
behandelte Signale werden während des Starts zunächst vorgemerkt, bis der
Popen-Prozess sicher übernommen ist. Danach führen sie in den gemeinsamen
Beenden-/Einsammeln-Pfad. Frühere Signalhandler werden garantiert
wiederhergestellt. NumPy erhält dieselben expliziten Ein-Thread-Werte wie der
vorhandene Offline-Paketprobeweg. Es entsteht kein Hintergrunddienst.
C lagert ausschließlich Modellleser und Signalverwaltung aus. Die Funktions-
und Klassen-ASTs sowie sämtliche R-Testbytes bleiben unverändert.

Jede der drei echten Stages besitzt ihr eigenes N=3-plus-Pflichtauswahl-Gate
vor dem Commit. Die Zielstände sind 838, 839 und 840 von 918; sie werden erst
durch das erfolgreiche jeweilige Apply bestätigt. Kein Endstand wird vorab
installiert. Alle IDs, Nachrichten, Voraussetzungen und Abnahmen bleiben erhalten.
Es liegt keine notwendige normative Detaillücke vor: Spec 0.2.99 und der
Entwicklungsvertrag bleiben bytegleich, ohne Klärungscommit oder Budgetänderung.

## Verhalten und Nachweisgrenzen

Neue Tests prüfen verzögerte/einmalige Modellladung, Wiederverwendung, Freigabe
bei normalem und behandeltem Fehlerende, unveränderte vollständige Reports für
Mehrfachauswahl sowie passive help/version/validate/show/list-Aufrufe ohne
optionale Imports. Ein echter Modellladetest benutzt die bereits gebundenen
Originalwheels im isolierten CPython-3.14-Zusatzpaket. Andere ABIs können dieses
Paket nur als inkompatibel zurückweisen; das ist keine positive ABI-Abnahme.
Die echten Prozessfälle synchronisieren mit dem eigenen Kind und prüfen
Normalende, Exitfehler, KeyboardInterrupt, SIGTERM auch während des Starts,
IPC-Fehler und SystemExit
auf erfolgtes Einsammeln. Modellhash-, Versions-, Link-, FIFO- und
Dateifehler gelangen nicht zur Deserialisierung. Offlinefallen bleiben auch
während der echten Modellinitialisierung aktiv; kein Netz-/CLI-/Trainingsmodus.

Reine Collection, Syntax, statische Analyse und passive native Paketvalidierung
in Dev sind keine bestandenen Verhaltenstests. Neue und betroffene Tests werden
ungefiltert verpflichtend im Apply ausgeführt; bestehende Testnummern bleiben.
Der unveränderte generische Bericht meldet bis zur tatsächlichen Integration in
19.n weiterhin offene Subjects und einen nicht verfügbaren Analyzer. Eine
Modellladung ist weder Rangliste noch Sprachentscheidung oder Releasefreigabe.

Die vorausschauend geprüfte Folge 19.n bleibt vollständig offen. Ihre
R-Abnahme verlangt echte Bibliotheksintegration je unterstützter Zusatzruntime.
Die vorliegende Basis enthält dafür nur Originalwheels für CPython 3.14;
3.10–3.13 bleiben, wie in Bundle 757 ausgewiesen, ohne reale Runtimebelege.
Diese Übergabe enthält deshalb die vollständige Gruppe 19.m, keinen verkürzten
19.n-Schritt und keinen vorgetäuschten Matrixerfolg. Nächste Position ist
19.n.W. Klassifikation, vollständige Entscheidungs-/Fortsetzungsintegration,
Korpusreview, Ressourcenmessungen und Release-Abnahmen bleiben in ihren
folgenden geplanten Gruppen offen. Harte Hostverluste werden nicht durch
Signaltests als wiederherstellbar behauptet.

Stageziel `19.m.W`: 838/918, erst nach eigenem Gate.
