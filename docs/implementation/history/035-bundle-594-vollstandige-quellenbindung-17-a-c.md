# Bundle 594 — vollständige Quellenbindung 17.a.C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Bundle 594 — vollständige Quellenbindung 17.a.C

Maßgebliche technische Basis: natives erfolgreiches sauberes Result
`specroad-apply_Result_012305_1105_26449d.zip`, SHA-256
`2971bf4c3f85e492ab50120632631c48ac20f74c3a5514a00928a65eba7efdf9`, Abschlusscommit
`ce015ce3544a2a0ae96d813dc8d9cd6de6f917bd`. Die drei OFF-PLAN-Stufen
CONTROL-RECOVERY-593.W/R/C sind im Result mit erfolgreichen eigenen Gates
und echten Commits belegt. Die nächste offene Produktposition ist 17.a.W.
Vertrag 4 erlaubt hier keine neue Spezifikationsklärung. Der bestehende
Quellvertrag aus §§ 10.15, 12.27 und SR-REQ-0361 bis 0364 genügt für 17.a;
Spezifikation und Entwicklungsbefugnis werden nicht verändert.

W bindet alle vier Quelltypen in allen drei Rollen an tatsächliche vollständige
Bytes, Projekt-/Schemaidentität, ScopeDescriptor, Modellwurzel und Provenienz.
Lokale Quellen verwenden ProjectBundleSnapshot; Git bleibt bei gebundenen
Commit-/Tree-/Blobobjekten; Baselines verwenden ihre verifizierten Originale;
Vollbundles verwenden native Container-, Receipt- und Modellprüfung. Registry,
Sprachpakete, referenzierte Archive und Binäranhänge gehören zum Quellbestand.

R ergänzt typisierte Selektoren, Fremdprojekt-/Versions- und Partialgrenzen,
erhaltene Extraktionsnachweise auch in Git, konfigurierte Baseline-Abweisung,
archivierte effektive Profilketten ohne Konfigurationsumschreibung sowie
abschließende Beobachtung aller drei Quellen. Ein später bewegter Git-Ref
ändert den gebundenen Commit nicht. Qualifizierte Legacy-Originalbytes bleiben
exakt erhalten. Keine heimliche Migration, Ersatzquelle oder Schreibfreigabe.

C trennt die bereits vorhandene vollständige Registry nach `snapshots/` ab;
`merge/` kombiniert deren Quellen. Die nativen M8/M10/M15-Prüfer bleiben
wiederverwendet; beide W/R-Testdateien bleiben bytegleich. Interne
Quellenbindungen sind kein neu eingeführtes normatives Mergeplanformat.

Vorbereitet sind genau die drei vollständigen zusammenhängenden Positionen
17.a.W/R/C mit eigenen Apply-Gates. Stand dieser Stage: 17.a.C,
Folgeposition `17.b.W`. Der Fortschrittsblock und die Checkboxen sind
Commitzielzustände: Sie gelten erst nach bestandenem Gate und echtem Commit;
ein bloß materialisierter Fehlerstand beweist keinen Abschluss.
Dev hat **keine Verhaltenstests** ausgeführt. Syntax, reine Collection und
native Paketvalidierung ersetzen weder Apply noch Release-/Matrixnachweise.
SR-TC-0361 bis 0364 bleiben wegen der nachfolgenden Mergearbeit ausdrücklich
teilweise umgesetzt. 17.b beginnt die eigenständige versionierte Planinventur;
Mergeplanung, Konfliktentscheidungen und Veröffentlichung werden durch dieses
Quellenbundle nicht vorweggenommen. Der vorhandene Scope bleibt erhalten.
