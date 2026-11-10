# CONTROL-BUDGET-RESET-661

10. November 2026; ausdrücklicher Nutzerauftrag, keine delegierte oder
automatische Budgetänderung. Gewünscht sind die Freigabe der noch notwendigen
18.h-Detailklärung, drei neue Plätze und anschließend die Wiederaufnahme.
Die installierte CLI kann bislang nur erhaltene Budgets übernehmen. Der
bereits akzeptierte und paketlos blockierte Stand darf nicht überschrieben werden.

Gewählt: `accept-current --clarification --reset-budget --reason ...` über
einen neuen erfolgreichen Apply-Nachfolger. Ein Version-2-Betreiberbeleg
erhält Vorvertrag und alte Versuche und bindet die ausdrückliche Erneuerung.
Direkte SQLite-Umschreibung oder erneutes Seeden der Historie sind verworfen:
Sie würden die tatsächliche frühere Befugnis verfälschen. Ein automatischer
Reset bei jedem Neustart wäre ebenfalls nicht beauftragt. Normative Regel:
[Spezifikation 2.4.3.5](../../specification/SpecRoad_Spezifikation.md).

W: vollständige CLI-/Beleg-/Übernahmeanbindung für den ausdrücklich erneuerten
V4-Vertrag und positive Abnahmen einschließlich erhaltenem Vorvertrag und
null Restplätzen. R: Fehlbedienung, fehlende/falsche Capability, Wiederholung,
manipulierte Belege und bestehende Stop-/Aktualitäts-/Konkurrenzgrenzen prüfen.
C: Resetvertrag und Capabilityprüfung aus dem bestehenden Übernahmeweg lösen,
ohne Verhalten, Feldmengen oder Gates zu ändern.

Commit-IDs: CONTROL-BUDGET-RESET-661.W, .R, .C; getrennte Apply-Gates.
Produktposition bleibt 750/900, nächster Schritt 18.h.W. Dessen Speicherregel
wird hier nicht entschieden; die ausdrücklich freigegebene Klärung gehört zum
anschließenden Automatikauftrag. Dev führt keine Verhaltenstests aus. Nach
erfolgreichem Apply: geprüfte Control-Version installieren, Betreiberbeleg
mit der hier erteilten Freigabe vormerken, Start/Resume ausdrücklich ausführen.
Originale, alte Results, laufende Fremdarbeit und Benutzerkonfiguration bleiben.
