# OFF-PLAN – Gebundene Ownerübergabe für Restore (Bundle 500)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Gebundene Ownerübergabe für Restore (Bundle 500)

Revision 27 präzisiert **RESTORE-OWNER-HANDOFF** in Spezifikation
**0.2.32 / 10.7.5**. Der reguläre Stand bleibt **649/900**, zuletzt
**15.l.W**, nächstens **15.l.R**. Autorität: **delegiert gemäß
SPECROAD-DECISION-1**, keine behauptete persönliche Einzelfreigabe.

- [x] **RESTORE-OWNER-HANDOFF:** Ownerübergabe an einen Restore konkretisieren.
  Commit: `docs(spec): Gebundene Ownerübergabe für Restore präzisieren`.

**Geprüfte Basis und Auftrag.** Maßgeblich ist das eindeutig aktuelle saubere
Result `specroad-apply_Result_193818_1026_6f163e.zip`, SHA-256
`37423ae89369c0dd958d5be0e1622ce51327305dcecbd73c15690a6b9a3c36fe`.
Es bindet Commit `0927dd09611f0ea798549f0169f20c6794e072f6`, Repository
`a33ed6cf-0a97-4b73-b11a-d4239e7a2145`, Fingerprint `7c9d2a24e397e0e5`,
Algorithmus `patchharbor-state-v1`. Root-Anleitung, Kontext, Umgebung,
Manifest, Run-/Ausführungslogs und alle **2.298** Snapshotdateien mit
Blob-IDs/Modi stimmen mit dem tatsächlichen sauberen Apply-Stand überein.
Bundle **499**, Paket-SHA-256
`c3dbe8dc60443e22c6135da36f896aba79a3bb64b7cf84f5ca019fbec56c6d13`,
ist ein regulärer W-Umsetzungsschritt. Sein zugehöriger Abschlusscommit
entstand nach **7.214/7.214** bestandenen parallelen Apply-Tests,
**Sequenz 205 / Gruppe 1**, vier Worker, **2442.22 s**. Gebundene Auswahl,
Einzeloutcomes und tatsächliche Commitdateien wurden geprüft.

§2.4 erlaubt Vertrag 3 ausdrücklich. Der aktuelle Auftrag erteilt
`version=3`, `clarification_limit=3`, `clarifications_remaining=3`,
`clarification_allowed=true`. Der neue Vertrag folgt dem belegten normalen
Abschluss von 499; alte Version-2-Aufträge und Antworten bleiben erhalten.
Dieses eine Klärungsbundle erneuert kein Budget. Die einmalige Verbuchung
bei Übernahme seines Folge-Results bleibt bei Control. Kein lokaler
Budgetzähler, Controlwrite oder eigener Folgeauftrag entsteht.

**Genaue Lücke.** 10.7.3 verweist für Ownerübernahme auf den bestehenden
Lockvertrag, 10.7.4 wählt ausdrücklich auch beschädigte Originaljournale.
Noch nicht bestimmt ist, welcher Zusammenhang einen Owner einer anderen
alten Transaktion mit dem **neuen** Restore-Auftrag verbinden muss und wie
diese Übergabe von der Fortsetzung **derselben** Restore-Ausführung getrennt
wird. Die Auswahl allein autorisiert keine Aufhebung einer Sperre; eine
Übernahme darf nicht aus einer fehlenden PID abgeleitet werden.

Geprüft wurden 2.1/2.4, 10.7.1–10.7.4, 11.7, N.2/N.3, SR-REQ-0221/0258/
0461/0462/0511/0569 und R-44/R-47 sowie der bestätigte Umfang von 15.l.R.
Technische Grundlagen sind `changes/locking.py`, `_lock_files.py`,
`_lock_owner_policy.py`, `recovery_lock.py`, `_journal_codec.py`,
`recovery/execution.py`, `_execution_layout.py`, `_journal_selection.py`
und die bestehende Beschreibung in `docs/development/Transaction_Recovery.md`.
Die gewöhnliche `transaction_recovery_lock`-API verlangt exakt dieselbe
Transaktions-/Requestidentität und ein gültiges gewöhnliches Journal;
`lock recover --force` hat ein Journalveto. Die W-Restore-API lehnt vorhandene
Owner sicher ab. Das sind vorhandene Grenzen, keine fehlende Erlaubnis,
die durch Austausch eines API-Namens übergangen werden dürfte.

**Alternativen.**

1. Owner automatisch aus Plan, Auswahl, Actorlabel oder fehlender PID
   übernehmen: widerspricht den aktuellen Berechtigungs-/Ownergates.
2. Für den allgemeinen Lock-Recovery-Weg Journale ausblenden oder löschen,
   oder einen Restore als gewöhnliche Transaktion umetikettieren: verletzt
   Journalveto, Originalerhaltung und getrennte Auftragsbindung.
