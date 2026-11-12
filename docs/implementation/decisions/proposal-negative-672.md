# PROPOSAL-NEGATIVE-672

12. November 2026. Delegiert gemäß SPECROAD-DECISION-1 / 2.4.3.1.
Quelle: erfolgreiches vollständiges Result 671, SHA-256
`117ae4019853c5169034de0a8c2f3ddaf0c846a45c4ea49e05997d1e2aa2265a`.

18.j verlangt neue autorisierte Widerrufe; 10.3 definiert deren Endzustand,
10.3.4 bislang nur neue approved/rejected-Zeilen in_review. Es fehlen
CLI-Wert, eigene Zustimmungsbindung und die persistierte negative Operation.
10.7.10 liefert nur den lesenden Kern, keine neue Schreibformatbefugnis.

Geprüfte Alternativen: Alte Reviews löschen/überschreiben verliert Nachweise.
Eine allgemeine Actor-Override-Option schwächt die Autoritätsgrenze. Ein neuer
Reviewdienst mit eigener Transaktion dupliziert den Writer. Gewählt wird die
kleine additive v2-Variante auf dem vorhandenen Fachbefehl und Writer. Alte
v1-Bytes bleiben lesbar; die neue negative Zeile ist eindeutig versioniert.
Widerruf betrifft nur die eigene frühere Zustimmung zur gleichen Bindung.
Die vorhandene Kontrollmatrix verlangt bei approved den Endstatus rejected,
keine erfundene Rückkehr nach in_review. Unterhalb des Quorums bleibt dagegen
in_review ohne künstliche Selbsttransition. Nichtleerer Widerrufsgrund ist
eine neue Eingabe für die neue Aktion; bestehende Aufrufe bleiben erhalten.

Scope und Reihenfolge 18.j bleiben erhalten; keine neue Produktposition oder
18.k-Transaktion. Herkunft, echte Human-Entscheidung, aktuelle Basis, Lock,
Quorum, Recovery, Sicherheits- und Reviewpflichten werden nicht abgeschwächt.
Keine Migration, Löschung, externe Voraussetzung oder behauptete Freigabe.
Die versionierte Ergänzung ist für zukünftige Änderungen zurücknehmbar,
ohne gespeicherte Originalbelege oder historische Nachweise umzuschreiben.

Normativ: Spec 10.3.5. Vollständige Abnahmen: Ergänzung 18.j. Der Klärungsstand
ändert keinen Produktfortschrittszähler. Umsetzung und Apply-Nachweise stehen
noch aus; jeder folgende W/R/C-Zustand bekommt sein eigenes Testgate.
