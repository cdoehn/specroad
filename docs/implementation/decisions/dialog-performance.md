# DIALOG-PERFORMANCE — ausdrücklicher Nutzerauftrag vom 18. November 2026

Normative Grenze: [Spezifikation 2.5.6](../../specification/SpecRoad_Spezifikation.md#256-testoptimierungen-und-explizites-profiling).
Die separate Hostbegrenzung hat ihre eigenen Commits. Dieser Auftrag optimiert
wiederholte reine Arbeit; Produktplanpositionen und deren Status bleiben erhalten.

- `DIALOG-PERFORMANCE.W`: bedarfsgerechte Register-Records mit gemeinsamem
  unveränderlichem Index; vollständige Schema-Vokabularprüfung einmal je
  geordneter JSON-Definition; begrenzte aufruflokale Wiederverwendung reiner
  Projektmodelle mit eigener tiefer Kopie je Verwendung. Öffentliche Proposal-
  Apply-, Check-, Review-, Historien- und Änderungseinstiege eröffnen den vorhandenen Kontext.
  Abnahme: vollständiges Register, unveränderte Instanzfehler, unbenutzte
  Schemaäste, voneinander getrennte Modell-, Binding-, Profil- und Recordobjekte.
- `DIALOG-PERFORMANCE.R`: Cachegrenzen und Verdrängung, ungeeignete Definitionen,
  Typ-/Reihenfolge-/Referenzunterschiede, Nebenläufigkeit, veränderte Originalbytes,
  Fehlerbereinigung und Legacy-Modelle; aktuelle Provider bleiben frisch.
- `DIALOG-PERFORMANCE.C`: unveränderliche Registerwert-Sicht und Schema-
  Cachezulassung von den jeweiligen fachlichen Parsern trennen. Testbytes und
  Pflichtauswahl von R bleiben unverändert; keine neue Verhaltensentscheidung.

Je Stage eigenes N=3-plus-Pflichtgate vor dem Commit. Pflicht bleiben alle
vorhandenen Proposal-/Dialog-/Review-/Apply-, Schema-/Sprach-, Modell-,
Qualifikations-, Publikations-, Writer-, Merge- und Legacy-Regressionen sowie
alle neuen/geänderten Testdateien. Der lange Dialogtest und seine Fixture
bleiben bytegleich; keine gestrichenen Assertions, Mock-Writer oder kleinen
Ersatzregister. Native Prüfer bleiben auch in den neuen kleinen Regressionen aktiv.

Speichergrenzen: vier Registerbilder bis je 1 MiB, 128 erfolgreiche Schema-
Definitionen bis je 512 KiB/16.384 JSON-Werte und der vorhandene gemeinsame
Aufrufcache mit acht Einträgen; Modellzulassung höchstens 16 MiB/65.536 Dateien.
Größere zulässige Daten durchlaufen die vollständige Prüfung ohne Aufnahme.
Die Modellkopie enthält keine Live-Dateideskriptoren oder Autoritätsobjekte.

Als späteres Messziel gilt eine Halbierung der vollständigen Dialoglaufzeit
auf demselben Host mit gleicher Parallelität. Das ist kein bereits gemessener
Speedup. Instrumentierte Profile und normale Apply-Zeiten getrennt auswerten.
Diese private Vorbereitung führt keine Verhaltenstests aus und startet keine
Automatik. Ihre echte Übernahme benötigt ein frisches maßgebliches Result.

Gebundene Übernahme: [Bundle 740](../history/bundle-740-host-once-dialog-performance.md).

Nach bestätigtem W: [Korrektur 741](../history/bundle-741-dialog-error-contract.md) erhält sämtliche R/C-Abnahmen und prüft die unveränderte native Fehlerklasse exakt.
