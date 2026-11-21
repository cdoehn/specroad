# APPROVAL-BINDING-783 — vorhandenes Approval-Gate an den Writer binden

21. November 2026. Autorität: **delegiert gemäß SPECROAD-DECISION-1**,
optional zugelassen durch den gebundenen Control-Vertrag 4. Keine behauptete
persönliche Fachfreigabe. Quelle: natives erfolgreiches Result SHA-256
`6247e49f8afeccd1acf9c331b39748e029de57b0a1ea8df8697795917038105c`,
Commit `7708b46e6c2587cfaaaa6d59b9377d6e1c012a5a`; 20.a.C bestätigt.

## Lücke und Entscheidung

20.c verlangt alle Ergebnisse von R-01 bis R-47. R-36 verlangt die echte Folge
proposed/5, in_review/6, approved/7. Der allgemeine Lifecyclefold verweigert
bisher jeden Approval-Übergang. Der vorhandene Approval-Kern prüft bereits
menschliche Identität/Aktualität, acht fachliche Kriterien und sieben explizite
Dienstbeobachtungen, führt aber keinen Write aus. Es fehlt die eindeutige
Bindung dieser Beobachtung an den gespeicherten Übergangsplan.

Dauerhafte Totalverweigerung erfüllt R-36 nicht. Ein `approved`-Flag oder ein
freier Callback würde vorhandene Reviewpflichten umgehen und wird verworfen.
Ein neuer persistierter Review-Artefakttyp würde die 28er-Matrix und bestehende
Vertrauensgrenzen ändern. Gewählt wird die kleinste ergänzende Referenz aus
Version, Kontext- und Reviewhash in der vorhandenen Transition-Metadatenhülle.
Der native Gateadapter verwendet die vorhandenen expliziten Hostdienste erneut
an jeder Publikationsgrenze; keine dynamische Registrierung aus Plan-JSON.

Die normative Regel steht ausschließlich in Spezifikation **9.6.4**. Sie erhält
9.6.1/9.6.3, 11.13, R-35 bis R-39 und SR-REQ-0043, 0070, 0283, 0499, 0650,
0674. Vorhandene Plans, historische Reviewbytes und Receipts werden nicht
migriert oder umgeschrieben. Fehlende Referenzen behalten die sichere Sperre.
Das technische Gate schließt keine menschliche Produktabnahme. Es hängt nicht
von einem erfundenen echten Reviewer ab: Verhaltenstests benutzen ausdrücklich
synthetische Daten und Dienste; echte Verwendung benötigt reale Hostnachweise.

Die Ergänzung ist auf den bereits geplanten R-36-Vertrag begrenzt. Sie ändert
weder Architektur/Vertrauen noch Datenverlust-, Sicherheits-, Release- oder
Kompatibilitätsregeln. Rücknahme der neuen Writerintegration ist möglich, ohne
alte Daten zu löschen. Bereits erzeugte Pläne/Receipts bleiben historische
Originale; es wird keine automatische neue Freigabe abgeleitet.

## Abnahmen und Reihenfolge

Der Klärungsstand ändert nur Spec, Planabnahmen und aktive Kataloghashbindungen,
keinen Produktzähler. Danach folgen echte 20.c.W/R/C-Zielstände. W verbindet
native positive R-36-Publikation, aktuelle Pflichtrelationen und die vollständige
R-01..R-47-Auswahl. R prüft fehlende/falsche Kontext-/Reviewbindung, nichtmenschliche
Akteure, fehlende/negative/wechselnde Dienste, gespeicherte Pläne, Fremdgates und
idempotente Receipts sowie reale CLI-/Datei-/Prozessgrenzen. C bereinigt nur die
Struktur bei bytegleichen W/R-Testoracles. Weitere vollständige geplante Gruppen
dürfen folgen; keine neue Klärung im Anhang. Jede Stage erhält ein eigenes Gate.

Dev führt keine Tests/Fixtures aus. Reine Collection und native Paketvalidierung
sind kein Verhaltenserfolg. Umsetzung und Abnahme sind in diesem Klärungsstand
noch offen; SpecRoad-Produkt-/Releasefreigabe bleibt offen.
