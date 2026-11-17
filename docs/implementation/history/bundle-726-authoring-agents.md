# Bundle 726 — Authoring als Proposal und Agentenverträge

Das native Result mit SHA-256
`16207b2adebe0c70b9a04fae3751a60c798d0c8d4d5c6391a87114de935ae8b4`
bestätigt das vollständige Bundle 725 bis einschließlich **18.x.C**,
Commit `3fda4e4a8d4555421475465f3b47ec2831a22d7a`, sauberer Projektstand.
Die letzte Stage meldet 13.963 bestandene Tests; bestätigt sind 780/918.
Kein offener Korrekturrest und keine Wiederholung erfolgreicher Commits.

Die Detailentscheidung [AUTHORING-PROPOSAL-726](../decisions/authoring-proposal-726.md)
steht als einzige Klärung vor den vollständigen Gruppen 18.l.W/R/C und
18.m.W/R/C. Sie schließt den äußeren Entwurfsvertrag, ohne generische
Kontrollwrites, Reviewrechte oder Scopeausnahmen freizugeben. Budgetänderung
und Produktfreigabe werden nicht erklärt.

18.l.W verbindet den normalen vollständigen Planer mit einer isolierten
Entwurfsveröffentlichung über den nativen Writer. Fachoperationen und Defaults
bleiben erhalten; Fachdateien werden dabei nicht ausgeführt. Native vollständige
Projektqualifikation, Hostautorität, Sperre und Receipt bleiben erforderlich.
Die gemeinsame vorbereitete Authoring-API deckt die vorhandenen normalen
Operationfamilien ab. Kontroll-/Baseline-Pläne bleiben gemäß 10.8.1 gesperrt.
18.l.R ergänzt Preview/strukturierte Ergebnispfade, frühe Actor-/Requestprüfung,
Negativfälle und vollständige Dokument-/Evidence-Kompositpläne. 18.l.C trennt
die äußere native Qualifikation vom fachlichen Planumbau; W/R-Tests bytegleich.

18.m.W vervollständigt tatsächliche native Capability- und Reviewvoraussetzungen.
Ein verfügbares Recordschema wird nicht als beliebiger ausführbarer Befehl
beworben. Die Proposal-Recordversion folgt dem registrierten nativen Leser;
Python-Authoring und CLI-Registrierungen bleiben getrennt. 18.m.R liefert die
vollständigen Requestverträge der realen Transportvarianten und prüft
nichtmenschliche Reviewverweigerung am echten Handler. 18.m.C bündelt die
Autorisierungsbeschreibung und ihr Schema ohne Verhaltensänderung.

Die zusätzlichen Tests beobachten fachliche Ziele/Defaults, echte Datei- und
Receiptwirkungen, verweigerte Rechte, unveränderte Quellen, strukturierte
Requestbindung und tatsächliche Handlerfehler. Keine Help-/Layout-/Dokumenttests.
Bestehende Tests und Nummern werden erhalten; geänderte generische Operation-
Fixtures erhalten die neue geschlossene Form und ihre vollständigen Verbraucher.
Nicht registrierte Raw-Input-CLIs bleiben als offene Gesamtabnahme 18.p sichtbar;
18.l schaltet deren bereits vorhandene native Plan-/Ausführungsschicht um.

Jede Stage besitzt ihr eigenes N3-plus-Pflichtauswahl-Gate vor ihrem Commit.
Dev prüft ausschließlich Syntax, statische Abhängigkeiten, reine Collection
und native Paketverträge. Die vorbereiteten Fortschrittswerte werden erst
nach dem jeweiligen erfolgreichen Apply-Gate übernommen, nicht als vorher
bestandene Verhaltenstests ausgegeben. Es gibt keine eigene Apply-Schleife.

Zielstand dieser Stage: **18.m.R**, **785/918**, danach **18.m.C**.
