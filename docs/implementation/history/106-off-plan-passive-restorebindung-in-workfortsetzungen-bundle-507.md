# OFF-PLAN – Passive Restorebindung in Workfortsetzungen (Bundle 507)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Passive Restorebindung in Workfortsetzungen (Bundle 507)

Revision 29 konkretisiert **RESTORE-WORK-BINDING** in Spezifikation
**0.2.34 / 10.7.7**, mit Verweisen in 11.12 und P.3. Autorität:
**delegiert gemäß SPECROAD-DECISION-1**; keine behauptete persönliche
Einzelfreigabe. Produktstand **649/900**, zuletzt **15.l.W**, nächstens
**15.l.R**; R/C und sämtliche noch offenen Produktabnahmen bleiben offen.

- [x] **RESTORE-WORK-BINDING:** Passive Workbindung und native Restorefortsetzung
  präzisieren. Commit: `docs(spec): Restorebindung in Workfortsetzungen präzisieren`.

**Maßgebliche Basis und belegter Vorgänger.** Das vollständig geprüfte Result
`specroad-apply_Result_052852_1027_29fbb0.zip` hat SHA-256
`70a401cea33d4f72bb5a77521af8efdeca87302466a9b6e619abbfc8b83d0cdf`.
Repository `a33ed6cf-0a97-4b73-b11a-d4239e7a2145`, Commit
`ab82ac50c1035ecc3fe1597e8b56187e94a249c6`, Fingerprint
`7c9d2a24e397e0e5`, Algorithmus `patchharbor-state-v1`.
Root-Anleitung, Kontext, Umgebung, Manifest, Run-/Ausführungslogs sowie
alle **2.312** Snapshotdateien einschließlich Blob-IDs und Modi wurden
geprüft. Der aktuelle Apply-Stand ist sauber und entspricht dem Snapshot.
Der echte Korrekturabschluss **15.l.R-FIX2**, Bundle **506**, Paket-SHA-256
`f328f651734c04989ddf9506fbb6825d0845cf173cf018abc919430d42f85d48`,
ist durch passenden Abschlusscommit und Payloadvergleich sowie
**7.345/7.345** bestandene Apply-Tests, **Sequenz 212 / Gruppe 2**,
vier parallele Worker und **2974.98 s** belegt. Die vollständige Auswahl,
dauerhaften Testnummern und Einzeloutcomes wurden abgeglichen.

§2.4 enthält SPECROAD-DECISION-1 und die ausdrückliche Vertrag-3-Erlaubnis.
Der aktuelle Auftrag ist gültig: `version=3`, `clarification_limit=3`,
`clarifications_remaining=3`, `clarification_allowed=true`. Bundle 506
war ein als `patch_ready` übergebener echter technischer Fix und ist sauber
abgeschlossen. Dieser reine Dokumentstand wird als `spec_clarification`
übergeben; nur Control verbucht den Platz bei Übernahme des Folge-Results.
Er erneuert kein Budget, ändert keine alten Aufträge, Antworten, Blockaden,
externen Konfigurationen oder Laufzeitdaten und startet keine Dienste.

**Konkrete Lücke und geprüfte Grundlagen.** Der offene Schritt 15.l.R verlangt
Einzellauf-/Workparität. 10.7.3 verbietet für beschädigte Ausgangsbytes eine
erfundene Modellwurzel und unterscheidet ursprünglichen Auftrag von aktuellem
Recoveryakteur. P.3 beschreibt dagegen bisher nur die ursprüngliche normative
Actor-/Operations-/Change-Plan-Bindung; 11.12/P.3/P.7 erlauben allgemeine
Rootlokalisierung, während 10.7.2/10.7.6 ausdrücklich keine Umbindung der im
Restoreplan gespeicherten Projekt-/Herkunftsroots erlauben. Ohne konkrete
Workvariante könnten dieselben Felder verschiedene Hashdomänen, aktuelle
Berechtigung oder sogar ein scheinbar gültiges Ausgangsmodell bezeichnen.
Auch ein äußerer alter Checkpoint darf nach tatsächlichem Restorebeginn
nicht die nachgewiesene Journalwahrheit verdrängen.

