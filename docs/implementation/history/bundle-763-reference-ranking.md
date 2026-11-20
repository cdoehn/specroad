# Bundle 763 — reale gebundene Referenzranglisten

20. November 2026. Das native Quell-Result mit SHA-256
`06637979c2ad25b54f691bbb7618e18ff1dbbf2436762740bc710f2c6ffe492d`
bestätigt die vollständige Folge 19.m.W/R/C aus Bundle 762 mit **8870**,
**9005** und **9007** bestandenen Tests. Der saubere Abschlusscommit ist
`4ce9b11db5a946624c6e61b3879cf573187ba737`. Damit sind **840/918** Positionen
bestätigt; es gibt keinen offenen Korrekturrest. Die historischen Berichte
bleiben unverändert.

## Vollständiger Planschritt 19.n.W

Der explizite Aufruf `specroad.analyzers.reference.rank_request(request)`
verwendet eine eigene, verzögert geladene Originalinstanz von py3langid 0.4.0.
Der bestehende Loader prüft die mitgelieferten Modellbytes gegen SHA-256
`f4f4a2c3465ca1f081541037f9cac23021d68151c2f709c55ae5eedfca522963`.
Alle Subjects werden separat in stabiler Reihenfolge mit ihrem vollständigen
Originalstring an die reale Bibliothek übergeben. Weder Projektsprachen noch
Einstellungen begrenzen den Kandidatenraum; fremde Modelle und Filter werden
nicht angeboten. Keine globale Upstream-Instanz, CLI, URL oder Trainingsfunktion.

Das Originalmodell besitzt 142 Spalten und 140 unterschiedliche Ausgabelabels;
die beiden zusätzlichen Spalten sind die von der Bibliothek zusammengeführten
Aliasse für `sr` und `uz`. Der vollständige geordnete Kandidatenkatalog wird
aus der ursprünglichen Modellreihenfolge abgeleitet, mit Hash gebunden und
gegen die tatsächlich geladene Instanz geprüft. Das ist keine Sprachauswahl.
Die Bibliothek normalisiert ihre Scores. Der Adapter bewahrt sämtliche
140 Scores und sortiert deterministisch nach Score und bei Gleichstand Code.
Unvollständige, doppelte, fremde oder nicht endliche Ranglisten sind Fehler.

Das unveränderliche Ergebnis bindet Request-ID, Snapshot-Hash, Descriptor-Hash,
Subject-Schlüssel, Originalwerthash, Originalmodell, geordneten Kandidatenraum
und tatsächliche Bibliotheks-/Python-/Unicodeversionen. Es enthält keine
persistierte Kopie der Texte. Die Ergebnisse sind eigene interne Ranglisten,
noch keine serialisierten Detector-Observations, Evidence oder Sprachfreigabe.
Der generische Workerbericht bleibt bis zur folgenden Integration offen.
Die zwölfstellige Scoreprojektion und Sprachentscheidung gehören weiterhin
zu 19.p und 19.q; die Längen-/Abstentionsvorbereitung zu 19.o.

## Abnahme und Liefergrenze

Die vorbereiteten Unit-Tests prüfen vollständige unabhängige Texte, Unicode-
Originale, Request-/Subjectbindungen, unveränderliche Ergebnisse, Modellbesitz,
passive Imports und unzulässige Filter sowie fehlerhafte Backendranglisten.
Der echte Integrationstest verwendet die vorhandenen Originalwheels im
isolierten CPython-3.14-Zusatzpaket. Er analysiert vollständige deutsche,
englische, französische und japanische Texte, vergleicht alle Scores mit einem
unabhängigen realen Bibliotheksaufruf und prüft die Bindungen. Ein weiterer
Test vergleicht den geordneten Katalog mit sämtlichen ursprünglichen
Modellspalten. Diese synthetischen Beispiele sind kein menschlich begutachteter
Releasekorpus. Netzwerk-, Unterprozess-, Filter- und operative Upstream-Wege
bleiben während der echten Integration gesperrt; Modell und Ranking sind real.

Dev führt ausschließlich reine Collection, Syntax-/statische Prüfung und
passive native Bundlevalidierung aus. Keine Testkörper, Fixtures oder
Test-Unterprozesse wurden hier ausgeführt. Alle neuen Testdateien sowie
relevante Analyzer-, Modell-, Paket-, Core- und Sicherheitsregressionen sind
ungefiltert in der Pflichtauswahl. Apply prüft deren Vereinigung mit seiner
fälligen gefilterten N=3-Gruppe vor dem einzigen angekündigten Commit.
Der vorbereitete Zielstand **841/918** gilt erst nach diesem erfolgreichen
Gate und Commit; nächste Position ist **19.n.R**.

Die priorisierte Folge wurde bis 19.o und 19.p geprüft. 19.n.R verlangt einen
echten nicht gemockten Integrationslauf je unterstützter Zusatzruntime. In der
gebundenen Basis liegen dafür nur Originalwheels für CPython 3.14 unter Linux
x86_64 vor; auch die lokale Vorbereitung weist keine Interpreter oder passenden
Originalwheels für 3.10–3.13 nach. Der vorhandene Inkompatibilitätszweig ist
kein positiver Runtimebeleg. Deshalb enthält diese ZIP den vollständigen
nutzbaren W-Schritt, ohne eine unvollständige R-Abnahme als erledigt auszugeben.
19.n.R/C und alle davon abhängigen Folgeschritte bleiben offen. Die fehlende
Matrix benötigt echte Originalartefakte und ausführbare unterstützte Runtimes;
es werden keine ABI-, Klassifikations-, Korpusreview- oder Releaseerfolge erfunden.

Es liegt keine notwendige normative Spezifikationslücke vor. Spec 0.2.99,
SPECROAD-DECISION-1, Entwicklungsvertrag, vorhandene Abnahmen und ihre Grenzen
bleiben unverändert. Dies ist eine normale Implementation-Stage ohne
Klärungspräfix, Korrekturbindung oder Budgetänderung.
