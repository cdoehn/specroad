# Gemeinsame Regeln des Implementierungsplans

Diese zentralen Regeln gelten für alle verlinkten Meilensteine. Die aktuellen Nutzeranweisungen und lokalen Betriebsregeln sowie die neueren Regeln in Spezifikation 2.5 haben bei älteren Workflowangaben Vorrang. Insbesondere: Dev führt keine Verhaltenstests aus; Apply führt vor jedem Commit die gefilterte fällige N=3-Gruppe plus Pflichtauswahl aus. Historische Volltest-/Dev-Testangaben ändern das nicht.

[Projektentwicklung](../../DEVELOPMENT.md) · [Planpflege](../implementation/AGENTS.md) · [Apply-Verfahren](Apply_Commit_Plans.md) · [Aktueller Testbetrieb](Testing.md)

## W/R/C und die Grenze jedes Commits

**W – Let it Work:** den konkret beschriebenen kleinsten nutzbaren, bereits sicheren Ausschnitt implementieren und sein Verhalten prüfen. W ist nicht absichtlich rot und darf keine scheinbar erfolgreiche Sicherheits-/Freigabeattrappe enthalten. Noch nicht unterstützte Teilfälle werden ausdrücklich zurückgewiesen. Grundlegende Sicherheits- und Datenintegritätsgrenzen werden nicht bis R verschoben.

**R – Make it Right:** denselben Ausschnitt vervollständigen; die jeweils genannten Fehlerfälle, Randbedingungen, vollständigen Mengen und Invarianten umsetzen. Kein fachlich nötiger Teil wird als bloß spätere Bereinigung aufgeschoben. W und R sind getrennte, jeweils grüne und nachvollziehbare Entwicklungsstände.

**C – Make it Clean:** die konkret genannte Struktur verbessern, ohne fachliche Verträge, Daten, Nebenwirkungen oder Testerwartungen zu verändern. Vorhandene Verhaltenstests laufen weiter; zusätzliche strukturelle Tests oder Tests auf interne Funktionsnamen sind kein Selbstzweck. Neue Anforderungen gehören nicht in C. Gibt es nach der tatsächlichen Umsetzung keinen sinnvollen Clean-Delta, wird der Plan nachvollziehbar angepasst statt einen leeren Alibi-Commit zu erfinden; nicht still einen geplanten Commit als erledigt markieren.

Für die ursprünglichen 885 Produktpositionen bleiben die Kennungen `Meilenstein.kleinbuchstabe.W|R|C`; ihre Schritte passen in a bis z, und exakte Commitnachrichten sowie absolute Positionen stehen direkt beim jeweiligen Produktcommit. Die zusätzlichen `AUDIT-*`-Kennungen und ihre Commitzuordnung sind oben geregelt. Größe und Zeilenanzahl müssen zwischen W, R und C nicht gleich sein. Die Reihenfolge lautet W, R, C, niemals alphabetisch C, R, W.

## TD-001 – Verhalten testen, nicht Ausgabe oder Dokumentation

Automatisierte Oracles sind fachliche Rückgabewerte, Exitcodes, Zustandsübergänge, tatsächliche Dateiwirkungen, unveränderte Originalbytes, Idempotenz, vollständige Ergebnis-/Pflichtmengen, Recovery, Ressourcenverbrauch und maschinenlesbare Verträge. Exaktheitsvektoren für JCS, Schemas, Hashdomänen, ZIP, CSV/NDJSON/ReqIF oder JSON-Reports sind erlaubt, soweit die Bytes selbst ein fachlicher Austausch-/Integritätsvertrag sind. Ein JSON-Resultat wird normalerweise geparst und fachlich geprüft, nicht wegen seiner Einrückung verglichen.

**Ausgeschlossen:** Tests auf Konsolenformulierungen, Farben, ANSI-Sequenzen, Symbole, Emojis, visuelle Reihenfolge, Tabellenlayout, Spinner, Ticker, Fortschrittsdarstellung, Pretty-/Helptext, HTML-/Markdown-Darstellung, Snapshot-/Golden-Files solcher Darstellung sowie Dokumentations-, Markdown-Lint-, Linkchecker- und Doctests. Auch ein Test, der nur die Vollständigkeit dieses Plans oder einer README behauptet, wird nicht in die Produktsuite aufgenommen. Hersteller-/Paketlizenz- und Payloadinventuren als tatsächliche Lieferdaten sind davon zu unterscheiden.

