# Grundlagen und Rangfolge

Übernommene fachliche Planbasis. Frühere Verträge und historische Ausgangszustände behalten ihre damalige Bedeutung; die aktuelle optionale Klärung folgt SPECROAD-DECISION-1, Vertrag 4 und verification/development_contract.json.

[Zentraler Fortschritt](../SpecRoad_Implementierungsplan.md)

## Verbindliche Grundlagen und Rangfolge

Fachliche Grundlage ist [`docs/specification/SpecRoad_Spezifikation.md`](../../specification/SpecRoad_Spezifikation.md), einschließlich aller konsolidierten Korrekturen, 742 Requirements, 51 Verifikationsverträge, 46 Szenario-/E2E-Identitäten sowie R-01 bis R-75, Anhang U und den PatchHarbor-Rundweg aus Anhang W. Der [`Prüfbericht`](../../reviews/SpecRoad_v0.2.7_Implementierungsreife_Pruefbericht.md) ist ein vorgelagerter Entwurfsreview, kein späterer Produktnachweis.

Gebundene Spezifikations-SHA-256: `fa3e492d18aaff24d9b22cd5c31a554a65173232c6d55a6147d526ed4fb81a09`.
Planungsbasis: Commit `fe2661d02ecf2f7eb483b58a4487eb009c6b3846`; sauberes Result-Bundle `specroad_Result_120209_0914_df3504.zip`; Repository-ID `3d2576df-d611-46fc-9d2b-92869468aaca`. Diese Angaben dokumentieren die Entstehung des Plans, nicht die zukünftige Patchbindung. **Jedes spätere Patchpaket bindet den dann aktuellen tatsächlichen Result-Zustand.**

Die ausdrücklichen Nutzerentscheidungen TD-001 und BD-001 vom 14. September 2026 gelten zusätzlich und bei den nachfolgend benannten Konflikten vorrangig. Sonstige normative Spezifikationsinhalte werden nicht stillschweigend abgeschwächt. Neue fachliche Widersprüche, fehlende zwingende Angaben und Sicherheitsprobleme sind offen zu benennen, nicht durch erfundene Annahmen oder Scheinerfolge zu lösen.

Die ausdrücklich erteilte Entwicklungsbefugnis **SPECROAD-DECISION-1** aus
Spezifikation 2.4 gilt zusätzlich für begrenzte Detaillücken im bestätigten
Auftrag. Der Dev-Agent entscheidet zulässige Fälle selbst, dokumentiert
Alternativen, Begründung und Abnahmekriterien vor der Umsetzung und führt
die offene Planarbeit nach dem gebundenen Apply fort. Diese Befugnis darf
weder Produktfreigaben ersetzen noch Scope, Sicherheit, Kompatibilität,
W/R/C oder TD-001 abschwächen. Wirklich außerhalb dieser Grenzen liegende
Entscheidungen bleiben mit konkreter Frage und Empfehlung blockiert.

Für die Begrenzung automatischer Klärungsübergaben gilt zusätzlich der
ausdrückliche Nutzerauftrag **SPECROAD-DECISION-1-V3** vom 26. Oktober 2026
nach **2.4.3** und dem folgenden OFF-PLAN-Abschnitt: Unter gültigem Vertrag 3
sind höchstens drei aufeinanderfolgende Klärungsbundles mit dauerhaftem
Restbudget zulässig; **Version 2 behält die Einerregel**. Ein automatischer Wechsel alter
Ketten erfordert erst den belegten erfolgreichen normalen Abschluss; die
ausdrückliche Bedienausnahme aus 2.4.3.2 bleibt zusätzlich anwendbar.
Produktfreigaben und die Grenzen aus 2.4.1/2.4.2/2.4.4 bleiben unverändert.
Dieser Plan ändert keine alten Aufträge, Antworten, Blockaden oder
Laufzeitdaten und ist keine Start-/Resume-Anweisung.
