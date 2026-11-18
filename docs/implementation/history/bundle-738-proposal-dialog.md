# Bundle 738 — Vollständiger nativer Proposal-Änderungsdialog

Das maßgebliche native Result mit SHA-256
`1f311874cefe4e8536dab6e0aadc14964fca8a17f590420535a923561cd14314`
bestätigt 18.o.R und 18.o.C, zuletzt Commit
`01ef916d6db33e1c6be6ebd49cddf18cb8b25483`, ohne offenen Rest und mit sauberem
Arbeitsbaum. Die Gates bestanden 11.241 beziehungsweise 11.322 Tests, davon
jeweils 5.483 Pflichttests. Bestätigter Ausgang ist 792/918.

Der notwendige einzelne Präfix PROPOSAL-DIALOG-738 präzisiert nach
SPECROAD-DECISION-1 die bislang fehlende native Veröffentlichung einer
vorbereiteten Inhaltsrevision. Seine Abwägung und Grenzen stehen in der
[Entscheidung](../decisions/proposal-dialog-738.md), normativ in 11.10.3.
Er ist keine Produktabnahme und ersetzt keine menschliche Entscheidung.

W ergänzt den geschlossenen proposal_change-Spezialisten im bestehenden
Writer: vollständige Vorherbytes, deterministischer Nachherrecord mit bereits
vergebenen Change-IDs, laufende native Qualifikation, unveränderte Sperren,
Receipts und Abbruchsperre. Der öffentliche native Dialog erzeugt tatsächlich
einen Draft, prüft und reviewt ihn, veröffentlicht eine Inhaltsüberarbeitung,
weist die Unwirksamkeit alter Reviews nach, fordert erneute Freigabe und
publiziert exakt die Fachdateien. Alle Testakteure sind ausdrücklich synthetisch;
die Testhosts behalten die tatsächlichen Originale und Provenienz der Writes.

R bindet zusätzlich den deklarierten Plan-Nachherrecord und ergänzt Rejection,
veränderte Basis und rohe Vorherbytes, falschen Spezialisten, Kontroll-/Scope-
Angriff, verlorene Provenienz unter der Writersperre, fehlende Autorität,
Requestkonflikt und belegten historischen Replay. Eine echte unterbrochene
native Transaktion behält ihren Korruptionsmarker; keine automatische
Wiederholung oder Wiederherstellung. Canonical No-op erhält auch die aktuelle
Freigabe und erzeugt weder Revision noch Erfolgsreceipt. W-Nachweise bleiben.

C trennt die reine Sequenzrekonstruktion und die frische vollständige
Qualifikation vom nativen Publikationsablauf. Die Funktionskörper bleiben
bis auf einen lokal verlegten Import gleich. Sämtliche R-Testbytes und die
vollständige R-Pflichtauswahl bleiben erhalten.

Die allgemeinen CLI-Verträge werden nicht geändert. Die vorhandenen nativen
APIs sind die öffentlichen Integrationsgrenzen dieses Schritts; unimplementierte
CLI-Authoring-Adapter bleiben im Katalog ausdrücklich offen. Keine künstliche
Erfüllungsbehauptung für diese gesonderten Oberflächen oder für 18.q.

Dieser Durchlauf liefert eine vollständige W/R/C-Gruppe einschließlich der
notwendigen Writerintegration. 18.q bleibt der nächste vollständige Schritt:
sein nativer Rückpaketexport benötigt eigene öffentliche Paketvorbereitung,
exaktes passives Inventar und vollständige Negativabnahmen. Es wird kein
verkürzter Exportzustand angehängt. Dev führt ausschließlich Syntaxprüfung,
statische Prüfung, reine Collection und native Paketvalidierung aus.
Jede Stage benötigt ihr eigenes N=3-plus-Pflichtgate vor ihrem Commit.
Vorbereitete Zähler und Katalogeinträge sind keine bestandenen Verhaltenstests.

Zielstand erst nach eigenem erfolgreichen Apply-Gate: **18.p.R**, **794/918**, danach **18.p.C**.
