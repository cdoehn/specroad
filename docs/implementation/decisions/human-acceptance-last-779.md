# HUMAN-ACCEPTANCE-LAST-779 — technische Arbeit vor menschliche Abnahmen

21. November 2026. Ausdrücklicher Nutzerauftrag: „Ja wir machen erstmal bei 20
weiter? Stelle den Plan um. Menschliche Abnahmen kommen ganz ans Ende wenn
möglich.“ Dies erweitert die Reihenfolgeentscheidung REPOSITORY-REVIEWS-768;
deren damalige Befugnis und Nachweise bleiben historische Originale.

## Befugnis und Wahl

Der Nutzer ändert die Reihenfolge, nicht die erforderliche Qualität oder die
menschliche Autorität. Dies ist ein vollständiger OFF-PLAN-Planungsauftrag,
keine optionale Detailklärung nach SPECROAD-DECISION-1. Ein sachlicher
Dokumentcommit mit Rolle `implementation` und `handoff_kind=patch_ready`
ändert weder Produktzähler noch Klärungs-/Korrekturbudgets. Er startet keine
Automatik und erklärt kein Review, keinen Test und kein Release für bestanden.

Unverändert sofort zu 19.t zurückzukehren würde den neuen Auftrag verfehlen.
Alle M20-Gruppen alphabetisch vorzuziehen würde dagegen echte Abhängigkeiten
verdecken: 20.b bindet sämtliche 46 Szenarien einschließlich der an SR-TC-0720
gebundenen SR-E2E-0045-Abnahme; 20.d enthält R-52 mit echter T.10-Detektion;
20.k verlangt den eingefrorenen realen Sprachkorpus. Diese Gruppen teilweise
als abgeschlossen auszugeben oder ihre Oracles auszudünnen wird verworfen.

Gewählt wird die vollständige Vorziehung der unabhängigen technischen Gruppen.
Die verbindliche aktuelle Reihenfolge steht einmalig im Fortschrittsblock des
[Planeinstiegs](../SpecRoad_Implementierungsplan.md); die konkreten Voraussetzungen
stehen in [M19](../milestones/M19.md) und [M20](../milestones/M20.md). Die normative
Befugnis und Grenzen stehen in Spezifikation 2.5.8. Alte Positionsnummern,
Commit-IDs, exakte Commitnachrichten, Requirements und W/R/C-Abnahmen bleiben
erhalten; eine Positionsnummer ist keine neue Laufreihenfolge.

## Abhängigkeitsprüfung

| Gruppen | Entscheidung und erhaltene Abnahme |
| --- | --- |
| 20.a | Unabhängiger aktueller Abnahmekatalog auf 19.x.C. Fehlende Ergebnisse, insbesondere SR-TC-0720, bleiben offen; keine Vollabnahme aus der Zuordnung. |
| 20.c | R-01 bis R-47 brauchen den vorhandenen Produktstand und den Katalog, nicht den fertigen Gesamtszenariolauf aus 20.b. Vollständige Regression bleibt Pflicht. |
| 20.e–20.j | Schreibschutz, Work-/Cacheparität, Offline-/Sicherheitsprüfung, Python-/Distributionsmatrix und reale Ressourcenmessungen nutzen den vorhandenen Produktstand. Sie ersetzen keine Korpusqualitätsabnahme. Fehlende Plattform-/Hostnachweise bleiben konkrete Blocker des jeweiligen Gates. |
| 20.m | Vollständige technische Herstellung und Prüfung der tatsächlichen Releasekandidaten, einschließlich Zusatzpaketen und gebundenem PatchHarbor-Rundweg. Keine Veröffentlichung, kein Tag, keine Produktfreigabe. Umfang und Ergänzung 20.m bleiben erforderlich. |
| 19.t, 19.y | Später gemeinsamer Abschlussblock: tatsächliche sprachkundige Reviews und Herkunft/Nutzungsfreigabe, Freeze vor Detektion, unveränderter realer Korpusnachweis, danach vollständige Core-/Zusatzmatrix. |
| 20.b, 20.d, 20.k | Vollständige abhängig gewordene Gesamt-/Sprachabnahmen nach dem Korpus und der Analyzerfreigabe; keine Teilgruppe, kein Mock statt realer Library, kein vorweggenommenes Häkchen. |
| 20.l, 20.n | Praktische Bedienungsdurchsicht und abschließende ausdrückliche Freigabeentscheidung zuletzt. Reviewbefugnis, TD-001 und tatsächliche Nachweisbindung bleiben erhalten. |

Damit liegen neun vollständige W/R/C-Gruppen mit 27 Produktcommits vor dem
Reviewblock. Weitere sieben Gruppen mit 21 Commits bleiben im Abschlussblock.
Das ist eine Arbeitsreihenfolge, keine Zusage einer störungsfreien Laufzeit.
Alle 48 noch offenen Produktpositionen bleiben offen; 870/918 bleibt bestehen.

## Abschluss und Aktualität

Menschliche Beiträge dürfen freiwillig früher eingehen, blockieren aber die
vorgezogenen unabhängigen Gruppen nicht. Sie gelten nur für die tatsächlich
geprüften Texte, Kriterien und Versionen. Tests von Review-/Approvalverhalten
mit ausdrücklich synthetischen Testakteuren sind keine Produktfreigaben.

Nach den menschlichen Korpusentscheidungen sind dessen echte technische Tests
zwingend nachgelagert. Deshalb kann die menschliche Korpusprüfung nicht hinter
ihre eigene Adapterabnahme verschoben werden. Der abschließende menschliche
Releaseentscheid bleibt zuletzt. Die bestehende Berechtigung zu optionalen
Detailklärungen ersetzt keinen dieser Nachweise.

Die vorgezogenen Artefakte aus 20.m sind tatsächliche geprüfte Kandidaten,
keine behauptete Veröffentlichung. 20.n muss die Originalbelege gegen den
endgültigen Source-/Spec-/Fixture-/Runtime- und Artefaktstand prüfen. Spätere
Änderungen verlangen die nach dem bestehenden Vertrag betroffenen echten
Neubauten, Regressionen, Messungen und gegebenenfalls erneuten Reviews;
historische Erfolge werden weder umgebunden noch als aktueller Erfolg kopiert.
Ohne diese Aktualitätsprüfung und alle zurückgestellten Gates bleibt die
Releaseentscheidung gesperrt. Produktlücken oder externe Blocker werden
konkret gemeldet, nicht durch diesen Plan aufgehoben.

## Dieser Commit

`HUMAN-ACCEPTANCE-LAST-779 docs(plan): technische Gesamtabnahme vor menschliche Abnahmen ziehen`

Fortgeschrieben werden Spezifikation, Planvoraussetzungen, der README-Hinweis
und aktive Kataloghashbindungen. SR-TC-0720 bleibt offen und ohne ausführbare
Passbehauptung. Code, Tests, stabile Testnummern, Originalmessungen und die
226 unbestätigten Reviewpunkte bleiben unverändert. Das eigene Apply-Gate
prüft bestehende Katalog-/Commitplanverträge plus die fällige N=3-Auswahl;
keine neuen Dokumentations- oder Darstellungstests.