3. Alle Restores mit übrigem Owner dauerhaft ausschließen: erhält zunächst
   Daten, ersetzt aber die zugesagte explizite Recovery nach Prozessabbruch
   nicht. Eine sichere W-Ablehnung darf kein dauerhafter Featureersatz werden.
4. **Gewählt:** ausdrücklicher, zweitseitig gebundener Restore-Handoff mit
   unveränderten nativen Mutex-/Owner-/Risiko-/Autorisierungsgates. Ein
   gewöhnlicher Altowner muss exakt auf einen gewählten kanonischen
   Originaltransaktionseintrag zeigen; ein Restore-Owner auf genau dieselbe
   ursprüngliche Ausführung. Beide Seiten und der aktuelle Recovery-Akteur
   bleiben getrennt auditiert. Kein globaler Lock-Recovery-Vertrag ändert sich.

**Begründung und Grenzen nach 2.4.1.** Die Entscheidung schließt eine
Detailgrenze im bereits offenen Restore-/Crashumfang von 15.l.R; sie fügt
keinen weiteren Produkt- oder Meilensteinschritt hinzu. Die konkrete Lösung
erhält gleichzeitig vollständige Restorequalifikation, explizite Auswahl,
korrupt erhaltene Originalbytes und alle alten Lock-/Risikogates. Sie
schwächt kein gleichrangiges Requirement ab. Die zusätzlichen Optionen sind
ausdrücklich und befehlsspezifisch; vorhandene ownerfreie Aufrufe und die
geschlossenen Plan-/Auswahlformate bleiben kompatibel. Niemand erhält durch
Dokument, Journal oder gespeicherte Autorisierung eine aktuelle Befugnis.

Nur der nun getrennt gebundene Restoreauftrag darf nach vollständiger
Prüfung den neuen Recovery-Owner stellen. Alte Requests, Journale, Belege
und Ownerbytes bleiben erhalten; eine echte aktuelle Hostautorität und
gegebenenfalls menschliche Risikoentscheidung sind weiterhin nötig. Diese
Entscheidung behauptet keine solche reale Zustimmung und benötigt keine
erfundenen externen Fakten. Native Primitiven haben Vorrang vor einem
zweiten Lock-/Dateisystemkern. Eine spätere versionierte Präzisierung kann
den Vertrag ändern, ohne bestehende Belege zu migrieren, zu löschen oder
als Produktfreigabe umzudeuten. Fehlende notwendige Bindungen bleiben echte
Blocker; kein unsicherer Fallback wird eingeführt.

**Normative Fortschreibung und offene Abnahmen.** Maßgeblich ist 10.7.5.
Die folgenden zusätzlichen Konkretisierungen gehören zur bestehenden
15.l.R-Abnahme; alle bisherigen W-/R-/C-Kriterien bleiben erhalten:

- Ein gültiger verwaister gewöhnlicher Owner, dessen kanonischer
  Transaktionseintrag ausdrücklich ausgewählt ist, kann unter aktueller
  Hostautorität und unveränderten Ownergates an genau den qualifizierten
  neuen Restore übergeben werden. Beschädigte Bytes und leere Originale
  werden unverändert gesichert; die Übernahme selbst publiziert kein Ziel.
- Ein abrupt abgebrochener Restore wird nur mit ursprünglichem Plan,
  Ausführungs-/Requestbindung und identischer Auswahl übernommen. Neuer
  Recovery-Akteur und ursprünglicher Akteur sind im Audit unterscheidbar.
  Vollzielabschluss und Teilziel-Rollback behalten SR-REQ-0258/0511.
- Fehlende Force-/Hash-/Grundangaben, abweichender Owner oder Root,
  falscher kanonischer Originalpfad, nicht ausgewählter Vorgang, fremde
  Restore-Ausführung und unlesbare notwendige Belege verhindern jeden
  Vorprüfungswrite mit der jeweils getrennten Fehlerklasse. Ein geänderter
  aktueller Owner wird nicht aus alten Audits wieder eingesetzt.
- Lebender Owner und besetzter echter Mutex bleiben unübernehmbar.
  Fremde, unprüfbare und PID-wiederverwendete Owner brauchen die vorhandene
  ausdrückliche Risikozustimmung. Denied-, nichtboolesche oder mutierte
  Hostantwort und lediglich gespeicherte Zustimmung genügen nicht.
- Tatsächliche Prozessabbrüche vor/nach Intentdurabilität, atomarem
  Ownerwechsel, Abschlussbeleg und Restore-Journalanlage erhalten alte
  und neue Belege. Vor Zielpublikation wird nur der gebundene
  `building`-Abschluss vollendet; kein neuer Restore beginnt beiläufig.
  Kurze/fremde Belege bleiben unangetastet, jeder neue Übernahmeversuch
  braucht aktuelle Prüfung. Fsync-/I/O-Fehler behaupten keinen Abschluss.
