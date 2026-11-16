# Bundle 707 — normale Schreibadapter und Abbruchsperre (18.u)

Datum: 15. November 2026. Grundlage ist das erfolgreiche, saubere Result
`specroad-apply_Result_151237_1115_ec38a8.zip`, SHA-256
`c331263229576645270479a18421910e9f3d8bb1f359fb9c3e9d520e942bb3a7`,
Commit `fc398fd4217296aa7832261f4ddb93549e023a64`. Bundle 706 bestätigt
TEST-OVERHEAD.W/R/C mit 7.506 / 7.562 / 7.643 bestandenen Tests. Es gibt keinen
offenen Korrekturrest; frühere erfolgreiche Commits werden nicht wiederholt.

Die vorhandenen C.1/C.2.1- und N-Verträge bestimmen diese Umsetzung vollständig.
Kein Klärungscommit und keine Budgetänderung. Diese Übergabe enthält die vollständige
Gruppe 18.u mit drei echten Zuständen. Jede Stage benötigt vor ihrem Commit die
fällige N=3-Gruppe plus ihre ungefilterte Pflichtauswahl. Vorherbytes und
Folgezustände werden getrennt gebunden; der Endstand wird nicht vorab installiert.

| Stage | Änderung und vorbereitete Abnahme |
| --- | --- |
| 18.u.W | Authoring, Relationsreview, Lifecycle, Evidence, Baseline, Import, Format-/Work-Publikation und öffentlicher Proposalabschluss verwenden denselben nativen Writer. Preflight blockiert normale Reads, Pläne, Dry-runs und Writes ohne automatische Reparatur. Normale Receipt-Leser und Export verstehen die neuen vollständigen Belege; historische v1-Belege bleiben lesbar. Reale positive, verweigerte und blockierte Adapterfälle sowie die bestehenden fachlichen Abnahmen werden an Apply übergeben. |
| 18.u.R | Wiederholungen liefern die ursprünglichen Ergebnisse ohne zweite Revision. Receipt-Namespace, Bytes, Inodes und Verzeichnisse bleiben gebunden. Aktuelle Zielprüfung verlangt originale Preflight-Eingänge und erneute Byteprüfung. Unklare Eigentümer und der reine Kernelmutex vor der Lockdatei sperren auch normale CLI-Aufrufe. Offene Marker bleiben gesperrt. |
| 18.u.C | Gemeinsame deskriptorrelative Receipt-Beobachtung ist vom historischen Journalformat getrennt. Unbenutzte alte normale Writer-/Cleanupimporte entfallen; native Qualifikation, Autoritätsprüfung und Effektfolge bleiben identisch. Die Testdateien bleiben bytegleich zu R. |

Die früheren automatischen Reparaturoracles der betroffenen normalen Adapter
werden durch erhaltene Original-/Teilzustände und die Abbruchsperre ersetzt.
Fehler, Autoritätsverweigerung, Quelltausch, Originalbelege, menschliche Freigaben,
KI-Schreibschutz, Historie und tatsächliche Prozessabbrüche bleiben verpflichtend.
Alte Testidentitäten werden beibehalten; neue Nummern werden nur angehängt.
Die Pflichtauswahl umfasst alle geänderten/neuen Testdateien und die relevanten
Writer-, Pfadschutz-, Receipt-, Proposal-, Import-, Work-, Preflight- und
Bundle-Regressionsdateien. Die nummerierte Rotationsauswahl wird nicht verkürzt.

Dev führt nur Syntax, statische Strukturprüfung, reine Collection und native
Paketvalidierung aus. Keine Testkörper oder Fixtures wurden in Dev ausgeführt;
Vorbereitung ist keine Verhaltensabnahme. Die Produktfortschrittswerte dieser
Stage gelten erst nach erfolgreichem eigenem Gate und Commit. Die vollständige
Folge 18.v (Migration, Merge und Rooterzeugung), 18.w (alte Reparaturbefehle) und
18.x (abschließende Format-/Git-Wiederanlaufabnahme) bleibt offen. Die größere
normale Adaptergruppe wird hier vollständig geliefert; zusätzliche Spezialwriter
werden nicht als unvollständiger Anhang vorgezogen. Keine Dienste, Konfigurationen,
Git-Schreibaktionen oder direkte Änderungen an Apply.

Vorbereiteter Zwischenstand: **18.u.C**; nach eigenem erfolgreichen Gate Zielposition **771/918**, danach **18.v.W**.