Geprüft wurden 2.1/2.4, 10.7.1–10.7.6, 11.6/11.12 und N/O/P,
SR-REQ-0258/0461/0462/0511, R-44/R-47 und die offenen 15.l.R-Abnahmen.
Die nativen Workmodule `manifest.py`, `_request_binding.py`,
`_normative_binding.py`, `resume_checks.py` und `publication.py` unterstützen
den normalen `change.apply`-Plan beziehungsweise Read-only-Aufträge; der
normative Wiederanlauf verlangt ein gültiges `TargetModel` und dessen Basis.
Die Restoremodule `values.py`, `_execution_binding.py`,
`_journal_selection.py`, `_execution_resume.py`, `execution.py` und die
internen CLI-Adapter verwenden bereits getrennte Originalplan-/Inventur-/
Auswahlbindungen, Native-Locks und aktuelle Recoveryautorisierung. Die
Work-Checkpoint-/Objektmechanik ist vorhanden. Ein veröffentlichter
Restore-Work-Bindungstyp ist im maßgeblichen Snapshot nicht implementiert.

**Alternativen und Entscheidung.**

1. Restore als gewöhnlichen `change.apply`-Workauftrag behandeln, Inventur-
   oder Zielhash als Basis/Operationshash einsetzen: würde die Hashdomänen
   verwechseln und den beschädigten Zustand fälschlich als Modell voraussetzen.
2. Nur CLI-Text, absolute Dateipfade oder frühere Autorisierungsentscheidungen
   speichern: bewahrt keine vollständigen passiven Originalbytes und könnte
   spätere Writes oder Rootwechsel ohne aktuelle Grenzen ermöglichen.
3. Eigenes Restore-Workpaket und zweite Recoveryengine einführen: unnötige
   neue Formate/Vertrauensgrenzen; konkurrierender Checkpoint könnte die
   bereits verbindlichen lokalen Journal-/Sicherungsnachweise verdrängen.
4. **Gewählt:** eine geschlossene, versionierte `plan_binding`-Variante im
   vorhandenen Workmanifest, Originalplan-/Auswahlbytes im bestehenden
   content-addressierten Objektbestand und `null` für nicht existierende
   Ausgangsmodell-/Change-Operationshashes. Die vorhandene native Restoreengine
   entscheidet Wiederanlauf und Abschluss; aktuelle Berechtigung bleibt getrennt.

**Abgleich mit allen Grenzen aus 2.4.1.** (1) Es ist eine konkrete passive
Feld- und Fortsetzungszuordnung im schon beauftragten 15.l.R, kein neuer
Command, Authprovider oder Architekturwechsel. (2) Sie erfüllt die Work-
Integrität und die Restore-/Crashverträge gleichzeitig: Originalinventur
statt falscher Modellbasis, aktive Journalwahrheit statt neuer Publikation.
(3) Bestehende Plan-, Auswahl-, Change-Plan- und Workbytes werden nicht
umgeschrieben; ein unbekannter Bindungstyp bleibt ausdrücklich unzulässig.
Keine CLI-Option verleiht neue Rechte. Herkunfts-/Owner-/Risikogates,
menschliche Reviews und historische Providerpflichten bleiben erhalten.
(4) Die neue versionierte Detailregel kann explizit fortgeschrieben werden;
alte Fassungen, Results, Evidence und Bestandsdateien bleiben erhalten.
(5) Die Zuordnung vorhandener Bytes und Verträge verlangt keine externen
Geheimnisse, erfundenen Hostgrants oder menschlichen Risikoentscheidungen.
Die tatsächlich verwendbare vertrauenswürdige CLI-Anbindung und die noch
fehlende Produktimplementierung werden damit ausdrücklich nicht behauptet.

