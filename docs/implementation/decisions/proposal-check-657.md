# PROPOSAL-CHECK-657 — isolierter Abschlussbericht und Debug-Aufbewahrung

9. November 2026; delegiert gemäß SPECROAD-DECISION-1, Vertrag 4.
Betroffen: vollständiger Schritt 18.g.W/R/C. Quellen: Spec 10.3, 11.10,
SR-REQ-0166–0170/0178/0195/0645, bestehende native Proposal-Basis-/Planprüfung,
Validator, Lint, Dokument-/Querydienste, semantischer Diff und direkte Impact-Analyse.

Die Pflicht zum isolierten Check und Aufräumen ist klar. Offen waren die
maschinenlesbare Auditprojektion, die explizite Debugoption und die beobachtbare
Bedeutung eines Checkresultats in anderen Ausgangszuständen. Geprüfte Alternativen:
freie Berichtsobjekte lassen Bindung/Teilfortschritt unklar; ein persistierter
Prüfstempel widerspricht der bestehenden Lesepflicht; ein komplett neuer
Prüfprozess dupliziert native Dienste. Gewählt ist ein kleiner additiver
`proposal-check-v1` mit bestehenden nativen Unterergebnissen und JCS-Hash,
einer ausdrücklichen `--keep-workspace`-Option und unveränderten Übergangsregeln.
Die vollständige normative Regel steht ausschließlich in Spec 10.3.2.

Alle Grenzen von 2.4.1 bleiben erhalten: bestehender Planscope und Abnahmen,
keine geänderte Nutzerentscheidung, unveränderte Sicherheits-/Reviewpflichten,
keine Bestandsmigration oder Datenverluste, additive rücknehmbare CLI/Result-
Festlegung, keine fehlenden externen Fakten oder erfundenen Freigaben. Fehlende
native Fachnachweise bleiben Fehler. Keine neue Requirement-ID oder Planposition.

Abnahmen: echte Basis-/Zieldateien nur im privaten Prüfbereich; Originalinventar
und Status bleiben gleich; Vollvalidierung, Lint, Query, Rendering, Diff und
beidseitiger direkter Impact stammen aus nativen Diensten; falscher Zielroot,
fehlerhafte Modelle und Quellenwechsel bleiben Fehler. Default-Cleanup auf
Erfolg/Fehler, explizite Aufbewahrung und blockierte Projekt-Unterpfade prüfen.
Bösartige passive Inhalte starten weder Shell, Tests, Builds, Netzwerk noch
Plugins. Audit/Hash/Result-Schema und argv/strukturierte Requests prüfen.
C erhält sämtliche W/R-Testbytes. Umsetzung und Apply-Nachweise sind noch offen;
dieser Klärungscommit allein zählt keine der 900 Produktpositionen als erledigt.