Fachliche Dokumentmodelle, vollständige ausgewählte Daten und sichere Verarbeitung von Text sind weiterhin testbar. Renderer implementieren die spezifizierten Formate, aber ihre erzeugte menschliche Darstellung wird nicht zum Testorakel. Sicherheitsprüfungen beobachten Rechte, tatsächliche unerlaubte Ausführung oder Dateizugriffe; sie werden nicht als kosmetische Output-Snapshots verkleidet. Ein manueller visueller Durchgang ist möglich und bleibt als solcher erkennbar.

**Explizite Spezifikationsabweichung:** SR-REQ-0215 wird nur für Verhalten und echte maschinenlesbare Golden-Vektoren umgesetzt. Der Output-Golden-Anteil von SR-REQ-0472 und die entsprechenden Darstellungsanteile unter anderem in SR-SCN-0012/SR-E2E-0012, SR-SCN-0019 und SR-SCN-0023 werden nach Nutzerentscheidung nicht automatisiert getestet. Dasselbe gilt für reine Dokumentationsnachweise. Die universellen Evidence-/Vollständigkeitsregeln SR-REQ-0491 bis SR-REQ-0494 und SR-REQ-0500 dürfen diese Ausnahme nicht über grüne Dummytests wieder einführen. Der Katalog hält solche Anteile explizit als `not_automated_by_user_policy: TD-001` fest, nicht als passed. Gemischte Requirements behalten ihre tatsächlich testbaren Verhaltensanteile. Der finale Bericht darf deshalb keine unveränderte, lückenlose Original-Spezifikationsabnahme ohne Erwähnung von TD-001 behaupten.

Die CLI wird dennoch von Anfang an **farbig, übersichtlich und ansprechend** umgesetzt: austauschbare Präsentationsschicht, deutlich erkennbare Phasen, fortlaufender Fortschritt, klare Warnungen und kompakter Abschluss. Es gibt keinen nachträglichen Riesenschritt, der sämtliche Bedienbarkeit erst am Ende erzeugt. Terminalbreite, TTY-/Plain-Modus, NO_COLOR und quiet werden bei der Implementierung berücksichtigt, aber ihre Darstellung nicht automatisiert festgeschrieben.

## BD-001 – flexible Anzahl eigenständiger Commits pro Bundle

Die Nutzerfreigabe mehrerer Commits und W/R/C-Folgen pro Bundle gilt fortlaufend und wird in der lokalen AGENTS.md gepflegt. Die gewählte Strecke muss zum Auftrag und den tatsächlichen Abhängigkeiten dieses Plans passen. Für die Audit-Nacharbeiten gilt die vorgeschaltete Reihenfolge oben; danach folgt die reguläre Produktfolge. Bundlegröße und Produktfortschritt werden getrennt geführt.

Nach Nutzerauftrag vom 28. Oktober 2026 gilt Spezifikation 2.5: Ausgangsziel ist der vollständige nächste offene W-, R- oder C-Schritt, einschließlich seines gesamten bisherigen Rests. Weitere zusammenhängende vollständige Schritte werden bei erfüllten Gates möglichst gemeinsam geliefert. Interne Aufgaben und grüne Zwischenprüfungen rechtfertigen keine eigenen Bundles oder zusätzlichen Teilcommits. Erst ein belegtes, nach Diagnose und Reparatur verbliebenes und durch geringeren Umfang lösbares Hindernis erlaubt zwei fachlich zusammenhängende, möglichst ausgewogene Teile. Nur die erneut scheiternde Hälfte wird weiter geteilt. Versuch, Fehler, Reparatur, Begründung, Teilumfänge und vollständiger Rest einschließlich Integration werden hier dokumentiert. Infrastrukturfehler und vermutete Komplexität allein rechtfertigen keine Teilung. Die gewählte erste/letzte Kennung, Anzahl und die exakten Einzelmessages werden vor Auslieferung genannt. Kein Squash und keine Umnummerierung nur wegen der Bündelgröße. Verschiedene Meilensteine dürfen nur bei erfüllten vorausgehenden Gates zusammen im selben Bundle liegen.

