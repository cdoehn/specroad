# Bundle 706 — MOVE-Abnahme an den veröffentlichten Versuch binden

Nutzerauftrag vom 15. November 2026: das fehlgeschlagene Bundle 705 reparieren.
Maßgebliche Quelle ist das native Fehler-Result mit SHA-256
`cf68a70061a7a541dd693162bdd90e516a25f82d8d0395e37bd374bec3c3d386`.
18.t.R ist auf `dbcaaf71ccde2f5884caba9c6ca2aef347845249` mit 8.348
bestandenen Tests committed; 18.t.C folgte auf
`42f0aabafc97248b613474b52791cf3bd5ee567f` mit 8.423 bestandenen Tests.
Die Schreibbelegreparatur aus [Bundle 705](bundle-705-native-validation-receipt.md)
ist damit abgenommen. Beide erfolgreichen Commits bleiben erhalten.
Produktfortschritt: 768 von 918; die nächste Produktposition bleibt 18.u.W.

TEST-OVERHEAD.W scheiterte mit acht Fehlern bei 7.534 Tests; 7.526 bestanden.
R und C dieser Optimierungsgruppe wurden noch nicht ausgeführt. Der native
Arbeitsbaum stimmt vollständig mit dem angekündigten W-Zustand überein.

Alle acht Fehler sind `StopIteration` beim sofortigen Lesen des gw0-Tokens
in den MOVE-Integrationstests. Ein vom Worker geschriebener Phasenmarker
beziehungsweise das Ende des anfänglichen Zielworkers bestätigt nicht,
dass der Controller den nächsten externen Status bereits veröffentlicht hat.
Seit der angekündigten 500-ms-Bündelung kann der gelesene Snapshot noch keine
aktuelle Versuchsliste enthalten. Der Fehler entsteht vor dem MOVE-Auftrag.
Auch ein beliebiger vorhandener Versuch ist kein Nachweis für den Quellworker.

Der gemeinsame Testhelfer wartet innerhalb der bestehenden begrenzten
Prozessbeobachtung auf genau den laufenden Quellversuch: gw0, gebundener
Quellhost und vollständige Testidentität. Er liefert Lauf-Snapshot und Token
aus demselben Lesen. Fehlender Status und eine noch leere Liste bedeuten
weiterhin fehlende Beobachtung; Prozessende, Mehrdeutigkeit oder Fristablauf
werden nicht als Erfolg ausgegeben. Keine längere Frist, kein fester Sleep,
keine erzwungene Statuspublikation und keine künstlich erzeugten Versuchsdaten.

Die Korrektur gilt für alle MOVE-Auftragspunkte beider Integrationsdateien,
einschließlich lokaler und Proxy-Worker, Setup/Call/Teardown, fehlender
Abbruchbestätigung, belegtem Ziel, gewöhnlichem Abschluss während Abbruch
und echtem Call-Fehler. Sämtliche vorhandenen IDs, Parametervarianten und
fachlichen Assertions bleiben erhalten: echte Prozessbeendigung, frische
Fixtures, getrennte dauerhafte Versuche, vorhandene Messphasen, unveränderte
Gate-Nachweise und kein unzulässiger Wiederholungsversuch. Die positive
MOVE-Abnahme mit langer vollständiger Testidentität nutzt denselben Helfer.

Die vollständige offene Folge TEST-OVERHEAD.W, TEST-OVERHEAD.R,
TEST-OVERHEAD.C behält IDs, Rollen und exakte Commitnachrichten. Jede Stage
erhält weiterhin ihr eigenes gefiltertes N=3-Gate plus die vollständige alte
Pflichtauswahl aller Hostbudget-, Status-, Scheduler-, MOVE- und Kopietests.
Die drei Optimierungen bleiben unverändert: kein erneutes Budget-fsync für
unveränderte gültige Budgets, gebündelte externe Statussnapshots mit sofortigem
Abschluss und nur entscheidungslokale Prognosewiederverwendung.

Keine neue Produktlogik, neue Testnummer, Spezifikationsklärung oder
Budgetänderung. C behält die reine Auslagerung der Schedulerberechnung.
Dev prüft nur Syntax, reine Collection und das native gebundene Paket.
Die Abnahme der drei Optimierungsstufen steht aus; Control bleibt pausiert.
