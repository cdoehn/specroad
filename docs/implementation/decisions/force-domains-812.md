# FORCE-DOMAINS-812 — Fachliche Forceabsicht und vollständige Planaufteilung

24. November 2026. Maßgebliche Quelle ist Result
`e45930c88a61ff485ae20d254032d38d2c7685a6e4054fced32ce129caa73a73`,
Commit `0e053d2543db4f4a7ab6e11ad73e68cbcc722d1e`.

## Ausdrückliche Planentscheidung

Der Nutzer genehmigt 21.e1 und 21.e2 ausdrücklich. Die Untersuchung und
begonnene Implementierung sind kein gescheiterter Apply-Test; die Teilung
wird nicht als nach WORKFLOW-514 belegte Fehlerreparatur ausgegeben.
Fachliche Zielberechnung/Herkunft und eigentümergebundene betriebliche
Publikation haben unterschiedliche Verträge und vollständige Abnahmeoracles.
Die zweite Gruppe behält die gesamte Integration. Keine Scopeverringerung.

| Alter Umfang / Rest | Verbindlicher neuer Träger |
|---|---|
| Authoring und Plan, Proposal, Review, Lifecycle, Readiness | 21.e1.W/R/C |
| Import, Merge, Migration, Baseline, Analyzerpolicy | 21.e1.W/R/C |
| Konkrete fachliche Ziele, stale/immutable Semantik, negative Originalbefunde und passive Leser | 21.e1.W/R/C |
| Work, Bundle, aktive/alte Marker, konkurrierende Locks | 21.e2.W/R/C |
| Pfad-/Sicherheits-/Format-/Ressourcenlimits, physische Fehler, beschädigter Bestand | 21.e2.W/R/C |
| Eigentümerbindung, eigene Attempt-Ablage, Originalerhaltung, fehlende Exklusivität | 21.e2.W/R/C |
| R-86/R-87, SR-REQ-0785/0786/0787, SR-VER-0060 und sämtliche alten Restfälle | Beide Gruppen; vollständige Gesamtintegration in 21.e2.C |

Die sechs Positionen 931–936 ersetzen verlustfrei die drei alten 931–933.
Nachfolgende M21-Positionen verschieben sich um drei, Gesamtumfang 999.
21.f setzt 21.e2.C voraus. Kein abgeschlossener Commit wird wiederholt,
kein Produktzähler allein durch die Teilung erhöht.

## Notwendige normative Detailklärung

X.12 verlangt exakte Absichts-/Requestbindung auch vor nativer ID- und
Zeitallokation. Der geschlossene 1.3.0-Raw-Plan hat kein Feld für diese Absicht.
Nur Zielbytes zu vergleichen verliert die native Eingabe; Audittext oder
Plan-ID umzudeuten wäre ein versteckter Transport. Ein unversioniertes neues
Feld würde bestehende geschlossene Leser inkompatibel verändern.

Gewählt wird der additive 1.4.0-Vertrag in X.12.2 mit vollständiger passiver
Absicht und versionierter Hashprojektion. Die vorhandenen Raw-Operationen,
Writer, native Hashes, Hostprüfung und Receiptpfade werden wiederverwendet.
Alte 1.2.0/1.3.0-Bytes und Hashes bleiben gültig. Keine freie Programmsprache,
kein neuer Ausführungspfad und keine gespeicherte Autorität entstehen.

Befugnis: **delegiert gemäß SPECROAD-DECISION-1**, Vertrag 4, 20 verbleibende
Klärungen. Die ausdrückliche Zustimmung betrifft die Planaufteilung, nicht
eine behauptete persönliche Prüfung dieser Detailwahl. Die Wahl bleibt im
bestätigten Forceumfang, erhält Sicherheits-/Nachweispflichten und ist durch
additive versionierte Leser rücknehmbar. Keine unbekannten externen Fakten
oder menschlichen Produktentscheidungen werden vorausgesetzt.

## Zusätzliche Abnahmen 21.e1

Normal-/Force-Paare prüfen konkrete Byteziele und vollständige negative
Befunde; alle tatsächlich ausführbaren nativen Prüfungen laufen weiter.
Unbestimmbare Ziele bleiben Fehler mit Diagnose, keine erratenen Reparaturen.
Native Wiederholung bestätigt den vollständigen ursprünglichen Beleg vor
neuer ID-/Zeitallokation. Andere Absicht, Actor, Request-/Forcebindung, explizite Ausführungs- oder
Backup-/Berichtsbindung oder Befehlkennung übernimmt keinen Erfolg.
Leere konkrete Ziele erhalten ihren eigenen Beleg ohne erfundene Dateieffekte. Gespeicherte Pläne werden nicht
neu kompiliert. Dry-run verändert keine Datei; echte Hostverweigerung bleibt
Verweigerung. Negative/unknown Berichte werden weder zu passed umgedeutet
noch als Review/Verification/Readiness benutzt. Die Leser erhalten Herkunft
und Originalbindungen; abweichende/unvollständige Receipts bleiben ungültig.

W, R und C bleiben getrennte echte Zwischenstände mit je eigener
N=3-plus-Pflichtauswahl vor dem Commit. Dev führt keine Verhaltenstests aus.
Klärung, Vorbereitung und erfolgreiche Apply-Abnahme bleiben unterscheidbar.
Neue CPU-/RSS-Zwischenmessungen bleiben aufgeschoben; die finale Abnahme
20.n mit tatsächlichen Originalbelegen bleibt offen.
