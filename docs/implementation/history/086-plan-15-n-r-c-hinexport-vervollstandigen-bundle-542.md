# PLAN 15.n.R/C — Hinexport vervollständigen (Bundle 542)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## PLAN 15.n.R/C — Hinexport vervollständigen (Bundle 542)

Maßgebliche technische Basis: vollständig nativ geprüftes Result
`specroad-apply_Result_193743_1101_7902d2.zip`, SHA-256
`b2b4dc57257d5e6dba543cda76dbcf653299ae4bba16efee518e6fbf8012d6ec`,
sauberer HEAD `d17b048a823492a53e2e83412f7f782632fb3f89`.
Bundle 541 ist mit echten W/R/C-Commits und 6573/6609/6645 bestandenen
Apply-Tests abgeschlossen. Dies sind gefilterte Rotationsgruppen plus
Pflichtauswahl, kein Vollsuite- oder Plattformfreigabenachweis.

Der einmalige N-Auftrag setzt den bereits geklärten Produktplan fort;
keine Spezifikationsklärung, Scope-Erweiterung oder neue normative Entscheidung.
Spec 0.2.46 mit W.1.1/W.2.1/W.3.1/W.6 bleibt unverändert maßgeblich.
R und danach C bilden zwei vollständige Zustände desselben Hinexports.
15.o und der Rückweg bleiben eigenständige offene Produktabschnitte.

R vervollständigt die Nachprüfung der gebundenen Runtime und Betriebsgrenzen
vor Capture, Snapshotnutzung und finaler Veröffentlichung. Private Kopien,
Workspace-Identität/Rechte, neue registrierte Repositorys, geänderte Exchanges,
Quellen und belegte Ziele dürfen weder ungebundene Writes noch Erfolg erzeugen.
Die private Projektion verwendet die vorhandenen deskriptorgebundenen
Verzeichnis-/Dateischreiber. Fehlgeschlagene Aufrufe bewahren tatsächliche
Referenzen und Diagnosebytes; keine automatische Wiederholung oder Neuplanung.

Vorbereitete Abnahmematrix: bestehende native Dirty-Schichten/Receipts und
ignorierte Pflichtbytes; Filter/Konversionen; Runtime-/Workspaceaustausch an
mehreren Phasengrenzen; veränderte Betriebsgrenzen; Pfadkollisionen, falsche
Profile und Teilpublikation; vollständiger öffentlicher Modul-/PYZ-Hinexport
und fortgesetzte Work-Kette. C trennt nur Projektprojektion und Kodierung vom
Ablauf. Die gleiche vollständige Pflichtauswahl schützt beide Zustände.

Dev führt keine Testkörper, Fixtures oder Testprozesse aus. Syntax, reine
Collection/Katalogprüfung und native Paketprüfung sind keine Verhaltensabnahme.
Jeder vorbereitete Fortschrittsmarker gilt erst mit dem zugehörigen erfolgreichen
Apply-Gate UND echten Commit; bei einem Fehler sind Log und tatsächlicher
Commitpräfix maßgeblich. Apply testet pro Zustand genau einmal die Vereinigung
seiner fälligen gefilterten N=3-Gruppe und ungefilterten Pflichtauswahl mit
hostabhängigen worksteal-Workern. Keine CI und kein Dienststart.

Vorbereiteter C-Zustand: `_snapshot_project` fasst nur die bestehende native
Snapshotprojektion, den exklusiven Stagingwriter und die anschließende
Projektbundle-/Receiptprüfung zusammen. Ein AST-Vergleich belegt unveränderte
Anweisungen nach Ersetzung der drei expliziten Abhängigkeiten. Der öffentliche
Export behält Reihenfolge, Fehler, Runtime-/Betriebsprüfungen und Ausgabegrenzen.
Keine neue Fachfunktion, keine neue Requirement-ID und kein Testkörperlauf.
