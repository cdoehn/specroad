# BOOTSTRAP-SNAPSHOT-715 — Fehlergarantie und Spezialabschluss

Datum: 16. November 2026. Quelle: erfolgreiches Result 714,
SHA-256 `549822fd1a4ae371d1c5049bae982265062f05bd9759209915ccd9d9818f9921`.
18.u.C wurde nach 15.532 bestandenen Tests committed; bestätigter Stand 771/918.

Der Nutzer bestätigt ausdrücklich die zuvor empfohlene Auflösung des Konflikts:
SR-REQ-0003 garantiert vor Schutzbeginn unveränderte Daten; danach bleibt ein
Fehler-/Abbruchbestand gesperrt, ohne Rollback oder Vervollständigung.
Diese konkrete Änderung der Garantie folgt aus dem Nutzerauftrag, nicht aus
dem positiven Control-Budget. Die blockierte Untersuchung und alte Evidence
werden nicht nachträglich als Erfolg oder frühere Befugnis ausgegeben.

Weitere notwendige Feldbindungen werden delegiert gemäß SPECROAD-DECISION-1
präzisiert: die geprüfte Vollsnapshot-/Backupbindung im gemeinsamen v2-Receipt
und ein zielgebundener Elternmarker vor jeglicher Rootwirkung. Ein Marker erst
im Ziel wäre zu spät für eine unterbrochene Rootanlage. Replaying alter
Bootstrapjournale widerspräche dem Auftrag; eine ungebundene Erfolgsmarke
verlör Originalnachweise. Die zwei exakt abgeleiteten Markernamen behalten
einen Eigentümerbeleg über eine fehlgeschlagene Markerentfernung hinweg.
Unveränderte passive Bootstrapnachweise bleiben lesbar, niemals ausführbar.

Normative Felder und Fehlergrenzen stehen in C.2.2/0003; SR-REQ-0480 und
der Root-Begriff werden widerspruchsfrei an die bereits beauftragte
Freigabegrenze aus 11.7 angeglichen. Gesperrte Teilpfade sind kein
veröffentlichter nutzbarer Projektroot.
Keine neue Requirement-ID, keine Scopeerweiterung, keine laufende Migration,
keine fremden Daten oder Historien werden gelöscht. Spec1.4 erlaubt den
beauftragten Formatwechsel vor Benutzungsfreigabe. Sicherheits-/Fachgates,
menschliche Reviews, Originale, stabile Testnummern und W/R/C bleiben bestehen.
Die versionierte Änderung ist rücknehmbar; sie erteilt keine Datenlöschbefugnis.

W: gemeinsame Migration-/Mergewriter und normale erfolgreiche Root-/Sandbox-
Erzeugung; echte Abbruchsperre verhindert jeden Retry im alten Ziel.
R: vollständige Backup-/Legacy-/Lösch-/Schema-/Receiptprüfung, adversarielle
Owner-/Pfad-/Inputwechsel; normale Abschlussleser aus Recovery herauslösen.
C: gemeinsame Primitiven und Entfernung obsoleter ausführbarer Spezialjournal-
und Bootstrap-Replayimplementierung bei bytegleichen W/R-Testoracles.

Abnahme: vor Schutzbeginn unverändert; echte Prozessabbrüche und I/O-Fehler an
allen Schutz-/Publikations-/Abschlussgrenzen; alte Ziele einschließlich fehlender
Konfiguration bleiben schreibfrei gesperrt, anderes leeres Ziel funktioniert.
Positive Migration/Merge, Migration-Verify, Bundle-/Sandboxerzeugung und
historische Receipts behalten ihre Fachprüfungen. Aktive/unklare/fremde Owner,
Links, beschädigte Marker, fehlende Backup-/Originaldaten und Quelltausch
erzeugen keinen Erfolg. Keine Dokumentations-/Darstellungstests.
Produktumsetzung und Apply-Nachweise sind im Präfix ausdrücklich noch offen.
