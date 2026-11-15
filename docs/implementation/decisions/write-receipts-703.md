# WRITE-RECEIPTS-703 — normale Belegstruktur ohne Recoverybilder

Datum: 15. November 2026. Autorität: delegiert gemäß SPECROAD-DECISION-1,
Vertrag 4, positive ausdrückliche Freigabe im gebundenen Auftrag.

18.t und Anhang C verlangen eine nächste geschlossene Receiptversion, legen
aber deren Feldmenge nicht fest. Geprüft wurden C.1/C.2, 10.6/10.7, Anhang N,
RECOVERY-REMOVAL-006 sowie native Receipt-, Proposal- und Qualifikationsleser.
Die alten Belege enthalten ein vollständiges ausführbares Recoveryjournal.
Unveränderte v1-Daten würden damit den bestätigten Rückbau nicht erfüllen;
ein ungebundenes Erfolgsflag würde Originalnachweise und Idempotenz verlieren.

Gewählt ist die kleinste eigenständig unterscheidbare v2-Beleggruppe: gebundene
Marker-/Auditdaten, echte Ressourcenhashes, vollständiger Zielbefund und dieselbe
semantische Ergebnisform sowie unveränderte Belegpfade. Normative Feldmengen
stehen ausschließlich in C.2.1. Es gibt keine neue Requirement-ID. Historische
Daten bleiben erhalten, neue Schreiber besitzen keinen Recovery-Fallback.

Der bereits beauftragte inkompatible Rückbau vor Produktnutzung deckt den
Formatwechsel. Scope, Pfadsicherheit, Fachprüfung, Autorität, Human-Reviews,
W/R/C, TD-001 und unveränderte externe Plattformnachweise bleiben wirksam.
Die Änderung ist versioniert rücknehmbar; fremde oder lokale Betriebsdaten
werden weder migriert noch gelöscht. Keine erfundene Einzelzustimmung.

18.t.W implementiert den vollständigen gemeinsamen Schutz-/Publikationsweg
und normale Beleglesung. R ergänzt adversarielle Grenzen und Crashmatrix; C
trennt Schutzprotokoll, reine Belege und Publikationsadapter ohne neue Semantik.
18.u stellt erst danach sämtliche normalen Aufrufer um; 18.v die Spezialwriter.
Eine vorbereitete Stage gilt erst nach ihrem eigenen erfolgreichen Apply-Gate.

Abnahmen: erfolgreiche Create/Replace/Delete-Publikation, native Zielgates,
fehlende/veränderte Belegteile, Requestkonflikte, tatsächliche Prozessabbrüche,
I/O-/Unlink-/Synchronisationsfehler, aktive/unklare/verwaiste Owner, Links und
Quell-/Roottausch. Offener Marker schlägt vorhandene Zielbytes und Receipts.
Keine automatische Reparatur und keine verlorene ursprüngliche Testabdeckung.