Nach ausdrücklichem Nutzerauftrag vom 30. Oktober 2026 ersetzt
RUNTIME-AUTO-521 allein die bisherige feste Laufzeitauswahl: laufende
Phasenmessung mit Historie, ausschließlich neueste Werte, dynamischer
Apply-Filter nach 2.5. W/R/C-Zustände und vollständige Arbeitspakete bleiben
unverändert. Diese Workflow-W/R-Folge ist keine Bearbeitung von 15.l.C.

**Technische Konsequenz für Format 1:** PatchHarbor kopiert normale Nutzdateien bereits vor dem Entrypoint in das Repository. Deshalb darf ein Mehr-Commit-Paket nicht einfach den gesamten letzten Produktstand als normale Payload vorinstallieren und danach mehrere leere oder gemischte Commits erzeugen. Commitweise Stände werden beispielsweise als inert eingebettete Patch-/Dateidaten im privat ausgeführten Entrypoint gehalten und dort einzeln materialisiert. Je Commit folgen Scopekontrolle, Verhaltenstests, Fortschrittsaktualisierung, gezieltes Staging und genau dessen Git-Commit. Alle eingebetteten Pfade bleiben genauso sicher und der zulässige Gesamtumfang wird vorher gebunden. Keine verdeckten Aufrufe von Projektcode, keine fremden Dateien und kein rekursiver PatchHarbor-Aufruf.

Bei Fehlern stoppt die Sequenz vor dem Commit des fehlerhaften Schritts. Zuvor in diesem Bundle tatsächlich grün abgeschlossene Commits bleiben erhalten; kein destruktives Rollback. Der Result-Zustand wird ausgewertet und ein gebundener FIX beziehungsweise Restauftrag erstellt. Die Aussage „bei Fehler kein Commit“ gilt für den gerade fehlgeschlagenen Commit, nicht als erfundene globale Transaktion über bereits bestätigte Commits. FIX-Commits verändern den Planzähler nicht. Auf einen noch nicht geprüften aktuellen Result-Zustand wird kein Folgepaket geraten.

**Die Planaktualisierung AUDIT-PLAN-UPDATE bleibt genau ein OFF-PLAN-Commit.** Sie verändert keine der 885 Produktpositionen und führt keine der neu geplanten Reparaturen aus.

## BN-001 – sichtbare fortlaufende Bundle-Nummer

Nutzerentscheidung vom 20. September 2026: Ab dem Bundle für `3.k.W` bis
`3.k.C` wird eine eigene laufende Bundle-Nummer geführt, beginnend mit `001`.
Sie zählt ausgelieferte nummerierte Pakete, nicht W/R/C-Commits. Der bisherige
Bestand wird nicht rückwirkend nummeriert. Bei erneuter Auslieferung derselben byteidentischen ZIP bleibt deren Nummer gleich.
Die höchste bereits ausgelieferte Nummer ist auch bei Fortsetzungsbundles zu berücksichtigen.

Der Abschlussblock der Chat-Antwort wiederholt den zutreffenden grünen, gelben oder roten Statusbalken. Bei einer Auslieferung stehen darunter `SPECRoad-PATCH-NR: NNN` und als allerletzte Zeile der tatsächliche Patch-Download-Link. SHA-256 und Backupstatus stehen davor. Bei STOP gibt es weder ein neues Paket noch einen erfundenen Download-Link. Diese Nutzerentscheidung vom 20. September 2026 ersetzt die ältere widersprechende Darstellungsregel der beigelegten statischen Chatvorlage, nicht deren Sicherheitsvertrag. Nur nach sämtlichen Gates,
allen vorgesehenen Commits und sauberem Endstand gibt der Entrypoint als seine
letzte Zeile `SPECRoad-PATCH-NR: NNN | APPLIED SUCCESSFULLY` aus. Bei einem
Abbruch darf diese Erfolgszeile nicht erscheinen. Der Fortschrittskopf hält die
letzte vollständig abgeschlossene nummerierte Bundle-Folge fest.

