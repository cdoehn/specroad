# MERGE-WORK-627 — vollständige passive Merge-Vorbereitung

7. November 2026 · 17.l · delegiert gemäß SPECROAD-DECISION-1, Vertrag 4.

Ausgangsbasis ist das native saubere Result mit SHA-256
`1b261d7b928893600effc8ea10355c803c5e9a3450dc6195b0a0a64b4e4bd2d0`, HEAD `2d073d1f4e95ad6705ce3def1237c8af73e33584`. Bundle 626 schloss seine technische Korrektur erfolgreich
ab; der belegte Produktstand ist 17.k.C, 726/900. Die aktuelle Freigabe erlaubt
eine optionale Klärung bei Restbudget 2. `verification/development_contract.json`
bestätigt Vertrag 4. Keine eigene Änderung dieses Budgets.

**Lücke.** 10.15.8 verlangt die öffentliche CLI-/Work-Gesamtintegration in
17.l; native Quellen, Konflikte, Metadaten, Zielprüfung und Writer sind vorhanden.
Die genaue passive Ergebnis-/Eingabebindung und CLI-Zuordnung der vier
Quellenadapter zu Work waren noch nicht festgelegt. Anhang P verlangt
vollständige Eingaben, Fortschritt, unveränderte Engineverträge und globale Gates.

**Alternativen.** Einen vollständigen Merge bei jedem Resume erneut beginnen
würde P.5 verletzen. Einen zweiten Mergealgorithmus im Work-Store einzuführen
würde Parität und Wartung unnötig erschweren. Gewählt ist ein geschlossener
passiver Adapter über die vorhandenen nativen Phasen und den vorhandenen Store,
mit Originalbytes und expliziter abschließender Nachrechnung. Neue Felder und
Quellenoptionen werden in 10.15.9 versioniert; bestehende Formate bleiben gültig.

**Grenzen.** Kein neuer fachlicher Scope, keine erfundene History, kein
gespeicherter Callback, keine neue menschliche Freigabe, keine Lockerung von
Closure, Prüfung, Publication oder Recovery. Vier Quellenadapter behalten ihre
unterschiedliche Herkunft; Parität betrifft Fachwerte und Zielbytes, nicht
absichtlich herkunftsgebundene IDs. Die Ergänzung ist additiv rücknehmbar;
historische Belege und Produktdaten bleiben erhalten. Keine unverfügbaren
externen Fakten sind für diese Detailregel erforderlich.

**Abnahme.** Native lokale/Git-/Baseline-/Vollbundle-Eingaben liefern gleiche
Fachwerte. Synchroner Lauf und verschieden partitionierte Work-Aufträge müssen
gleiche vollständige Originalplan-, Konflikt-, Metadaten- und Zielbytes ergeben.
Ein ungültiges Ziel behält seine negativen Befunde. Geänderte Originalbytes,
fehlende Workobjekte, umgehashte Phasenresultate, nicht zusammenhängender
Fortschritt und inkompatible Engine-/Toolstände dürfen kein Ergebnis freigeben.
Das normative Projekt bleibt unverändert. Tests verwenden kleine vollständige
native Daten; bestehende Größen-/Publikationsreferenzen bleiben Pflicht.

**Phasen.** 17.l.W integriert die vollständige passive Vorbereitung einschließlich
aller Quellenarten, externer Checkpoints und öffentlichem `merge plan`.
17.l.R bleibt die Vervollständigung einschließlich öffentlichem Merge-Apply,
portabler CLI-Gesamtintegration, vollständiger Fehler-/Manipulations- und
Resume-Paritätsabnahme gemäß 10.15.8 und Anhang P. 17.l.C parametriert danach
die gemeinsame Matrix. Keine Position wird verkürzt, gestrichen oder vorab als
bestanden erklärt. Der Klärungszustand selbst verändert keine Produktzähler.
M17-Abschluss und erforderliche Plattform-/Gesamtnachweise bleiben gesonderte
Gates; Collection ist keine Verhaltensabnahme.
