# OFF-PLAN – Verwaister äußerer Restore-Work-Owner (Bundle 510)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Verwaister äußerer Restore-Work-Owner (Bundle 510)

Revision 30 konkretisiert **RESTORE-WORK-OWNER-HANDOFF** in Spezifikation
**0.2.35 / 10.7.8**, mit Verweisen in 11.12 und P.2. Autorität:
**delegiert gemäß SPECROAD-DECISION-1**; keine behauptete persönliche
Einzelfreigabe oder Risikoakzeptanz. Produktstand **649/900**, zuletzt
**15.l.W**, nächstens **15.l.R**. R/C und alle übrigen offenen Abnahmen
bleiben offen.

- [x] **RESTORE-WORK-OWNER-HANDOFF:** Explizite, nativ belegte Übernahme des
  äußeren Restore-Work-Owners spezifizieren. Commit:
  `docs(spec): Verwaiste äußere Restore-Work-Owner präzisieren`.

**Maßgebliche Basis und belegter Vorgänger.** Das vollständig geprüfte Result
`specroad-apply_Result_111547_1027_6cbf1b.zip` hat SHA-256
`a5a4afcaf7c46624f694b9c8b707f2ede299bbbb46c6eb083401ddf735ce147b`.
Repository `a33ed6cf-0a97-4b73-b11a-d4239e7a2145`, Abschlusscommit
`d2267f4c82a7aa3f8ba1e2caf1799a5e6ae0b892`, Fingerprint
`7c9d2a24e397e0e5`, Algorithmus `patchharbor-state-v1`.
Root-Anleitung, Kontext, Umgebung, Manifest, Run-/Ausführungslogs und alle
**2.317** Snapshotdateien einschließlich Blob-IDs und Git-Modi wurden
geprüft. Der registrierte Apply-Stand ist sauber und entspricht dem Snapshot.
Bundle **509**, Paket-SHA-256
`a32fb736362cd8368b741b294e1a779dc237eabf754fb31da2477a9a7426d980`,
ist als echter 15.l.R-Zwischenstand durch passenden Abschlusscommit,
Payloadvergleich und **7.372/7.372** bestandene Apply-Tests nachgewiesen:
**Sequenz 215 / Gruppe 2**, vier parallele Worker, **3728.13 s**.
Die vollständige Collection umfasst **22.114** aktive Tests; permanente
Testnummern, Auswahlbindung und sämtliche Einzeloutcomes wurden abgeglichen.
Dies ist ein Teiltestnachweis, kein Vollsuite- oder Releasebeleg.

§2.4 enthält SPECROAD-DECISION-1 und die ausdrückliche Vertrag-3-Erlaubnis.
Der aktuelle Vertrag ist gültig: `version=3`, `clarification_limit=3`,
`clarifications_remaining=3`, `clarification_allowed=true`. Die Übergabe
wird als `spec_clarification` klassifiziert. Nur Control verbucht den
verbrauchten Platz bei Übernahme des Folge-Results. Dieses Bundle erneuert
kein Budget und ändert keine alten Aufträge, Antworten, Blockaden,
Konfigurationen oder Laufzeitdaten.

**Konkrete Lücke und geprüfte Quellen.** 10.7.7 verlangt die Wiederaufnahme
der nativen Restoretransaktion und anschließend eine vollständige äußere
Ergebnislieferung; P.2 verlangt eine erneute Work-/Ownerprüfung und verbietet
eine PID-/Hostname-basierte Übernahme. Ein konkreter Übernahmeauftrag und
dessen Belege für den erhaltenen äußeren Work-Owner fehlen jedoch. Die
Projektownerregel 10.7.5 gilt für einen anderen Lock und verleiht keine
Berechtigung zum Verändern externer Workdaten.

