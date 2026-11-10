# Testoptimierungen und dauerhaftes Profiling

Ausdrücklicher Nutzerauftrag vom 10. November 2026, OFF-PLAN in Dev2/Apply2.
Die zehn untersuchten langsamen M17-Tests, ihre vorhandene Abdeckung und das
wiederverwendbare Profilingwerkzeug bilden eine gemeinsame Übergabe. Die
Produktpositionen, M18 und die bestehenden Betriebsfreigaben bleiben erhalten.
Diese Beschreibung ist ein Abnahmeplan und kein Benchmark- oder Apply-Erfolg.

## Geordnete Commitfolge

1. `TEST-PERFORMANCE.W` — `perf(tests): reuse bound registry and checkpoint inputs`
   Alle vorbereiteten Optimierungen gemeinsam: vier exakte Registereingaben
   bis je ein MiB im prozesslokalen LRU, frische öffentliche Records, einmaliger
   qualifizierter Modellaufbau für Inventar/Relationen, reine RecordedSource-
   Nachweise nur je äußerem Aufruf, begrenzte Checkpoint-Objektbytes je
   Kettenlesung sowie entfallende doppelte Ergebnis-/Statusprüfungen in
   Testhelfern. Native Grund- und Sicherheitsabnahmen gehören bereits zu W.
2. `TEST-PERFORMANCE.R` — `test(performance): cover reuse bounds and fresh source checks`
   Zusätzliche Abnahmen für Verdrängung, große gültige Register, konkurrierende
   öffentliche Werte, ungültige Eingaben, veränderte historische Bindungen und
   Bytes, nicht unveränderliche Dateicontainer und weiterhin aktuelle Quellen.
   Die bereits vorhandenen Produktgrenzen werden dabei vollständig erhalten.
3. `TEST-PERFORMANCE.C` — `refactor(performance): separate cache admission and value rebuilding`
   Zulassung unveränderlicher RecordedSource-Schlüssel und Rekonstruktion
   eigener Register-Records aus den privaten Cachewerten getrennt benennen.
   Parsergrammatik, Cachegrenzen, Fehler und Fachverhalten bleiben gleich.
4. `TEST-PROFILING.W` — `feat(dev): persist selected parallel test profiles and traces`
   Alle/Top-N/freie Testauswahl, gefrorener Quellsnapshot, native parallele
   Ausführung mit CPU-Zuordnung, cProfile je Phase, strace, Prozessdaten,
   versionierte SQLite-Speicherung einschließlich Rohbytes, Status und Export.
   Kleine echte pytest/xdist-Integrationen prüfen Auswahl und Phasenerfassung.
5. `TEST-PROFILING.R` — `fix(profiling): reject changing artifacts and inconsistent run outcomes`
   Rohdaten beim Import an den geöffneten Dateideskriptor und unveränderte
   Signaturen einschließlich ctime binden. Links, Dateiwechsel und abweichende
   erneute Importe ablehnen; unvollständige Importe erhalten. Beschädigte
   komprimierte Daten dürfen keine Ausgabe veröffentlichen. Vollständige
   Phasen allein dürfen einen fehlenden oder fehlerhaften Prozessabschluss
   nicht in einen erfolgreichen Lauf umdeuten.
6. `TEST-PROFILING.C` — `refactor(profiling): separate outcome checks and artifact indexing`
   Native Ergebnisprüfung und Rohdatenarchivierung von der Prozesssteuerung
   trennen. Befehle, Datenbankschema, Auswahl und Fehlerverhalten erhalten.

Jeder Zustand wird erst nach dem erfolgreichen Gate und Commit seines
Vorgängers ausgebracht. Geänderte/neue Testdateien, relevante Regressionen und
die unveränderten zehn Diagnosefälle sind explizit ausgewählt. N=3,
Laufzeitfilter und ungefilterte Pflichtauswahl bleiben die bestehenden Regeln.
Stabile Testnummern werden nur angehängt. In Dev erfolgen ausschließlich
statische Prüfungen, reine Collection und native Paketvalidierung.

## Grenzen der Optimierungen

Registerschlüssel sind die vollständigen Eingabebytes; Hash und Version werden
bei jeder öffentlichen Konstruktion geprüft. Nur erfolgreiche reine Parses
werden behalten. Ausgegebene Mapping- und Record-Objekte gehören jeweils dem
Aufrufer. Der Cache bleibt begrenzt; größere gültige Eingaben werden vollständig
verarbeitet. Kein Host-Locale-, Netzwerk- oder Projektpfad-Fallback entsteht.

RecordedSource-Wiederverwendung betrifft ausschließlich erfolgreiche reine
Prüfungen der vollständigen unveränderlichen Bindungs- und Dateibytes innerhalb
eines äußeren Aufrufs. Aktuelle Quellen, Autorisierungen, Journalentscheidungen,
Sperren und Veröffentlichungen werden dadurch nicht ersetzt. Die Relations-
auswertung nutzt dieselben qualifizierten Records wie das Inventar, einschließlich
der bestehenden Legacy-Navigation. Es wird kein Modell über Aufrufe hinweg geteilt.

Checkpoint-Objektbytes sind nur innerhalb einer Kettenlesung wiederverwendbar,
mit höchstens 16 MiB und 4.096 Einträgen. Ein Treffer prüft weiterhin die Größe
der jeweiligen Referenz und die Metadatengrenze. Alle tatsächlich gelesenen
Dateien bleiben im vollständigen abschließend geprüften Lesesatz, auch wenn das
Cachebudget erschöpft ist. Jede neue Kettenlesung beginnt frisch. Pointer,
Kontrollrecords, native Datei-/Besitzer-/Lockprüfungen, fsync und sämtliche
Veröffentlichungsbarrieren bleiben erhalten. Die bestehende Grenze gegenüber
nicht kooperierenden externen Eingriffen wird nicht als atomarer Snapshot ausgegeben.

Die Testhelfer verwenden bereits nativ gelieferte Manifeste beziehungsweise
geprüfte Continuation-Werte. Eine verpflichtende erste Ergebnisprüfung bleibt
erhalten. Identische Schutzpfade werden innerhalb eines Aufbaus einmal gebunden;
unterschiedliche Quellen und alle Quellenrollen bleiben bestehen. Vollständige
Register-, Legacy-, Publikations-, Manipulations- und Recoveryreferenzen bleiben
Teil der Apply-Abnahme. Es gibt keine größere Schrittweite oder geteilte
veränderliche Projektfixture zur Beschleunigung.

## Diagnose und spätere Messung

Die gespeicherten Profile begründen zwei Hauptursachen: wiederholtes vollständiges
Registerparsen und wiederholtes Einlesen/Prüfen gemeinsamer Work-Objekte. Die
ursprünglichen Profile und Messhistorien bleiben erhalten. Ihre instrumentierten
Zeiten sind kein unbeeinflusster Benchmark und beweisen keine neue Beschleunigung.

Die Bedienung und Datenbanktabellen des Werkzeugs stehen in
[Test-Profiling](Test_Profiling.md). Seine kleinen Apply-Integrationstests benötigen
keine systemweite strace-Installation. Ein ausdrücklich gestarteter echter
Profilinglauf benötigt strace; er ist kein Bestandteil der Bundle-Ausführung.
Ein späterer Vergleich muss dieselben Testidentitäten, Setup/Call/Teardown,
Host, Workerzahl und Instrumentierung berücksichtigen. Keine fremde oder
instrumentierte Laufzeit wird als normale Messung der anderen Linie gespeichert.
