# Transaktionsprüfung vor normalen Projektaufrufen

`specroad.changes.transaction_preflight` prüft aktuelle Betriebsmetadaten vor
einem normalen Projektaufruf. Der vertrauenswürdige Host liefert die echte
`CommandClass`; eine Klassenangabe allein authentifiziert keinen Aufrufer.
Unterstützt sind `READ_ONLY`, `PLAN_OUTPUT`, `GENERATED_OUTPUT` und
`NORMATIVE_WRITE`, jeweils mit explizitem Dry-Run-Modus. Die Funktion führt
keine neue Fachoperation aus und installiert keinen zusätzlichen CLI-Befehl.

Die kurze Prüfung liest flach die aktiven Namensstellen. Sie klassifiziert
höchstens 16 aktive oder unklare Einträge und scannt keine Artefakte,
Anhänge, Caches, Receipt- oder Audithistorie. Bereits gefundene aktive Einträge
beweisen Recoverybedarf; eine abgeschnittene Liste bleibt gesperrt und erlaubt
keine automatische Auswahl. Die bestehende schreibfreie Projektvalidierung
verwendet dieselbe begrenzte Startbeobachtung. Die ausdrücklich angeforderte
Metadatendiagnose behält dagegen ihren vollständigen Namensbestand; sie liest
weiterhin keine Journalbodies oder Modellartefakte und verändert keine Dateien.

Ein Lese-, Plan-, Ausgabe- oder Dry-Run-Aufruf liefert bei Recoverybedarf
Exit 5 ohne Konfigurations-/Journalbody, Modellload, Lockdatei oder anderen
Betriebswrite. Eine freie Transaktionsprüfung liefert Exit 0, aber weder
Schreibberechtigung noch eine gültige Modellbasis: normale Konfigurations-,
Validierungs-, Autorisierungs- und Veröffentlichungsprüfungen bleiben nötig.

Automatische Recovery setzt einen normativen Aufruf ohne Dry-Run,
`transaction_policy.auto_recover=true`, eine neue Request-ID, einen expliziten
Actor und eine vom Host registrierte `RecoveryAuthority` voraus. Fehlende Policy
wird nicht als Zustimmung gelesen. Die Konfiguration wird innerhalb des
Metadatenbudgets von 1 MiB gelesen. Ein lebender, fremder oder nicht sicher
beurteilbarer Eigentümer wird nicht automatisch übernommen. Ein nachweislich
beendeter lokaler Writer wird nur unter dem nativen Mutex und mit dauerhaftem
Übernahmebeleg übernommen. Mehrere oder unklare Transaktionen verlangen eine
explizite Auswahl; die automatische Funktion rät keine Transaktion. Die neue
Request-ID darf nicht mit der Request-ID der ausgewählten alten Transaktion
übereinstimmen; dieser Konflikt endet vor Lockanlage und Recovery mit Code 6.

Nach dieser Entscheidung beginnt eine ausgewiesene Recoveryphase. Sie darf die
dafür nötigen vollständigen Journal-/Ressourcenbeweise lesen. Die vorhandenen
APIs verwerfen bewiesene Building-/Prepared-Vorbereitungen, schließen ein
vollständig veröffentlichtes Ziel ab oder rollen einen bewiesenen Teilstand
zurück. Dauerhafte Receipts und explizite Bereinigung erhalten die Belege.
Projektpolicy und native Bindungen werden vor der Mutation erneut geprüft.

Ein einzelner nativer `pending-cleanup`- oder `pending-discard`-Deskriptor darf
dieselbe Transaktion auswählen, auch wenn ihr Arbeitsverzeichnis bereits ins
Archiv verschoben wurde. Sein Lesen bleibt im kurzen Metadatenbudget. Root,
Projekt, Transaktion, Journalhash und unveränderlicher Intent müssen zusammen
passen; fremde Referenzpfade werden nicht verfolgt. Die Recovery liest nur die
aus dem verifizierten Journal abgeleiteten kanonischen Belegstellen und nutzt
den vorhandenen Abschlussweg. Beschädigte Belege und weitere aktive
Transaktionen bleiben gesperrt; historische Receipts werden nicht durchsucht.

Auch nach erfolgreicher Recovery liefert dieser Aufruf Exit 5:
`recovery_completed=true`, `normal_operation_started=false`,
`request_consumed=false`, `requires_new_invocation=true`. Die neue Request-ID
erhält kein Erfolgsreceipt. Vorhandene Receipts betreffen ausschließlich die alte
Transaktion. Der Host muss einen neuen Aufruf mit aktuellen Eingaben beginnen;
eine frühere Beobachtung ist keine wiederverwendbare Schreibberechtigung.
Fehler behalten den tatsächlichen Teilabschluss und mögliche Writes sichtbar.

Intern trennt der C-Stand drei Aufgaben: `transaction_preflight` hält die
öffentliche Aufruf-/Ergebnisgrenze, `_preflight_decision` liest die begrenzten
Metadaten und bindet die Auswahl in einer internen `RecoveryDecision`,
`_automatic_recovery` führt ausschließlich die ausgewählte alte Recovery aus.
Die Entscheidung ist keine Schreibberechtigung. Aktuelle Policy-, Eigentümer-,
Journal- und Ressourcenprüfungen bleiben im ausführenden Pfad erforderlich.
Sein tatsächlicher Zwischenfortschritt bleibt auch bei einer späteren Ausnahme
für dieselbe öffentliche Fehlerantwort erhalten.

Der W-/R-Stand deckt native lokale Linux-Transaktionen und die explizite
Bibliotheksintegration ab. Tests in getrennten Interpretern verfolgen Recovery
und danach eine frisch geplante, erneut autorisierte native Veröffentlichung.
Ein vor Recovery erstellter PublicationPreflight wird unter dem neuen
Writerlock gegen die aktuellen Bytes und Dateibindungen geprüft. Die klare
Transaktionsbeobachtung kann diese Prüfung oder die neue Berechtigung nicht
ersetzen. Die Wiederaufnahme einer unterbrochenen Archivierung behält den
ursprünglichen Intent und alle alten Ergebnisbelege.
Allgemeine Preflightprofile und Detailfortsetzung bleiben 6.a,
`environment check` bleibt 6.b, die vollständige Crashmatrix bleibt 5.v.
Die Verhaltenstests stehen in `test_transaction_preflight.py` und
`test_transaction_preflight_right.py`; die technische
Testausführung richtet sich nach [Testing.md](Testing.md) und der lokalen AGENTS.md.
