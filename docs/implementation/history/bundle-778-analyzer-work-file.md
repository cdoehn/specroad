# Bundle 778 — native Work-Datei im Fehlerfall unverändert zurücklegen

Das native Result von [Bundle 777](bundle-777-analyzer-resume-metrics.md),
SHA-256 `264164f0c729156721b2aff48091acd45873948c3d03f1074618d8cbd476cdb4`,
belegt den erfolgreichen Commit 19.w.W mit 9.080 bestandenen Tests.
Commit `57599a113db71547c01d66473258d825ecce4525` bleibt erhalten und wird
nicht wiederholt. In 19.w.R bestanden 9.280 Tests; der Test für fehlende
Work-Objekte scheiterte beim abschließenden Wiederaufruf mit Code 7 statt 1.
Der vollständige offene Rest ist 19.w.R/C und 19.x.W/R/C, mit unveränderten
IDs, Rollen, Commitnachrichten und jeweils eigenem Apply-Gate.

Die statische Diagnose folgt dem unveränderten nativen Sicherheitsvertrag:
Checkpointobjekte entstehen als private Dateien (0600). Der Test entfernte
ein Objekt und erzeugte es anschließend mit `Path.write_bytes` neu; diese
Neuanlage erbt die Host-Umask und erhält nicht automatisch den ursprünglichen
privaten Modus. Die native Work-Prüfung verweigert fremde Zugriffsrechte und
übersetzt diese Sicherheitsverletzung in Code 7. Ein unveränderter Inhalt
allein stellt deshalb die ursprüngliche gültige Testvoraussetzung nicht her.

Der Test lagert die tatsächliche Originaldatei nun außerhalb des Work-Baums
im eigenen temporären Verzeichnis aus und legt dieselbe Datei zurück. Der
fehlende Objektpfad, der echte Code-5-Fehler, der unterbliebene Workerstart
und die unveränderten übrigen Work-/Tracebytes bleiben geprüft. Vor dem
abschließenden Resume werden wiederhergestellte Bytes und der ursprüngliche
Dateimodus ausdrücklich geprüft. Dessen ursprüngliche Erfolgsbedingung bleibt
erhalten und zeigt bei einem Fehler zusätzlich das native Resultobjekt.

Diese Fixture-Korrektur ändert keine produktiven Dateirechte, Sicherheits-
prüfungen, Wiederaufnahmeverträge oder Ressourcenbudgets. Sämtliche Produkt-
und Messbytes bleiben pro Stage unverändert, ebenso Test-IDs und bestehende
Abnahmen. Die vollständige Testdatei sowie Work-/Analyzer-Regressionen bleiben
Pflichtauswahl. Keine neue normative Entscheidung oder erfundene Abnahme;
menschliche Reviews und 19.t bleiben vor 19.y offen.