Im maßgeblichen Snapshot verwendet `work/restore_execution.py` nur
`inspect_checkpoint()` und bestätigt noch keinen Workfortschritt.
`work/checkpoints.py` veröffentlicht über `for_checkpoint()` beziehungsweise
`_update()`. Dessen `work/_root_lock.py` erhält Owner bei Prozessabbruch
und verweigert beim nächsten schreibenden Eintritt jeden vorhandenen
`work-lock.json`; reine Inspektion kann die Bytes unter dem Kernelmutex
erhalten lesen. Ein zusätzlicher dauerhafter Workfortschritt würde daher
einen bisher nicht festgelegten äußeren Wiederanlauf benötigen. Der vorhandene
`changes/_lock_process.py` bietet native Boot-/PID-Namespace- und
Prozessstartbeobachtung; unprüfbare Zustände bleiben ausdrücklich unbekannt.
Keiner dieser Befunde belegt eine bereits implementierte sichere Übernahme.

Geprüfte fachliche Grundlagen: 2.1/2.4, 10.7.3/10.7.5–10.7.7, 11.12,
P.1–P.3/P.6–P.9, SR-REQ-0258/0461/0462/0511 und die offenen 15.l.R-Abnahmen.
Außerdem wurden die vorhandenen Workmanifest-, Checkpoint-, Abschluss- und
Ergebnislieferadapter sowie native Restoreausführung und Recovery geprüft.
Die normale Read-only-Abschlussroute ersetzt den Restoreabschluss nicht.

**Alternativen und Entscheidung.**

1. Einen freien Kernelmutex, Lockalter oder PID allein als Erlaubnis zum
   Löschen des Work-Owners verwenden: widerspricht der bestehenden Ownergrenze
   und schützt nicht gegen PID-Wiederverwendung oder unbekannte Umgebungen.
2. Die Projektoptionen `--force`/`--accept-remote-risk` auch auf den äußeren
   Work-Lock anwenden: würde eine Zustimmung für einen anderen Gegenstand
   wiederverwenden und die getrennten Vertrauensgrenzen vermischen.
3. Den Owner dauerhaft sperren und stets manuelles Löschen oder Kopieren
   des Workverzeichnisses verlangen: liefert keinen spezifizierten sicheren
   Wiederanlauf, verliert möglicherweise Betriebsbelege und ersetzt nicht
   die noch notwendige lokale native Restore-Recovery. Der schon bestehende
   verifizierte Pakettransport bleibt möglich, ist aber kein Ersatz für
   die Wiederaufnahme im unveränderten Work-Root.
4. **Gewählt:** ausdrückliches aktuelles Paar aus exaktem Work-Ownerhash und
   Begründung; vollständige unabhängige Work-/Root-/Checkpointprüfung und
   native Bestätigung eines beendeten lokalen ursprünglichen Owners unter
   durchgehend gehaltenem Kernelmutex. Originalbytes und Ownerwechsel werden
   vor der Fortsetzung dauerhaft belegt. Fremde/unklare Owner erhalten keinen
   Override. Die native Projekt-Recovery bleibt gesondert autorisiert.

**Abgleich mit allen Grenzen aus 2.4.1.** (1) Diese Detailregel schließt
die Crashfortsetzung des bereits beauftragten Restore-Works in 15.l.R;
sie führt keinen weiteren Fachcommand, Authprovider oder Hintergrundprozess
ein. Die beiden ausdrücklich getrennten Work-Optionen konkretisieren nur
den bereits vorgesehenen Aufruf `work resume` für `recover.restore`.
(2) Erhaltene Owner und vollständige Wiederaufnahme werden gleichzeitig
abgedeckt; native Journalwahrheit bleibt vor jeder neuen Originalinventur
maßgeblich. (3) Sicherheitsniveau, ursprünglicher Auftrag, historische
Dateibytes, Recoverybarrieren und menschliche Reviews bleiben erhalten.
Keine allgemeine oder fremde Lockfreigabe wird delegiert; lebende und
unbekannte Owner bleiben blockiert. Alte Aufrufe, Workdaten und Produkt-
freigaben ändern sich nicht. (4) Versionierte additive Regel und erhaltene
Original-/Übergabebytes erlauben eine ausdrückliche spätere Fortschreibung;
kein Löschen alter Belege, automatischer Rollback oder Buildkompatibilitäts-
wechsel wird erlaubt. (5) Die Regel benötigt keine fehlende externe
Risikoakzeptanz oder erfundene Hostberechtigung. Native Laufzeitbeobachtung
ist bei der späteren tatsächlichen Ausführung Pflicht und darf scheitern.