- Normale Reader und Writer bleiben bei ungelöstem Zustand gesperrt.
  Allgemeines Lock-Recovery behält sein Journalveto; gewöhnliche
  Transaktionsübernahme ihre ursprüngliche Bindung. Einzellauf und Work
  verwenden dieselben Restore- und Handoffgates, einschließlich der
  unveränderten vollständigen Ziel-, Sicherungs- und Crashabnahmen.

**Umsetzung und Übergabe.** Dieses Bundle enthält nur Spezifikation, Plan
und die erforderlichen aktiven Kataloghashbindungen. Produktcode, Tests,
Fixtures, Testnummern, Runner, Workflows, lokale Regeln und historische
Nachweise bleiben bytegleich. Es gibt keine neuen Dokumentationstests,
keinen Volltest und keine künstliche W/R/C-Folge. SR-TC-0461/0462 bleiben
`partial`, 15.l.R/C offen. Die vollständige Restoreintegration und alle
bereits dokumentierten Pflichtprovider bleiben ausdrücklich offen.

Der externe Entrypoint prüft genau **Sequenz 206 / Gruppe 2 von 3**, mit
vier parallelen Workern, vor dem einen OFF-PLAN-Commit. Erst danach werden
der OFF-PLAN-Marker und die Bundle-Nummer **500** gesetzt; der Produktzähler
und alle regulären W/R/C-Checkboxen bleiben unverändert. Apply ist bei der
Übergabe ausstehend. Die nativ geprüfte kanonische ZIP wird atomar an Exchange
übergeben; `spec_clarification`, danach sofortiger Abschluss dieses Auftrags.
Kein eigenes Apply, kein Warten auf Result und keine Hintergrundfortsetzung.

**Beobachtete gezielte Dev-Prüfung.** Die Dokument- und Katalogfassung
besteht **54/54** bestehende Verhaltenstests aus `tests/test_catalog_check.py`
und `tests/test_catalog_check_right.py` in **6.56 s**, mit **vier
parallelen Workern**, CPython **3.14.4**, Exit **0** und ausschließlich
`passed`-Einzeloutcomes. Ausgeführt wurde `tools/run_selected_tests.py
--workers 4 --expected-tests 54` mit den beiden genannten vollständigen
Dateien in einem frischen ignorierten Berichtsroot. Geprüft werden die von
der Spezifikationshashbindung betroffenen maschinenlesbaren Katalog- und
Auswahlverträge; keine Dokumentation, Darstellung oder externe Control-Ausführung.

Die vollständige Collection-/Katalogprüfung bestätigt **21.646** aktive
Tests, **0** Katalogfehler, Exit **0** und **0** ausgeführte Testkörper.
Die **21.650** dauerhaft reservierten Nummern einschließlich vier historisch
entfernter Identitäten bleiben bytegleich. Produktcode, Testdateien,
Fixtures, Oracles, Runner, Workflows und historische Evidence ändern sich
nicht. Die **743** aktiven Katalogdateien ändern ausschließlich
`specification_sha256`; einschließlich Spezifikation und Plan sind es
**745** geänderte Bestandsdateien, keine neuen Produktdateien oder Löschungen.

Gebundener Entwicklungsquellhash:
`845526de781aec0e1ea1a4c4ff63195c4acf94fb9649edf17bb90c953aaa67d2`;
Katalogvertrag-SHA-256:
`72d2821f56afaac92242f4c7f577b4b64162b337f8f2420cec8ea11c128399da`;
Auswahlbericht-SHA-256:
`a535faf4999c329960901bfe6ac791b56f15ec44218d0e2e8212a2a49615151d`;
Einzeloutcomes-SHA-256:
`25f490624d730a46732dcc9a240d7690f6fe66e47dca7fecd528e22bcb1116d1`.
Dies ist ausdrücklich eine Teilprüfung mit `full_suite_passed=null`;
kein vollständiger oder serieller Testlauf und kein Releasebeleg.

Der bestätigte vorherige Apply-Nachweis für den regulären
W-Schritt 15.l.W (Bundle 499) ist davon getrennt:
Auswahlbindungs-SHA-256 `94e6dca23b34d1c7bac1eeab679f6b53eb34db9090133e068f284c60fecef614`,
Bericht-SHA-256 `60d0961904247a2bd2de87d563ebe63f9db99db28881bad23d38b145ece1231e` und
Einzeloutcomes-SHA-256 `61bebf66381e8bd20c5e3390467e986740c0274b06e2ff15a71f6730cb842921`.
Die vorgesehene neue Apply-Gruppe und der OFF-PLAN-Commit sind bei dieser
Übergabe noch nicht ausgeführt. Native ZIP-Prüfung und atomare Veröffentlichung
beenden den Einzelauftrag; 15.l.R bleibt offen.
