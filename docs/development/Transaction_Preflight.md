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
Übernahmebeleg übernommen. Mehrere oder unklare aktive Einträge verlangen eine
explizite Auswahl; die automatische Funktion rät keine Transaktion.

Nach dieser Entscheidung beginnt eine ausgewiesene Recoveryphase. Sie darf die
dafür nötigen vollständigen Journal-/Ressourcenbeweise lesen. Die vorhandenen
APIs verwerfen bewiesene Building-/Prepared-Vorbereitungen, schließen ein
vollständig veröffentlichtes Ziel ab oder rollen einen bewiesenen Teilstand
zurück. Dauerhafte Receipts und explizite Bereinigung erhalten die Belege.
Projektpolicy und native Bindungen werden vor der Mutation erneut geprüft.

Auch nach erfolgreicher Recovery liefert dieser Aufruf Exit 5:
`recovery_completed=true`, `normal_operation_started=false`,
`request_consumed=false`, `requires_new_invocation=true`. Die neue Request-ID
erhält kein Erfolgsreceipt. Vorhandene Receipts betreffen ausschließlich die alte
Transaktion. Der Host muss einen neuen Aufruf mit aktuellen Eingaben beginnen;
eine frühere Beobachtung ist keine wiederverwendbare Schreibberechtigung.
Fehler behalten den tatsächlichen Teilabschluss und mögliche Writes sichtbar.

Der W-Stand deckt native lokale Linux-Transaktionen und die explizite
Bibliotheksintegration ab. Weitere Wiederaufruf-/Unterbrechungsgrenzen folgen
in 5.t.R. Allgemeine Preflightprofile und Detailfortsetzung bleiben 6.a,
`environment check` bleibt 6.b, die vollständige Crashmatrix bleibt 5.v.
Die Verhaltenstests stehen in `test_transaction_preflight.py`; die technische
Testausführung richtet sich nach [Testing.md](Testing.md) und der lokalen AGENTS.md.
