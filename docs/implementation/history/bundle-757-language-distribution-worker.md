# Bundle 757 — Sprachdistribution und Workerstart

19. November 2026. Natives Quellresult SHA-256
`de9026a6b5e6cfdac73c6145dd2a545318d6b0f4b6387d8130a0c0309a2807c2`, sauberer HEAD
`2e845d6f0723edddd7a393548b3748216e118fd3`. Alle sechs Stufen 19.i.W/R/C und
19.j.W/R/C sind mit eigenen Gates committed; 831/918 bestätigt, kein offener
Korrekturrest. Ihre Testzahlen: 11602, 11746, 11706, 11616, 11766, 11718.

Die bereits geplanten vollständigen Gruppen 19.k und 19.l erhalten sechs echte
Zustände und sechs eigene Apply-Gates. T.6 legt Referenzversion, getrennte
ABI-Pakete, passiven Core und die Vertrauensgrenze bereits fest. Die konkreten
Wheelpins und das interne Entwicklungs-Paketmanifest setzen diesen Vertrag um;
keine neue öffentliche Produktdatenform, Detailklärung oder Budgetänderung.

19.k.W deklariert das optionale Extra und baut getrennte Offline-ZIPs aus
explizit bereitgestellten, originalen hashgeprüften Wheels. Adapter/Core,
NumPy-Wheel, py3langid, Referenzmodell, vollständige mitgelieferte Lizenzdateien
und ein deterministisches Datei-Hashinventar sind enthalten. Es gibt keinen
Resolver, Download oder automatischen Installer im ausgelieferten Produkt.
19.k.R prüft die vollständigen Inhalte gegen unabhängige Pins und Core-Identität.
Die explizite Laufzeitprüfung führt jede gewählte ABI separat mit ihrem echten
Interpreter aus und bindet beobachtete Python-/Bibliotheksversionen an das
jeweilige Paket. Die Matrixfunktion verweigert fehlende oder doppelt verwendete
ABI-Pakete. Core-Modul und Zipapp bleiben ohne NumPy-Binary verwendbar.
19.k.C trennt Wheelprüfung, Archivpublikation und Komposition strukturell; die
Core-Buildidentität wird unverändert wiederverwendet.

Die Originalartefakte wurden über die offiziellen PyPI-Versionsmetadaten
bezogen und vollständig gehasht. Statische Metadatenprüfung ist kein bestandener
Laufzeitnachweis. NumPy 2.2.6 ist für CPython 3.10 gepinnt; 2.3.5 mit jeweils
separatem Wheelhash für 3.11–3.14. Das mitgelieferte py3langid-Modell ist gebunden
an `f4f4a2c3465ca1f081541037f9cac23021d68151c2f709c55ae5eedfca522963`.
Primärquellen: [py3langid 0.4.0](https://pypi.org/project/py3langid/0.4.0/),
[NumPy 2.2.6](https://pypi.org/project/numpy/2.2.6/),
[NumPy 2.3.5](https://pypi.org/project/numpy/2.3.5/).

Der echte Offline-Integrationstest verwendet ausschließlich die originale
CPython-3.14-/Linux-x86-64-Kombination. Auf anderen ABIs prüft er die konkrete
Ablehnung und behauptet keinen erfolgreichen kompatiblen Lauf. Alle fünf
Paket-/Interpreterkoordinaten werden getrennt verlangt; vier fehlende reale
Interpreter oder Wheels werden niemals durch Skip, Mock oder eine wiederholte
3.14-Ausführung ersetzt. Reale 3.10–3.13-Nachweise sind hier weiterhin **offen**,
kein ARM-Nachweis, kein Klassifikations- oder Releaseerfolg. Gemäß dem bestehenden
M19-Abschlussgate blockieren fehlende plattformgebundene Nachweise die jeweilige
Freigabe, nicht die korrekt abgeschlossene lokale Umsetzung; 19.y und 20.k
bleiben vollständig offen. Die Entwicklungsartefakte weisen deshalb immer
`release_approved=false` aus. Es wurde keine externe Prüfumgebung eingerichtet.

19.l.W integriert den bekannten Worker in direkte und dauerhafte explizite
Analyseaufrufe. Interpreter und Importwurzel kommen ausschließlich aus der
laufenden vertrauenswürdigen Distribution. `-I -S -B`, ein fester Bootstrap,
explizites argv, stdin und kontrollierte Prozessumgebung vermeiden Shell,
Projekt-CWD-Imports und fremde Entry-point-Suche. Der komplette native Request
bleibt einschließlich aller Analyzer/Subjects gebunden. Externe Descriptoren
können keinen Prozess auswählen. Die Work-Abschlussprüfung bleibt passiv und
startet beim bloßen Lesen eines abgeschlossenen Ergebnisses keinen Worker.
19.l.R prüft auch mehrfaches/falsches JSON, falsche Requestbindungen, doppelte
Analyzer, Startfehler sowie tatsächliche vergiftete Projekt-/Umgebungsdateien.
19.l.C kapselt den Prozessadapter und erhält die W/R-Testbytes unverändert.

Der Worker liefert bis 19.n weiterhin ehrliche offene/unverfügbare Ergebnisse
mit Code 5. Er lädt noch kein Modell, behauptet keine Spracherkennung und wertet
keine aus Projektdaten gelieferten Modell-, Interpreter- oder Workerpfade aus.
Der bestehende Schreibversuchsschutz bleibt in Tests vollständig aktiv; nur
explizite neue Workeraufrufe erlauben dort einen Subprozess. Andere Helferaufrufe
behalten ihren bisherigen strikten Standard. Alle betroffenen Helferregressionen
gehören zur Pflichtauswahl. Modellladen, Lebensdauer-/Ressourcenintegration und
reale Entscheidungen bleiben den folgenden bestätigten Positionen vorbehalten.

Zielstand **19.k.C**, **834/918**, danach **19.l.W**:
erst nach seinem eigenen erfolgreichen Apply-Gate und Commit gültig. Dev führt
keine Testkörper, Fixtures oder Testprozesse aus. Reine Collection, statische
Analyse und native Paketvalidierung sind keine vorweggenommene Verhaltensabnahme.
