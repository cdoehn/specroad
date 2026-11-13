# Bundle 675 — Laufprofil begrenzen, vollständigen 18.k-Rest fortführen

13. November 2026. Quelle ist das native Fehler-Result 674 mit SHA-256
`b9739d2c95a9194f70f0a2093664894030607ad4e23e71ce6822e87db576395d`.
PROPOSAL-APPLY-674 ist nach 11262 bestandenen Tests als
`8af77c07279e1784a11de2809834723296940dc7` committed. Anschließend wurde
18.k.W vollständig ausgebracht und erfolgreich gesammelt (27190 Tests),
aber vor Beginn der Verhaltenstests mit `Unsafe or oversized host input`
abgebrochen. Kein Produktcommit entstand; die ausgebrachte W-Checkliste ist
kein bestätigter Fortschritt. R und C wurden noch nicht ausgebracht.

## Belegte Ursache und begrenzte Korrektur

Das erhaltene lokale W-Laufprofil hat 16.087.459 Bytes, die unveränderte
Leseschranke erlaubt 16.000.000. Es enthält 60350 Hostschätzungen und 27169
Basiswerte für die gesamte Historie, obwohl nur 11384 Tests ausgewählt sind.
Die erfolgreiche vorherige Stage lag mit 15.955.067 Bytes noch unter der
Grenze. Aus dem vorhandenen Profil werden für denselben Lauf lediglich
27311 Hostschätzungen und 11363 Basiswerte benötigt; die entsprechende
JSON-Projektion hat 8.019.221 Bytes. Das ist eine Auswertung vorhandener
Daten, keine neue Testausführung oder Laufzeitmessung.

`prepare_pool` übernimmt nur Schätzungen für ausgewählte Testidentitäten und
tatsächlich beteiligte Hostkennungen sowie Basiswerte ausgewählter Tests.
Alle dafür verfügbaren Werte bleiben exakt erhalten: aktuelle Hostmessungen
haben weiter Vorrang; fehlende oder ungültige Messungen bleiben fehlend,
Nullzeiten bleiben gültig. Kein Host oder Test wird umbenannt, ausgelassen,
zusätzlich gestartet oder wiederholt. Auswahlbindung, Quellen-/Umgebungs-
prüfung, Workergrenzen, Sicherheitslimit und Reader bleiben unverändert.
SQLite, Rohmessungen, Auswahl-Snapshot und lokale Konfigurationen werden
nicht umgeschrieben. Die Korrektur braucht keine normative Detailklärung.

Vier neue Regressionen werden ausschließlich für Apply vorbereitet: drei
unabhängige Überschreitungen durch andere Tests, nicht beteiligte Hosts oder
nicht ausgewählte Basiswerte durchlaufen echte Profilvorbereitung, sichere
JSON-Lektüre, Snapshot- und Quellbindung. Ein Schedulervergleich prüft dieselben
Hostprognosen, Zuteilungen, vollständigen Testidentitäten und Fertigstellung
mit und ohne irrelevante Historieneinträge. Externe Hostprobes sind synthetisch;
der Profil-/Snapshot-/Schedulerpfad ist echt. Bestehende Host-/History-/RPC-/
Scheduler- und native Workerintegrationen bleiben ungefilterte Pflichtauswahl.

## Erhaltener Rest und Nachweisgrenze

18.k.W, 18.k.R und 18.k.C behalten IDs, Rollen, Nachrichten und vollständige
Abnahmen. Der erste Commit umfasst auch sämtliche uncommitteten W-Dateien.
Jede Stage erhält ein eigenes N=3-plus-Pflichtauswahl-Gate vor dem Commit;
R/C werden erst nach dem jeweiligen vorherigen Commit installiert. Der
bereits erfolgreiche Klärungscommit wird nicht wiederholt oder verändert.
Spezifikation, Entscheidung, Planabnahmen und Budgets bleiben unverändert.
Alle im Result bereits zugeteilten Testnummern bleiben erhalten. Neue
Korrekturtests werden hinten angefügt; die noch nie ausgebrachten R-Tests
folgen danach, ohne bereits zugeteilte Nummern zu verschieben.

Historische Berichte bleiben bytegleich, auch der ursprüngliche
Vorbereitungsbericht von Bundle 674. Dieser Bericht ersetzt dessen offene
Ergebnisannahme durch den beobachteten Abbruch und den weiterhin vollständigen
Rest. Vorbereitete Zähler und Checklisten gelten erst nach dem jeweiligen
Apply-Gate. Dev führt nur Syntax, Collection, Katalog-, Stage- und native
Paketprüfungen aus; keine Verhaltenstests, Fixtures oder Test-Unterprozesse.
Nach 18.k.C bleibt 18.l.W die nächste eigenständige Produktposition.

Vorbereiteter Zustand: `18.k.W`.
