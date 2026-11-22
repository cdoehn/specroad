# Bundle 793 — vollständige Korrektur von 21.a.W/R/C

22. November 2026. Maßgeblich ist das native Fehler-Result mit SHA-256
`92fc9a520be88876dabb6bbb55c333048aa56e9b2ee718fddd13f4cfa5827c06`.
Bundle 792 scheiterte im ersten Gate mit **51 fehlgeschlagenen und 25.071
bestandenen Tests**. Kein Commit entstand. Die bestätigte Basis bleibt
**888/996** bei `8ca0287085b3a0a7a68cb70033db3db4a02beef3`.
Der vollständige offene Rest **21.a.W, 21.a.R, 21.a.C** bleibt in dieser
Reihenfolge mit den ursprünglichen Rollen `implementation` erhalten.
Die Korrekturbindung bezeichnet genau diesen Rest des alten Commitplans.

Dieser Zielbestand gehört zu **21.a.W** und gilt erst nach dessen eigenem
erfolgreichen Apply-Gate und Commit. Jeder Zwischenstand wird einzeln
ausgebracht und geprüft. Der Endstand wird nicht vorab installiert.
Dev führte ausschließlich Syntax-, Collection-, Schemaform- und passive
native Paket-/Fortsetzungsprüfungen aus: **tests_run=0**.

## Belegte Ursachen und Reparaturen

- Die Befehlsregistrierung von `config.show` importierte Modell-/Ressourcencode
  bereits bei Hilfe und Versionsausgabe. Fachimporte erfolgen jetzt erst im
  aufgerufenen Handler beziehungsweise in der Konfigurationsprojektion.
- Der geschlossene öffentliche Befehlskatalog im Regressionstest fehlte um
  den tatsächlich vorgesehenen lesenden Config-Befehl. Die exakte Erwartung
  wurde ergänzt; die Prüfung unerlaubter Aliase bleibt bestehen.
- `init` erzeugt weiterhin ausdrücklich Projekte im Format 0.2. Die erweiterte
  Typregistrierung ließ aber den neuen Planordner in diese alten Projekte
  gelangen. Das Anfangsinventar verwendet wieder genau die Typen seiner
  Projektversion; alle bisherigen Bootstrap-/Abbruchoracles bleiben erhalten.
- Der native Init hinterlässt sein ursprüngliches Bootstrap-Journal. Der
  additive Migrationspfad kann dieses eine bekannte passive Original jetzt
  anhand der geschlossenen nativen Wertgrammatik und gebundenen Distributions-
  Ressourcen vom Modellinput trennen. Der vollständige Backup-/Migrations-
  Bestand erhält dieselben Journalbytes als geschützte Originale. Historische
  Inodes und der damalige Zustand sind keine aktuelle Konsistenz- oder
  Abschlussfreigabe. Native Live-Prüfung, Sperre, Writer und vollständige
  Zielvalidierung bleiben verpflichtend. Unbekannte oder aktive Betriebsdaten,
  zusätzliche Dateien und beschädigte Originale werden nicht ausgeblendet.

Die Journal-Wertprüfung wird mit dem vorhandenen Bootstrap-Reader geteilt.
Dessen aktuelle Root-/Stage-Inodeprüfungen bleiben bestehen. W erhält den
vollständigen reparierten Umfang aus [Bundle 792](bundle-792-plan-model.md).
R ergänzt 13 native Original-/Negativfälle sowie den bisherigen vollständigen
R-Umfang. C behält alle W/R-Testquellen bytegleich und nur die bereits geplante
verhaltensgleiche Strukturbereinigung.

Alle 51 fehlgeschlagenen Identitäten und die vollständigen bisherigen
Pflichtauswahlen bleiben gebunden. Neue R-Identitäten werden hinter den
bereits angekündigten Nummern angehängt, keine Nummer wird wiederverwendet.
Jedes Gate vereinigt die fällige gefilterte N=3-Gruppe mit der ungefilterten
Pflichtmenge. Das bisherige grüne Teilresultat ist keine Abnahme der Reparatur.

Normative Spezifikation, Entwicklungsvertrag und Apply-Testpolicy bleiben
unverändert. Der historische 0.2-Migrationsvertrag behält seinen Hash
`e844cb7008efd11ff58bd09c54e07822d7a22b540acc2164446fa12aa2ae4f36`.
Keine neue Klärung, keine erfundenen Messungen oder menschlichen Freigaben.
Nach erfolgreichem 21.a.C wären **891/996** Produktpositionen abgeschlossen;
danach folgt unverändert **21.b.W**. Der bestätigte technische Rest und die
menschlichen Schlussabnahmen bleiben vollständig erhalten.