**Zusätzliche offene Verhaltensabnahmen von 15.l.R.**

- Beide Restoremodi behalten ihre fachlichen Parameter über kleine und
  große Workschritte. Ein Planungscheckpoint mit beschädigter Konfiguration
  erzeugt weder fiktive Modellbasis noch Actor-/Writefreigabe; Einzellauf
  und Work liefern denselben vollständig qualifizierten externen Plan.
- Ausführungswork erhält Originalplanbytes, inneren/äußeren Hash, Auswahl,
  Inventur, Projekt-ID, ursprünglichen Actor und Request exakt. Human ohne
  optionale Request-ID sowie AI/CI mit verpflichtender ID folgen 10.7.3.
  Leere Auswahl bleibt leer; fremde alte Journale werden nicht ergänzt.
- Fehlende/abweichende Objekte, falsche innere Hashdomäne, Auswahl-/Actor-/
  Requestkonflikt, unbekannter Bindungstyp und fremde Rootzuordnung werden
  vor Projektwrite in der vorgeschriebenen Fehlerklasse abgewiesen. Alte
  Change-Plan-/Read-only-Workcheckpoints bleiben unverändert verwendbar.
- Work-/Plantransport kann mit identischen Originalbytes verlagert werden;
  gebundene Projekt-/Herkunftsroots bleiben unverändert. Ein Workexport ist
  kein Nachweis einer aktiven Transaktionskopie. Verlust notwendiger lokaler
  Recoverybytes bleibt konkret blockierend statt aus Workhashes rekonstruiert.
- Fehlende oder ablehnende aktuelle Recoveryautorität, gespeicherte Zustimmung,
  lebender Owner und unbelegte Übernahme erlauben keinen Write. Ein wirklich
  autorisierter Wiederanlauf trennt aktuellen Recoveryakteur und ursprünglichen
  Workakteur im Audit, ohne den ursprünglichen Auftrag zu erweitern.
- Tatsächlicher Prozessabbruch mit älterem äußerem Workcheckpoint führt
  ausschließlich zur passenden nativen Recovery. Vollziel plus fehlende
  externe Quelle wird ohne erneute Publikation abgeschlossen; Teilziel wird
  bytegetreu zurückgerollt. Fehlende Before Images, fremde Änderungen und
  mehrdeutige Bindungen erhalten alle Sperren und Nachweise. Ein Rollback
  darf weder als Restoreerfolg noch als Anlass für neue Planung gelten.
- Verlorener Workabschluss nach dauerhaftem Restoreaudit wird ohne zweite
  Zielpublikation vollständig nachgetragen; ein abgeschlossener Workretry
  liefert seinen gespeicherten Befund, keinen neuen Aktualitätsnachweis.
  Cancel/Export umgehen keine laufende Restoretransaktion. Verbrauch und
  Generationen bleiben Betriebsdaten, Fachresultat und Fehlerklassen stimmen
  mit dem Einzellauf überein. Echte große, geteilte Verarbeitung bleibt Pflicht.

**Umfang und Übergabe.** Nur Spezifikation, Plan und notwendige aktive
Spezifikationshashbindungen ändern sich. Produktcode, Tests, Testnummern,
Fixtures, Runner, Workflows und historische Nachweise bleiben bytegleich.
Keine Dokumentationstests, kein zusätzlicher Volltest, keine künstliche
W/R/C-Folge. SR-TC-0461/0462 bleiben `partial`; die vollständige CLI-/Work-
Integration, I/O-/Crashmatrix und Schutz-/Lifecycle-/Spezialistenprovider
bleiben offene Abnahmen. Der Entrypoint prüft genau die fällige
**Sequenz 213 / Gruppe 0 von 3** parallel vor genau einem OFF-PLAN-Commit.
Erst nach erfolgreichem Gate werden dieser Klärungsmarker und Bundle-Nummer
**507** gesetzt. Produktzähler **649/900** und reguläre Checkboxen bleiben
unverändert. Apply und Commit sind bei Übergabe ausstehend. Nach nativer
ZIP-Prüfung und atomarer Veröffentlichung endet dieser N-Auftrag sofort.


