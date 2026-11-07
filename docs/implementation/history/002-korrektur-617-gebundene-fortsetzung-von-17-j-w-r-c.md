# Korrektur 617 — gebundene Fortsetzung von 17.j.W/R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrektur 617 — gebundene Fortsetzung von 17.j.W/R/C

Maßgeblich ist das nativ geprüfte Fehler-Result `specroad-apply_Result_024957_1106_83bbf2.zip`,
SHA-256 `e1672a45d0db6f2e3a4c9059234746a027150664548cc78105e811d8f229c993`, HEAD `125e0a9ec51ab630c299c71845de659ae3c56d0f`,
Fingerprint `e0ffe7718a51fb57`. Der Klärungscommit
MERGE-TARGET-616 wurde als 125e0a9ec51ab630c299c71845de659ae3c56d0f
nach 7016 bestandenen Tests committed. 17.j.W scheiterte vor seinem Commit
mit einem Fehler und 9559 bestandenen Tests; 17.j.R/C wurden nicht ausgeführt.
Der vollständige erhaltene W-Arbeitsstand ist die technische Korrekturbasis.

Belegter Fehler: `test_bound_target_project_policy_controls_real_profile_warning[info-False]`
endet in `FailPolicy` mit `ResultContractError: Unsupported fail threshold`.
Die vorhandene native ProjectConfiguration samt veröffentlichtem JSON-Schema
akzeptiert `validation_policy.fail_on=info`; die gemeinsame Diagnostikbewertung
und ihr Ergebnis-Schema hatten diesen Wert noch ausgeschlossen. Der bereits
committede Vertrag 10.15.7 verlangt gerade die Bewertung nach dieser Zielpolicy.
Dies ist eine technische Inkonsistenz, keine neue normative Detailentscheidung.

W/R/C erhalten dieselbe gezielte Korrektur: Die gemeinsame Bewertung unterstützt
die bestehende Schwerefolge error, warning, info auch als Projektschwellwert.
Ein info-Schwellwert blockiert jeden vorhandenen Befund, aber keinen vollständigen
befundfreien Check. Strict darf die strengere info-Policy nicht abschwächen.
Unvollständigkeit und unabhängige Fehlercodes bleiben vorrangig; beobachtete
Schweregrade und native Originalberichte bleiben unverändert. Das gebundene
model-validation-v1-Ergebnis kann den tatsächlich verwendeten info-Wert abbilden.
Die CLI-Optionsdefinition `--fail-on error|warning` bleibt bytegleich; vorhandene
Parser-/Optionsregressionen schützen weiterhin diese explizite Grenze.

Die vorhandenen stabilen Testidentitäten werden um echte native Info-/Leerbefund-
Projekte, Schemaabnahme und die vollständige Schwere-/Strict-Matrix ergänzt.
Der ursprünglich fehlgeschlagene Test und sämtliche ursprünglichen Pflichtdateien
bleiben erhalten. Alle Diagnose-, Modellbewertungs- und Optionsregressionen sowie
betroffene Change-/Migrationspfade gehören zusätzlich in jedes Apply-Gate.
Keine Quell-/Zielvalidatoren werden gemockt und keine Akzeptanz abgeschwächt.
Spezifikation und Klärungsabnahmen bleiben unverändert; keine neue Klärungsstage,
keine Budgetänderung. Die offenen IDs und Rollen 17.j.W/R/C bleiben vollständig.

Jeder Zwischenstand wird erst nach seinem eigenen N=3-plus-Pflichtauswahl-Gate
committed. Der fehlgeschlagene W-Versuch behält Gruppe 0; danach folgen 1 und 2.
Planfortschritt wird nur durch erfolgreiche Commits wirksam. Dev führte keine
Verhaltenstests aus. M17, Transaktions-/CLI-/Work-Integration in 17.k–17.l und
menschliche Freigaben bleiben offen; dieser Nachweis ist keine Produktfreigabe.
