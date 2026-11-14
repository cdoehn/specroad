# Bundle 700 — gemeinsame native Projektqualifikation (18.s)

Datum: 14. November 2026. Technische Basis ist das nativ geprüfte saubere Result
`specroad-apply_Result_190908_1114_9b7bfc.zip`, SHA-256
`c91747c0235b82d29057235127e186a5d6022878c9d6d55ce2db0cb4abef6756`,
Commit `ba630ba34c5b15d0fcdca3024ee5c86bf8ba5703`. Es ist der aktuelle
Checkpoint nach dem vollständig erfolgreichen OFF-PLAN-Bundle 699. Kein
offener Korrekturpräfix und keine Wiederholung der SPECULATE-Commits.

## Vollständige Folge und fachliche Grenze

18.s.W/R/C setzt die bereits bestätigte Trennung aus 10.7.3 und
RECOVERY-REMOVAL-006 um. Es gibt keine neue normative Detailentscheidung.
Jede Stage wird erst nach erfolgreichem eigenem N=3-plus-Pflichtauswahl-Gate
committed; erst dann wird die nächste ausgebracht. Die Checklisten und
Fortschrittswerte sind ausschließlich Zielwerte der jeweiligen Stage,
kein vorweggenommener Apply-Erfolg. Der folgende vollständige Schritt 18.t
führt den neuen Schreibmarker-/Abschlussvertrag ein; dieses Bundle liefert
seine gemeinsame lesende Qualifikationsgrundlage und ändert keinen Writer.

| Stage | Vollständiger Umfang |
| --- | --- |
| 18.s.W | Gemeinsame Services, Fehler, Pfade, Projekt-/Spezialprüfungen, Original-Receiptlinien, Archivclosure und historische Evidence in `qualification/`; alle normalen Proposal-Aufrufer umgestellt. Restore verwendet exakt dieselben Funktionen über Übergangsimporte. |
| 18.s.R | Gemeinsames sicheres Inventar; übrige Merge-, Migration-, CLI- und normale Work-Verbraucher umgestellt. Gemeinsame Work-Buildkennung von Restore getrennt, Restore-Import nur noch im gewählten Restore-Zweig. |
| 18.s.C | Fachlich benannte `QualificationServices`/`QualificationError`, dieselben exakten Typen über alte Aliasnamen; bereinigte Adapter. Identische W/R-Testbytes und unveränderte Ergebnisse, Gatekennungen, Fehlercodes und Seiteneffekte. |

## Importinventar und Verantwortungsgrenzen

Die statische Inventur umfasst direkte, funktionslokale und relative Imports,
Reexports und dynamische Verweise; die unabhängige Apply-Abnahme qualifiziert
ein echtes natives Projekt bei nicht verfügbaren Restore-Adaptern.

| Erhaltene Fachaufgabe | Maßgebliches Modul | Verbraucher |
| --- | --- | --- |
| Explizite Hosteingaben und strenge native Typen | `qualification/services.py` | Proposal Check/Review/Apply, Merge-Publikation, CLI InvocationContext; alte `recovery/services.py` ist Aliasadapter |
| Vollständiger Projektbefund | `qualification/project.py` | Proposal-History und Check-/Review-/Decision-/Apply-Prüfungen; Merge Target/PublicationTarget; Restore über Reexport |
| Reviews, Quellen, Task-Done, Konfiguration, Proposal-Originale | `qualification/specialists.py` | gemeinsame Projektprüfung und Merge-Publikation |
| Archive, Formate, abgeschlossene Receipts, historische Evidence | `qualification/archives.py`, `formats.py`, `receipts.py`, `terminal_receipts.py`, `evidence.py` | gemeinsame Validierung, vorhandene Restore-Leser über Adapter; keine Restore-Rekonstruktion im gemeinsamen Paket |
| Sicheres Inventar und Pfade | `qualification/inventory.py`, `paths.py` | Migration CLI/Eingänge, Projektauswahl, Work-Leser; Restore-Inventar bleibt Reexport |
| Gemeinsame Fehler und ausschließlich bytegebundene Wiederverwendung | `qualification/errors.py`, `owned.py` | CLI-Transport/Work, Work-Manifest/Fehler, Merge RecordedSource/Publication; verbleibende Restore-Aufrufer teilen dieselben Typen und denselben ContextVar |
| Aktuelle Work-Buildbindung | `work/build.py` | normales Work-Lesen und Transport, CLI Work; Restore-Execution importiert denselben Helfer |

`recovery/_sources.py` behält nur die Restore-spezifische Rekonstruktion;
`baseline_objects` stammt aus der gemeinsamen Archivprüfung. `RestorePlan`,
Restore-Owner/Execution/Work-Adapter und öffentliche Restore-Kommandos bleiben
bis 18.w erhalten. Die bestehenden `changes`-Journal-/Receiptleser bleiben
bis zum geplanten Writer-/Formatwechsel maßgeblich. Kein Importinventar
behauptet hier bereits deren Entfernung oder den Abschluss von 18.t–18.x.

## Abnahmen und Nachweisgrenze

Neue kleine native Verhaltenstests prüfen vollständige gültige/ungültige
Projektbefunde, nicht fälschbare Serviceeingaben, erneute Quellenbeobachtung
trotz Bytewiederverwendung sowie applied-Proposals mit und ohne tatsächliche
Original-Publikationsbelege. R ergänzt Rootaustausch, portable Namenskonflikte,
Hard-/Symlinks, unbekannte deklarierte Formate und native Qualifikation ohne
Restore-Adapter. Keine Erfolgsstubs, gelöschten Assertions oder Ersatzbelege.

Die Pflichtauswahl enthält alle neuen/geänderten Testdateien und vollständige
betroffene Proposal-/Restore-/Merge-/Migration-/Work-/CLI-Regressionen,
einschließlich aktueller Reviews, Task-Done, Archiv-/Legacyclosure und
historischer Evidence. Große native Referenzfälle bleiben unverändert.
Neue Nummern werden angehängt; alte Identitäten und Rotationsanker bleiben.

SR-TC-0462 bindet ausschließlich den jetzt implementierten gemeinsamen
Qualifikationsanteil als `partial`. Git-Wiederanlauf, neue Receiptformate und
die vollständige 18.x-Abnahme bleiben offen. Andere offene Requirements
werden nicht allein durch einen Refactor als umgesetzt ausgegeben.

Dev-Nachweise: Syntax, statische Import-/Funktionsinventur, reine vollständige
Collection und native Paket-/Bindungsprüfung. Keine Testkörper oder Fixtures
in Dev. Verhaltens- und Plattformnachweise entstehen erst im echten Apply;
keine Release-/Nutzungsfreigabe, keine Budget- oder Betriebsänderung.