**Beobachtete gezielte Dev-Prüfung.** Die Dokument- und Katalogfassung
besteht **54/54** bestehende Verhaltenstests aus `tests/test_catalog_check.py`
und `tests/test_catalog_check_right.py` in **6.66 s**, mit **vier
parallelen Workern**, CPython **3.14.4**, Exit **0** und ausschließlich
`passed`-Einzeloutcomes. Ausgeführt wurde `tools/run_selected_tests.py
--workers 4 --expected-tests 54` mit den beiden genannten vollständigen
Dateien in einem frischen ignorierten Berichtsroot. Geprüft werden die von
der Spezifikationshashbindung betroffenen maschinenlesbaren Katalog- und
Auswahlverträge; keine Dokumentation, Darstellung oder externe Control-Ausführung.

Die vollständige Collection-/Katalogprüfung bestätigt **22.033** aktive
Tests, **0** Katalogfehler, Exit **0** und **0** ausgeführte Testkörper.
Die **22.037** dauerhaft reservierten Nummern einschließlich vier historisch
entfernter Identitäten bleiben bytegleich. Produktcode, Testdateien,
Fixtures, Oracles, Runner, Workflows und historische Evidence ändern sich
nicht. Die **743** aktiven Katalogdateien ändern ausschließlich
`specification_sha256`; einschließlich Spezifikation und Plan sind es
**745** geänderte Bestandsdateien, keine neuen Produktdateien oder Löschungen.

Gebundener Entwicklungsquellhash:
`d0597b7f934565d86645094563a5cb0a700e07038dea98079de47e5d99878cde`;
Katalogvertrag-SHA-256:
`c493e97e8bec2da3c04be675920109c108cbdf577e8ba681f9b74f7e77a644db`;
Auswahlbericht-SHA-256:
`fb23c55ab9936ba7dc4f6a8b40063215968bdf59643dfd24db761ee796b8928a`;
Einzeloutcomes-SHA-256:
`d0aa0e6393a9cf9bc241e7975134b9f28c85aeb728ef68a28ea7d538a5929177`.
Dies ist ausdrücklich eine Teilprüfung mit `full_suite_passed=null`;
kein vollständiger oder serieller Testlauf und kein Releasebeleg.

Ein früherer gezielter Kataloglauf vor der abschließenden Versionspflege
bestand ebenfalls 54/54 Tests in 6.62 s. Nach der vollständigen Nachführung
von Dokumentversion, Änderungsverlauf und aktiven Hashbindungen wurde die
obige endgültige Fassung erneut geprüft; allein deren Quellhash bindet
die Übergabe. Es wurde kein zusätzlicher Volltest ausgeführt.

Der bestätigte vorherige Apply-Nachweis für die echte technische
Korrektur 15.l.R-FIX2 (Bundle 506) ist davon getrennt:
Auswahlbindungs-SHA-256 `150c552a85ca09c25303e0b7b4201fee57c7b40f8264b3a20b9eeda7db6c43ba`,
Bericht-SHA-256 `f6144aa496c4d21fb1e452aef730c4531448a9aefdc6ba809e2acc75333f6359` und
Einzeloutcomes-SHA-256 `c39a3972e3489fade075e5a4bd81229ec2e89dcb3383d4ca97cf5f0df7abf4d2`.
Die vorgesehene neue Apply-Gruppe und der OFF-PLAN-Commit sind bei dieser
Übergabe noch nicht ausgeführt. Native ZIP-Prüfung und atomare Veröffentlichung
beenden den Einzelauftrag; 15.l.R bleibt offen.
