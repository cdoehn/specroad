# OFF-PLAN – Dreierregel für Control-Vertrag 3 (Bundle 498)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Dreierregel für Control-Vertrag 3 (Bundle 498)

Revision 26 setzt den ausdrücklichen manuellen Nutzerauftrag als
**SPECROAD-DECISION-1-V3** um. Spezifikation **0.2.31 / 2.4.3** erweitert
die Entwicklungsbefugnis ausschließlich unter gültigem Control-Vertrag 3.
Der reguläre Stand bleibt **648/900**, zuletzt **15.k.C**, nächstens **15.l.W**.

- [x] **SPECROAD-DECISION-1-V3:** Klärungsbudget für Control-Vertrag 3 erweitern.
  Commit: `docs(spec): Klärungsbudget für Control-Vertrag 3 erweitern`.

**Auftrag und Autorität.** Der Nutzer beauftragt ausdrücklich die Erweiterung
von **SPECROAD-DECISION-1** auf höchstens drei aufeinanderfolgende
Klärungsbundles unter **Control-Vertrag 3** und erteilt dafür die Befugnis zur
Änderung der Projektregel. Autorität ist dieser manuelle Nutzerauftrag vom
26. Oktober 2026, **nicht** die bisherige Delegation. Die bisherige Einerregel
bleibt für Version 2 erhalten. Dieser Dokumentauftrag erneuert weder ein
laufendes Budget noch eine blockierte oder pausierte Automatik.

**Geprüfte Ausgangsbasis.** Das eindeutig zugeordnete saubere Result
`specroad-apply_Result_163544_1026_0a669e.zip`, SHA-256
`83253d84ee6442a209a6e8d384325565191cca1079c09558f2bbedec65d90ffd`,
bestätigt das zuvor übergebene Bundle **497**, Paket-SHA-256
`b40b8c66582b9edab03ff38f00724914618cce806e9afc9c240b68335fb2a4d9`.
Der tatsächliche Abschlusscommit ist
`54049d34312aded9b2afd6e56097600063760678`, Parent
`f8ac3ad362a0eee777e4b228e950e9c33f93840a`, mit exakt dem OFF-PLAN-Commit
**RESTORE-JOURNAL-SELECTION**. Repository-ID
`a33ed6cf-0a97-4b73-b11a-d4239e7a2145`, Fingerprint
`7c9d2a24e397e0e5` und Algorithmus `patchharbor-state-v1` stammen unverändert
aus diesem neuen Result. Generierte Root-Anleitung, Kontext, Umgebung,
Manifest, Run-/Ausführungslogs, alle **2.292** Snapshotdateien samt
Blob-IDs/Modi, tatsächlicher sauberer Apply-Stand, Paketbytes und gebundene
Testreceipts wurden geprüft. **7.202/7.202** Tests bestanden mit vier
parallelen Workern, **Sequenz 203 / Gruppe 2**, in **2456.49 s**.
Produktstand **648/900**, zuletzt **15.k.C**, nächstens **15.l.W**, und
Bundle **497** stimmen mit den tatsächlichen Commitdateien überein.

**Abgleich und Entscheidung.** Spezifikation **0.2.30**, 2.1 und 2.4.1–2.4.4,
die ursprünglichen Verfahrensabnahmen von Bundle 389, die anschließenden
Klärungsbelege sowie die aktuelle lokale Test-/Übergabepolicy wurden
abgeglichen. Eine nachträgliche Erweiterung aller alten Aufträge oder ein
Reset bei Neustart würde der ausdrücklichen Bestands- und Budgetgrenze
widersprechen; ein bloßes Ersetzen von „eins“ durch „drei“ ließe Verbrauch,
Fehlerfälle und Versionswechsel offen. Gewählt ist deshalb exakt die
beauftragte versionierte Dreierregel mit typisierten Vertragsfeldern,
dauerhaftem einmaligem Verbrauch und ausschließlich belegtem normalem
Abschluss als Reset-/Übergangsgrenze. Bestehende fachliche Grenzen,
menschliche Produktfreigaben, Reviews, Risikoentscheidungen und Nachweise
werden nicht abgeschwächt.

**Normative Fortschreibung und Erhaltung.** Spezifikation **0.2.31 / 2.4.3**
enthält die Regel vollständig. Die grundlegende Delegation, die zulässigen
fachlichen Entscheidungen nach 2.4.1, Entscheidungsbelege nach 2.4.2 und
Blocker-/Erhaltungsregeln nach 2.4.4 bleiben erhalten; letztere drei Abschnitte
bleiben bytegleich. Die folgenden Abnahmen konkretisieren ausschließlich
das externe Entwicklungsverfahren. Die früheren Abnahmen aus Bundle 389
bleiben als Vertrag-2-Nachweis lesbar und werden nicht als bereits
beobachtete Vertrag-3-Ausführung ausgegeben. Historische Evidence,
Reviewentscheidungen, Quell- und Paketnachweise bleiben unverändert.
Es entstehen keine neue Requirement-ID und keine reguläre Produktposition.

