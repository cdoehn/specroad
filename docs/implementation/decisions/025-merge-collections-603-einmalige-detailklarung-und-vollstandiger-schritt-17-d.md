# MERGE-COLLECTIONS-603 — einmalige Detailklärung und vollständiger Schritt 17.d

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## MERGE-COLLECTIONS-603 — einmalige Detailklärung und vollständiger Schritt 17.d

Ausdrücklicher manueller Nutzerauftrag vom 5. November 2026: die bisher
blockierte Detailklärung einmalig freigeben und nach Übergabe des Patches
für Apply beenden. SPECROAD-DECISION-1 und 2.4.3.1 erlauben diesen einen
Klärungspräfix vor der vollständigen Umsetzung in derselben ZIP. Der zuletzt
automatisch verweigerte Vertrag und die Control-Historie werden nicht
umgeschrieben; kein allgemeines Budget und keine Automatik werden aktiviert.

Technische Grundlage: nativ geprüftes sauberes Result
`specroad-apply_Result_121026_1105_a3436b.zip`, SHA-256
`5cdcf3b1b199626bc715622bb1772d5b9364a8492549bb5eee1c3c4f2afa1d7d`,
Abschlusscommit `6735602c06a864d03599b5e0f59fbdf08e35b456`.
CONTROL-BLOCKED-601.R/C wurden im Korrekturbundle 602 mit 7.676/7.699 Tests
jeweils erfolgreich committed. Der Produktstand ist weiterhin 702/900,
letzter Plancommit 17.c.C. Diese Gruppen sind kein Vollsuite-Nachweis.

Lücke: SR-REQ-0367 fordert schemafeste stabile Mengenschlüssel, aber die
eingebauten Schemata deklarieren weder Collection-Art noch Schlüssel.
17.c lässt konkurrierende Arrays daher absichtlich ungelöst. Geprüft wurden
die vollständigen Schemafabriken, Feldmerge, Quellinventur, SR-REQ-0365/0367/
0542, Abschnitt 10.15 und K.3 sowie die vollständigen Schritte 17.d–17.o.

Alternativen: (1) aus Feldnamen/Elementformen automatisch Mengen erraten;
(2) sämtliche Arrays dauerhaft als Konflikt behandeln und den Planschritt
nur teilweise umsetzen; (3) eine kleine ausdrückliche Schemaannotation samt
abschließender anfänglicher Feldbelegung festlegen. Gewählt wird (3): keine
Heuristik, keine neue Identitäts- oder Schreibfreigabe, keine externen Fakten.
Die Eingaben bleiben unverändert; die rein lesende Erweiterung ist durch
spätere versionierte Vertragsänderung reversibel. Reihenfolge und Original-
beobachtungen bleiben erhalten. Abwesenheit von Dateien wird nicht als
bewusste Löschung interpretiert; dafür wird ein separater expliziter Wunsch
gefordert, der weiterhin keine Writerberechtigung erteilt.

Normative Festlegung steht zuerst in 10.15.2. Die aktive Katalogbindung wird
mitgeführt; historische Nachweise bleiben unverändert. Die vorhandene API
ohne Schema-ID behält ihr Verhalten. Nur tags, Term-Synonyme und die benannten
Konfigurationsdimensionen erhalten deklarierte Mengensemantik. Relations-
historie, unveränderbare Ressourcen, endgültige Zielvalidierung, CLI und
Publikation bleiben Aufgaben der unveränderten nachfolgenden M17-Schritte.

W liefert vollständige schemafähige Mengenmatrix mit stabilen Schlüsseln,
verschachtelten Mengen, strikter Quellvalidierung und schreibfreiem Vergleich
echter Anhangbytes einschließlich expliziter Entfernung. R vervollständigt
die Fehlerklassen geordneter Folgen, portable Pfad-/Unterpfadkollisionen und
die Robustheitsmatrix für verschachtelte, fehlende und widersprüchliche Werte.
C trennt reine Schema-/Anhanghelfer ohne Fachänderung; W/R-Testbytes bleiben
gleich. Synthetische Integration verwendet echte qualifizierte Mergequellen
und die vollständige Inventur, keine ersatzweise erfundenen Modellwurzelhashes.

Die Klärungsstage lässt alle drei 17.d-Commits offen. Nachfolgende Checkboxen
und Produktzähler sind Commitzielzustände, erst nach bestandenem eigenem
Apply-Gate und echtem Commit wirksam. Jede Stage erhält gefilterte fällige
N=3-Gruppe plus vollständige ungefilterte Pflichtauswahl. Kein Endstand wird
vorab ausgebracht. Dev führt nur Syntax, Collection und native Paketprüfung
aus; keine Verhaltenstests und kein behaupteter Abnahmeerfolg. Nach atomarer
Übergabe genau dieser ZIP endet der Auftrag ohne Apply-/Warteschleife.
