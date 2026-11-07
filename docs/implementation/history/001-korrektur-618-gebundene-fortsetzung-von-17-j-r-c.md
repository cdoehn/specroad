# Korrektur 618 — gebundene Fortsetzung von 17.j.R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrektur 618 — gebundene Fortsetzung von 17.j.R/C

Maßgeblich ist das nativ geprüfte Fehler-Result `specroad-apply_Result_035652_1106_59fcdc.zip`,
SHA-256 `d685a41e0864305525e522918ddbc505983c8558ee1075ba08af590c8592bb73`, HEAD `08ecfe2349d710c2856e5e3dd7f96a472367e140`,
Fingerprint `87ff4fcc58540c41`. Bundle 617 hat 17.j.W als
08ecfe2349d710c2856e5e3dd7f96a472367e140 nach 10005 bestandenen Tests
committed (Gruppe 0 plus 4069 Pflichttests). Dieser Commit und der bereits
abgeschlossene Klärungscommit MERGE-TARGET-616 bleiben erhalten.
17.j.R scheiterte vor seinem Commit mit elf Fehlern und 10079 bestandenen
Tests; 17.j.C wurde nicht ausgeführt. Der vollständig rekonstruierte,
erhaltene R-Arbeitsstand ist die Korrekturbasis, nicht nur der Base-Snapshot.

Die elf Fehler liegen in `tests/test_merge_target_right.py`: neun Varianten
der nativen Reviewprüfung und die Nachprüfung eines veralteten Reviews rufen
die nicht vorhandene Methode `SourceSnapshot.load` auf. Sie verwenden nun
den bestehenden öffentlichen Konstruktor `SourceSnapshot(SourceRequest(...))`.
Die tatsächlichen nativen Revieweingaben und sämtliche positiven/negativen
Erwartungen bleiben erhalten; kein Provider oder Validator wird ersetzt.

Der Baseline-Quellartentest erhält bereits `target_validated=true`, vergleicht
aber die rekonstruierte Konfiguration byteweise mit den Betriebsfeldern des
ursprünglichen Arbeitsprojekts. Der bestehende Baselinevertrag bewahrt die
semantische Konfiguration und rekonstruiert ausgeschlossene betriebliche Werte.
Der korrigierte Test verlangt exakte Zielgleichheit mit der qualifizierten
Quelle, dieselbe vollständige Pfadmenge und bytegleiche übrige Originaldateien.
Die semantische Projektion wird zusätzlich mit den archivierten Originalbytes
und ihrem Konfigurationshash verglichen; die Zielwurzel muss der archivierten
Modellwurzel entsprechen. Local-, Bundle- und Git-Quellen behalten den
vollständigen ursprünglichen Bytevergleich. Der Schreibfreiheitstest bleibt.

Produktcode, normative Spezifikation, Klärungsabnahmen, Testidentitäten und
Nummern bleiben unverändert. Die vollständigen offenen IDs/Rollen 17.j.R/C
werden fortgeführt; keine neue Klärung und keine Budgetänderung. Beide Stufen
enthalten denselben korrigierten Test. C erhält weiterhin ausschließlich die
bereits angekündigte Strukturverschiebung passiver Ergebniswerte und seinen
Planfortschritt. Kein späterer Zustand wird vor dem vorigen Gate installiert.

Jede Stufe behält alle bisherigen ungefilterten Pflichtdateien und ihr eigenes
N=3-plus-Pflichtauswahl-Gate. R bleibt Gruppe 1, danach folgt C mit Gruppe 2.
Planfortschritt wird erst durch erfolgreiche Apply-Commits wirksam. Dev führt
nur Syntax-/Collection-/Paketprüfung aus, keine Verhaltenstests. Der gesamte
Schritt 17.j bleibt bis zum erfolgreichen Restabschluss offen; M17 sowie
Transaktions-/CLI-/Work-Integration in 17.k–17.l bleiben weiterhin erforderlich.