**Verbindliche Abnahmen für Control-Vertrag 3.** Diese sind überprüfbare
Verfahrenskriterien, keine in diesem Bundle ausgeführten Control-Tests:

1. Ein Vertrag enthält tatsächlich `version=3`, `clarification_limit=3`,
   einen ganzzahligen Restwert von 0 bis 3 und ein Boolean für
   `clarification_allowed`. Strings, Boolean als Ganzzahl, fehlende Felder,
   andere Limits, Werte außerhalb des Bereichs und Restwert 0 mit `true`
   gestatten keine automatische Klärung. Es gibt keinen stillen Default,
   keine Vertragsreparatur und keinen Fallback auf eine andere Version.
2. Nur ein gültiger Vertrag mit `true` und positivem Restbudget erlaubt
   innerhalb der unveränderten fachlichen Grenzen eine automatische
   Klärungsübergabe. `false` sperrt sie auch bei Restwert 1, 2 oder 3.
   Der Agent darf das dauerhaft verwaltete Budget nicht selbst erhöhen.
3. Je Auftrag und Quell-Result entsteht höchstens eine nativ geprüfte,
   vierfach gebundene kanonische ZIP mit korrekten Quell-/Paket-SHAs und
   `status=spec_clarification`. Der Auftrag endet sofort nach atomarer
   Übergabe; keine eigene Apply-/Warte-/Modellschleife. Der normale
   Planschritt bleibt offen.
4. Bei Übernahme des zugeordneten Folge-Results jeder klassifizierten
   Klärungsübergabe sinkt das Restbudget genau einmal um eins, auch bei
   Apply-Fehler. Wiederholte Übernahme verbraucht nicht doppelt und füllt
   nichts auf. Eine unklare Result-/Paketzuordnung begründet keinen
   erfolgreichen Abschluss oder Folgeauftrag.
5. Nur erfolgreiches sauberes Apply mit passendem Abschlusscommit und
   verbleibendes Budget erlauben einen neuen freigebenden Auftrag für die
   nächste Klärung. Bei drei so getrennt übergebenen Klärungen verläuft
   das Budget **3 → 2 → 1 → 0**. Danach bleibt klare reguläre Umsetzung
   erlaubt; eine vierte Klärung ist gesperrt. Fehlendes, fehlerhaftes oder
   unsauberes Apply sowie fehlender/falscher Abschlusscommit erlauben auch
   bei positivem Restwert keine weitere Klärung. Wenn weitere notwendige
   Klärung gesperrt ist, folgt `blocked` mit konkreter Frage und Empfehlung.
6. Nur ein als `patch_ready` klassifiziertes Bundle mit echter regulärer
   Umsetzung oder technischer Korrektur eröffnet nach erfolgreichem sauberem
   Apply und passendem Abschlusscommit erneut drei Plätze. Reine Klärung,
   kosmetischer Reset, Alibi-Commit, Fehler oder unklassifizierte Übergabe
   tun dies nicht. Eine bloße Antwortklassifikation ersetzt keine Prüfung
   des tatsächlichen fachlichen Inhalts.
7. Retry, Overload, Pause, Neustart und Recovery erhalten das dauerhaft
   gespeicherte Budget. Alte Aufträge und Version 2 behalten die Einerregel;
   ihre Antworten, Blockaden und Belege werden nicht umgeschrieben. Eine
   alte Kette wechselt erst nach dem belegten erfolgreichen normalen
   Abschluss gemäß 2.4.3 in einen neuen Vertrag 3. Dieser Dokumentcommit
   allein erlaubt weder den Wechsel noch das Auffüllen.
8. Die Grenzen aus 2.4.1, Entscheidungsbelege aus 2.4.2 und echte Blocker nach
   2.4.4 gelten für jede der drei möglichen Klärungen einzeln. Fehlende
   unverzichtbare externe Fakten, menschliche Freigaben oder unauflösbare
   fachliche Konflikte werden weder durch Budget noch Vertragsversion ersetzt.