PatchHarbor selbst erzeugt **danach** seinen Result-Bericht und kann weitere
Terminalzeilen ausgeben. Die Kennung bestätigt den Entrypoint-Abschluss, nicht
einen erst danach möglicherweise scheiternden Result-Export. Run-Ergebnis,
Git-Stand und frisches Result bleiben die belastbaren Prüfquellen; die sichtbare
Nummer ersetzt keine SHA-256-, Repository- oder Replay-Bindung.

## Umsetzung, Pfade, Abhängigkeiten und Testgates

Die unten angegebenen Modulpfade sind konkrete vorgeschlagene Verantwortungsgrenzen, keine Pflicht zu einer Datei pro Schritt oder pro Requirement. Lokale, verhaltensneutrale Benennungs-/Zuschnittverbesserungen sind erlaubt und werden im betroffenen Planabschnitt mitgeführt. Eine neue Architektur oder fachliche Erweiterung ist keine unbemerkte Clean-Änderung. Ein Schritt umfasst jeweils Produktcode, passende Verhaltenstests und nötige Registry-/Schema-/Datenintegration; Testarbeit ist nicht auf M20 verschoben.

Die strikt lineare Commitposition ist der ausführbare Standard: jeder Commit setzt seinen unmittelbar vorhergehenden Plan-Commit und dessen tatsächlichen grünen Stand voraus. Die Meilensteingates beziehen sich nur auf die zu diesem Zeitpunkt aktivierten realen Fähigkeiten. Später geplante Adapter sind entweder nicht angeboten oder schlagen ausdrücklich als noch nicht unterstützt fehl, niemals als angeblich bestanden. Ein erster Test darf schon mit Standardbibliothek/kleinem temporären Projekt arbeiten; die gemeinsame Infrastruktur in M1 konsolidiert solche Tests, sie legitimiert kein vorheriges ungeprüftes Produktverhalten.

Wichtige Staffelung: Datenmodelle und Mehrsprachigkeit M2; Graph/Scopes und reine Diff-/Impactkerne M3; gemeinsame Validierung M4; alle normativen Writes über M5; Workunterbau M6 vor den großen Featureabläufen. Lokale/Git-Quellen M8, echte Baselinequelle M10, Bundlequelle M15. Release-Baselines sind in M10 ohne echtes Readiness-Gate blockiert und werden erst mit M12/M13 vollständig freigeschaltet. Dokument-/Viewanbieter für Verifikation und Roadmap wachsen in M12/M13 hinzu. Der sichere Archivkern entsteht für Work früh und wird in M14/M15 zu vollständigen Fachformaten ergänzt; XML-Sicherheit entsteht für Evidence in M12 und wird bei ReqIF wiederverwendet. Legacy-Originalreader werden in M16 wirklich implementiert. Der generische Analyzer und der **reale** erste Sprachadapter sind beide Pflichtumfang in M19.

Die je Schritt benannten Verhaltenstests konkretisieren dessen fachliche Abnahme; sie sind keine Auswahlregel für Apply. Für die Testausführung gilt die zentrale lokale AGENTS.md, für technische Aufrufe [Testing.md](Testing.md). Ein zielruntimeabhängiger Referenznachweis erfordert die passende Plattform; ein Pixel-/aarch64-Lauf ist kein x86-64-Nachweis. Nicht verfügbare Nachweise bleiben offen. Fachliche Runtime-/Budget-/Abbruchsverträge bleiben Teil der jeweiligen Produktabnahme.

Keine unbeauftragten Tags, Releases, Pushes, externen Genehmigungen oder neuen Produktanforderungen. Kein pauschales git add -A, reset --hard oder git clean. Beabsichtigte Pfade stagen, Fremdänderungen erhalten, Exitstatus und reale Dateieffekte prüfen. Entwicklungstests dürfen Testakteure simulieren; produktive menschliche Freigaben dürfen daraus nicht abgeleitet werden.