**Zusätzliche offene Verhaltensabnahmen von 15.l.R.**

- Ein echter Prozessabbruch während äußerer Checkpointveröffentlichung
  hinterlässt den tatsächlichen Owner und den letzten vollständigen
  Checkpoint. Ein ausdrücklich angeforderter Wiederanlauf mit exakt passendem
  Ownerhash und erneut nativ als beendet bestätigtem lokalen Owner bewahrt
  alle ursprünglichen Bytes, belegt den Ownerwechsel und führt den identischen
  Auftrag fort; unveröffentlichte Generationen gelten nicht als Fortschritt.
- Getrennt nachweisen: terminaler identischer Prozess, sicher abwesender PID
  und tatsächlich wiederverwendeter PID mit anderer Startkennung. Ein lebender
  ursprünglicher Prozess, belegter Mutex, unbekannter Start, abweichender
  Boot-/PID-Namespace, fehlendes/unlesbares `/proc` oder lediglich freier Mutex
  gestatten keinen Austausch. Der neue Prozess eines wiederverwendeten PID
  wird weder einem verändernden Signal ausgesetzt noch beendet.
- Fehlendes Optionspaar lässt den Owner unverändert; einseitige oder
  ungültige Angaben ergeben 2, ein abweichender Bytehash 6. Falsche Work-/
  Anfangs-/Root-/Checkpointbindung, fehlende Objektbytes, unsichere Dateien
  und native Beobachtungsänderung vor dem Austausch werden in der
  vorgeschriebenen Fehlerklasse abgewiesen. Ein frischer `--force`- oder
  Remote-Risiko-Wert für den Projektlock ersetzt keine Work-Erlaubnis.
- Tatsächliche Abbrüche vor dem gesicherten Übergabebeleg, vor/nach atomarem
  Ownerwechsel, vor/nach Übergabeabschluss und bei der folgenden
  Checkpointveröffentlichung behalten die tatsächlich entstandenen Bytes.
  Wiederaufnahme rekonstruiert genau den belegten betrieblichen Zustand;
  kein Owner wird aus Absicht, Lockalter oder gespeicherter Zustimmung
  erfunden. Neue Ownerwechsel benötigen jeweils den aktuellen Ownerhash
  und alle aktuellen Prüfungen. Defekte oder widersprüchliche Belege sperren.
- Nach erfolgreicher äußerer Übernahme bleibt die innere Restore-Recovery
  unabhängig: fehlende aktuelle Autorität, unzulässiger Projektowner,
  unvollständige Before Images oder Konflikte bleiben blockierend.
  Vollziel mit fehlendem äußeren Abschluss wird ohne Zielneupublikation
  abgeschlossen; Teilziel wird nur nativ zurückgerollt. Quellenverlust
  darf diese Unterscheidung nicht verdecken; Rollback wird kein Restoreerfolg.
- Workfortschritt und vollständiges Ergebnis werden erst an ihren realen
  Publikationsgrenzen bestätigt. Vollständig abgeschlossenes Work liefert
  nach 10.7.7/11.12 sein gespeichertes Resultat, ohne eine neue Prüfung eines
  geänderten Projekts zu behaupten. Übergabebelege allein genügen nicht.
- `work status` beobachtet ohne Austausch; Cancel/Export bereinigen keine
  laufende Owner-/Restoreübergabe. Bestehende Read-only-/Change-Plan-Workdaten,
  geschützte Geschichte, Buildgrenzen und normale Projektowner-Recovery
  bleiben unverändert; beide neuen Optionen sind für andere innere Befehle
  unzulässig. CLI und strukturierter Aufruf weisen dieselben Gates nach.