**Offene Nachweise und Umfangsgrenze.** Diese Dokumentfassung implementiert
kein Control-, Watcher- oder Produktverhalten. Dauerhaftes Budget, Retry-,
Fehler- und Übergangsfälle sind erst durch die jeweiligen eigenständig
beauftragten externen Läufe nachgewiesen. Bestehende Blockaden und alte
Antworten bleiben erhalten. Keine Dienste, Konfigurationen oder Laufzeitdaten
werden verändert; kein Apply oder Fortsetzen einer Automatik wird gestartet.
Alle regulären W/R/C-Checkboxen, **648/900** und **15.l.W** bleiben unverändert.
Die bestehende parallele Apply-Testrotation **N=3** bleibt vom hiervon
unabhängigen Klärungslimit 3 getrennt. Dokumentversion und aktive
Kataloghashbindungen werden gemeinsam fortgeschrieben; keine neuen
Dokumentationstests und kein zusätzlicher Volltest.


**Dokumentübergabe und Commit-Gate.** Genau ein echter OFF-PLAN-Dokumentcommit,
keine künstliche W/R/C-Folge. Produktcode, Tests, Fixtures, Oracles,
Testnummern, Runner, Workflows, lokale Regeln und historische Evidence
bleiben bytegleich. Geändert werden Spezifikation, Plan und ausschließlich
die aktiven Spezifikationshashfelder der **743** Katalogdateien.

Vor diesem Dokumentcommit prüft der externe Entrypoint genau **Sequenz 204 /
Gruppe 0 von 3**, **7.202 Tests**, mit vier parallelen Workern. Erst nach
Erfolg setzt er den Offplan-Marker und die Bundle-Nummer **498**. Produktzähler
und reguläre W/R/C-Checkboxen bleiben unverändert. Fehler erhalten den
tatsächlichen Zustand und vorherige Commits. Die geplante Übergabe ist
`spec_clarification`, kein als Umsetzung ausgegebener Budget-Reset. Nach
nativer ZIP-Prüfung und atomarer Exchange-Veröffentlichung endet der Auftrag.

**Beobachtete gezielte Dev-Prüfung.** Die Dokument- und Katalogfassung
besteht **54/54** bestehende Verhaltenstests aus `tests/test_catalog_check.py`
und `tests/test_catalog_check_right.py` in **6.54 s**, mit **vier
parallelen Workern**, CPython **3.14.4**, Exit **0** und ausschließlich
`passed`-Einzeloutcomes. Ausgeführt wurde `tools/run_selected_tests.py
--workers 4 --expected-tests 54` mit den beiden genannten vollständigen
Dateien in einem frischen ignorierten Berichtsroot. Geprüft werden die von
der Spezifikationshashbindung betroffenen maschinenlesbaren Katalog- und
Auswahlverträge; keine Dokumentation, Darstellung oder externe Control-Ausführung.

Die vollständige Collection-/Katalogprüfung bestätigt **21.604** aktive
Tests, **0** Katalogfehler, Exit **0** und **0** ausgeführte Testkörper.
Die **21.608** dauerhaft reservierten Nummern einschließlich vier historisch
entfernter Identitäten bleiben bytegleich. Produktcode, Testdateien,
Fixtures, Oracles, Runner, Workflows und historische Evidence ändern sich
nicht. Die **743** aktiven Katalogdateien ändern ausschließlich
`specification_sha256`; einschließlich Spezifikation und Plan sind es
**745** geänderte Bestandsdateien, keine neuen Produktdateien oder Löschungen.

Gebundener Entwicklungsquellhash:
`ee9f13fd252ca62e2b6f843580c733ed9ff569b42c248a00d36220a75be23ff2`;
Katalogvertrag-SHA-256:
`b0275a46bc71aa58e877d2dee580a83868b9753de57c15d42022f28835dd0095`;
Auswahlbericht-SHA-256:
`5e461b418e6130c0928c2bfbdda93774850447df9d261f23076e5942dda649fb`;
Einzeloutcomes-SHA-256:
`d0aa0e6393a9cf9bc241e7975134b9f28c85aeb728ef68a28ea7d538a5929177`.
Dies ist ausdrücklich eine Teilprüfung mit `full_suite_passed=null`;
kein vollständiger oder serieller Testlauf und kein Releasebeleg.

Der bestätigte vorherige Apply-Nachweis für OFF-PLAN
RESTORE-JOURNAL-SELECTION ist davon getrennt:
Auswahlbindungs-SHA-256 `6b22b40f3e0be7a6f770e0d6e8d31f06b1ca99d9ea02688a0c48b981e5b14d9d`,
Bericht-SHA-256 `0ee893e39fcff23d24be07e855d8947a67d17c2ecfae4f7fb2bbe57bb8ec1b6f` und
Einzeloutcomes-SHA-256 `b2e088aa833cf0883ef20f9421e483edb3c659fb9a8776a9e47881a2b768bc42`.
Die vorgesehene neue Apply-Gruppe und der OFF-PLAN-Commit sind bei dieser
Übergabe noch nicht ausgeführt. Native ZIP-Prüfung und atomare Veröffentlichung
beenden den Einzelauftrag; 15.l.W bleibt offen.
