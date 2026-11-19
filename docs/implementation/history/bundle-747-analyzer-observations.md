# Bundle 747 — Subjects und Beobachtungen

19. November 2026. Grundlage ist das native erfolgreiche Result mit SHA-256
`84e42cfedee24fc98528cbe296f95d25a62f2d760667f8cf8e519fa39256ad85` und sauberem HEAD
`3ba3b3a04b81a0d23837acc31b39451632781a51`. Es belegt alle sieben Stages von 746,
zuletzt 19.b.C mit 7.892 bestandenen Tests. 807/918 Positionen sind bestätigt;
es besteht kein offener Korrekturrest. Erfolgreiche Commits werden nicht wiederholt.

Die notwendige Detailentscheidung [ANALYZER-OBSERVATION-747](../decisions/analyzer-observation-747.md)
geht den vollständigen Gruppen 19.c.W/R/C und 19.d.W/R/C voraus. Jede Stage
installiert ausschließlich ihre eigenen Bytes, durchläuft N=3 plus die
ungefilterte Pflichtauswahl und erhält erst nach Erfolg ihren eigenen Commit.

Dieser vorbereitete Zielstand **19.d.W** hat nach seinem eigenen erfolgreichen
Gate **811/918** Positionen; nächste Position **19.d.R**. In Dev
wurden keine Verhaltenstests, Fixtures oder Testprozesse ausgeführt. Syntax,
statische Prüfung, reine Collection und native Paketvalidierung sind keine
Verhaltensabnahme. Keine automatischen Dienst-, CI- oder Workerstarts.

19.c.W liest alle gewählten vollständigen Werte mit nativer Scope-/Snapshot-
Bindung und ausschließlich explizitem Kontext. R übernimmt Aufruferdaten
vor dem Lesen und vereinheitlicht native Modell-, Quellenwechsel-, Sicherheits-
und Umgebungsfehler; Abnahmen umfassen Unicode, Pointer, Konfiguration,
verifizierte Partialgrenzen und tatsächliche Quellenänderungen. C isoliert den
nativen Quelladapter; verschobene Definitionen und sämtliche W/R-Tests bleiben gleich.

19.d.W bindet die genaue Subjectpartition, Findings und ursprüngliche
Request-/Analyzer-/Engineprovenienz; Betriebsdaten bleiben aus der Fachprojektion.
R ergänzt unabhängige erwartete Provenienz-/Transportbindung und die adversarialen
Abnahmen zu widersprüchlichen Mengen, fremden Bindungen und passiven Namespaces.
C trennt Beobachtung, Provenienz und Betriebssicht ohne Fachänderung; die
verschobenen Definitionen und sämtliche W/R-Testbytes bleiben unverändert.

Die Tests nutzen kleine echte Eingaben und unabhängige Hash-/Mengenerwartungen.
Ein Vollständigkeitsfall überschreitet die Query-Seitengröße, ein vollständiger
nativer Partialfall erhält die Integrationsgrenze. Es wird kein echter Detector
oder Engineinventar erfunden. Reportpackage, CLI, Work und Sprachworker bleiben
den folgenden Planpositionen vorbehalten. Vollsuite und separate unterstützte
Python-/Plattformmatrix bleiben Voraussetzung der Meilenstein-/Releasefreigabe.