**Umsetzung und Übergabegrenze.** Dies ist ausschließlich ein
OFF-PLAN-Spezifikationsstand, kein Produktcode, keine künstliche W/R/C-Folge,
kein zusätzlicher regulärer Planschritt und keine behauptete Produktabnahme.
15.l.R bleibt offen, insbesondere äußere Fortschritts-/Ergebnislieferung,
native Crash-/Ownerparität, vertrauenswürdige CLI-Anbindung und die übrigen
historischen Provider-/Erhaltungsgates. Aktive Katalogdateien erhalten nur
die neue Spezifikationshashbindung; historische Nachweise werden nicht
nachträglich umgebunden. Nach dem erfolgreichen Apply muss Control den
offenen Schritt erneut beauftragen.

Der Entrypoint stellt genau diesen Dokument-/Katalogstand her und prüft vor
seinem einen OFF-PLAN-Commit die fällige **N=3-Gruppe 0, Sequenz 216** parallel.
Erst nach bestandenem Apply-Testlauf setzt er die OFF-PLAN-Checkbox und
Bundle-Nummer auf 510; der Produktzähler bleibt **649/900**. Ein tatsächlicher
Commit schaltet anschließend auf Gruppe 1. Keine neue Testidentität,
Umnummerierung, zusätzliche Vollsuite, serielle Ausführung oder CI-Auslösung.

**Beobachtete gezielte Dev-Prüfung.** Die endgültige aktive Katalogfassung
besteht **54/54** bestehende Verhaltenstests aus `tests/test_catalog_check.py`
und `tests/test_catalog_check_right.py` in **6.54 s**, mit **vier
parallelen Workern**, Exit **0** und ausschließlich `passed`-Einzeloutcomes.
Ausgeführt wurde `tools/run_selected_tests.py --workers 4 --expected-tests 54`
mit den beiden vollständigen Dateien in einem frischen ignorierten
Berichtsroot. Geprüft wurden die betroffenen maschinenlesbaren Katalog- und
Auswahlverträge; keine Dokumentations-/Darstellungstests und keine externe
Control-Ausführung.

Die vollständige Collection-/Katalogprüfung bestätigt **22.114** aktive
Tests, **0** Katalogfehler, Exit **0** und **0** ausgeführte Testkörper.
Die **22.118** dauerhaft reservierten Nummern einschließlich vier historisch
entfernter Identitäten bleiben bytegleich. Produktcode, Tests, Fixtures,
Oracles, Runner, Workflows und historische Evidence bleiben unverändert.
Die **743** aktiven Katalogdateien ändern ausschließlich
`specification_sha256`; einschließlich Spezifikation und Plan sind es
**745** geänderte Bestandsdateien, keine neuen Produktdateien oder Löschungen.

Gebundener Entwicklungsquellhash:
`46d8dbffb99cdd7946d37f5418bfe930073b3c3a1f0649e2e396fc664749cc7e`;
Katalogvertrag-SHA-256:
`f724111c4107ab205255a1834d47b5483b824d522a06c377a626e2d5b07f720e`;
Auswahlbericht-SHA-256:
`f3d783dc86d0b03a56daefcf83e7c337943a10abdc16647785e815f2634cd2fd`;
Einzeloutcomes-SHA-256:
`d0aa0e6393a9cf9bc241e7975134b9f28c85aeb728ef68a28ea7d538a5929177`.
Dies ist ausdrücklich eine Teilprüfung mit `full_suite_passed=null`,
kein vollständiger oder serieller Testlauf und kein Releasebeleg.

Der bestätigte vorherige Apply-Nachweis für den regulären Zwischenstand
15.l.R (Bundle 509) ist davon getrennt:
Auswahlbindungs-SHA-256 `325b574bb83736a9fb43450ba00e6b59c1ff272e4c1c7f6db0dfe6fa347f096e`,
Bericht-SHA-256 `7a98bbe76b53e7b90b4916fb377e3d7361e71a202cf079eefcbe25a9a3c50a0f` und
Einzeloutcomes-SHA-256 `2fd3406b6a722ffce1791bfad59327d2daa33543c94606fe398755bb894b6f9e`.
Die vorgesehene neue Apply-Gruppe und der OFF-PLAN-Commit sind bei dieser
Übergabe noch nicht ausgeführt. Native ZIP-Prüfung und atomare Veröffentlichung
beenden den Einzelauftrag; 15.l.R bleibt offen.
