# MERGE-CLI-633 — geprüfte Übergabe vom passiven Merge zum Writer

8. November 2026 · SPECROAD-DECISION-1 / Vertrag 4 · Planrevision 112.

Basis ist das erfolgreiche saubere Result
`c96c954fbce51828061d9add226e5995ac1d80da119f94be4cfb43785bea4750`,
HEAD `64930b8f34f17e3171a84d705298ce3b1b2e2ce0`.
632 ist abgeschlossen; der Produktfortschritt bleibt 727/900, nächster Schritt
17.l.R. Der gelesene Entwicklungsvertrag erlaubt einen optionalen
Klärungspräfix mit anschließender Umsetzung; der aktuelle Control-Auftrag
meldet `clarification_allowed=true`, Restbudget 2. Keine Budgetänderung.

**Notwendige Detaillücke.** 10.15.8 spezifiziert den nativen Publication-Writer,
10.15.9 den passiven Vorbereitungs-/Work-Vertrag. Die genaue öffentliche
Übergabe, die Dateiart von `merge apply` und die Wiederholung nach verändertem
Ours sind noch nicht festgelegt. Ein beliebiges Format oder eine neue
Idempotenzregel in Produktcode würde diese Normlücke verdecken.

**Alternativen und Entscheidung.** Einen semantischen Konfliktplan bei jedem
Apply neu aufzubauen würde einen wiederholten Aufruf nach eigener Publikation
an verändertem Ours scheitern lassen. Ein zweiter Writer oder neue beschreibbare
Work-Transaktionen wären unnötig und riskanter. Gewählt ist der kleinere
additive Adapter: `merge plan --for-apply` erzeugt den vorhandenen vollständigen
nativen Change-Plan, wahlweise aus einem fertig geprüften passiven Work-Auftrag;
`merge apply` liest genau diesen Plan und nutzt die bestehende native
Request-Quittung, Backup-, Sperr-, Validierungs- und Recovery-Kette. Die
unveränderten passiven Daten behalten ihren eigenen Schemavertrag; nur die
Command-Schemaauswahl umfasst zusätzlich den neuen Plan-Resulttyp.

**Grenzen.** Keine automatische Pfadumbindung, Freigabe, Quellenannahme,
Request-ID-Umdeutung oder neue Scopeentscheidung. Explizite menschliche
Reviews, native Spezialistengates und reale aktuelle Code-/Evidenceprüfungen
bleiben verpflichtend. Ursprüngliche Parameter und Historie bleiben Daten,
keine ausführbaren Callbacks. Die Erweiterung ist additiv reversibel; keine
historischen Belege werden umgeschrieben. Das öffentliche Verhalten ist in
10.15.10 normiert, alle aktiven Katalogbindungen werden auf die neue Spec
umgebunden. Die Abnahmen stehen in M17; keine Tests im Dev.

**Stufen.** Genau dieser OFF-PLAN-Präfix zuerst, anschließend der vollständige
Rest 17.l.R und 17.l.C mit getrennten Apply-Testgates. Kein erfolgreicher W-
oder OFF-PLAN-Commit wird wiederholt. Der M17-Gesamtnachweis und die
Plattformfreigaben bleiben eigenständige Gates und werden nicht erfunden.
