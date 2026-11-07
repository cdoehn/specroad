# MERGE-RELATIONS-606 — gebundene Herkunft und vollständiger Schritt 17.e

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## MERGE-RELATIONS-606 — gebundene Herkunft und vollständiger Schritt 17.e

Autorität: delegiert gemäß SPECROAD-DECISION-1, 2.4.1/2.4.2/2.4.3.1 und
aktuellem Control-Vertrag 4 mit Klärungsfreigabe. Keine persönliche Review-
oder Risikoakzeptanz wird behauptet. Quell-Result SHA-256:
`d24fdc9b741de1c0f5441c7143a8940c6226b33c7847f048a5ec466daadeca80`,
sauberer HEAD `c550cf1a892cb05ff803e3b85f24ac3b5434d66b`. Die drei
OFF-PLAN-605-Gates mit 7737, 7766 und 7756 bestandenen Tests und ihren echten
Commits sind im Result belegt. Der Produktstand bleibt 705/900, 17.d.C.

Lücke: 17.e verlangt gemeinsame Identitätshistorie; HistoryOrigin und
HistoryObservation sind bereits reine, ausdrücklich vom Aufrufer gebundene
Beobachtungen. Es fehlt die genaue Zuordnung solcher Beobachtungen zu den
drei vollständigen nativen Quellen und normativen Ressourcen. Geprüft wurden
17.e/17.f und Folgeschritte, SR-REQ-0368/0370, 10.15.1/2, K.3, native
Quellinventur, Relation-/Identitätswerte und neutrale Historyvergleiche.

Alternativen: gleiche IDs/Bytes/Zeitstempel als Herkunft erraten; beliebige
neue Historienpersistenz in Projekte einführen; oder bestehende explizite
Herkunftsbeobachtungen an vollständige Quellbindungen und native Identitäten
binden. Gewählt ist der dritte Weg: kleinster lesender Anschluss, fehlende
Herkunft bleibt ungeklärt, widersprüchliche Herkunft kollidiert. Er authentifiziert
keinen erfundenen Ursprung und ersetzt den späteren Herkunftsprovider nicht.
Für die öffentliche CLI bleibt tatsächliche Ancestry/Provenienz erforderlich.

Grenzprüfung 2.4.1: ausschließlich bestätigter 17.e-Scope; keine vorgezogene
CLI oder Architekturänderung; bestehende History-, Original-, Review- und
Writerschutzregeln bleiben; keine Projektbytes/Altformate ändern sich; die
additive API/Norm kann versioniert zurückgenommen werden; keine externen
Fakten werden angenommen. Synthetische Erzeugungsereignisse sind als solche
ausgewiesen. Native Quellhashes werden aus echten Quellen berechnet.

Die normative Regel steht zuerst in 10.15.3 und aktiven Katalogbindungen.
W liefert vollständige Relation-ID-Zuordnung, unabhängige Ergänzungen,
Quell-/Herkunftsbindung und gemeinsame Identitätsprüfung. R vervollständigt
explizite Entfernung gegen Änderung, Besitzer-/Erstellungsmetadatenschutz,
Legacy-Schutz und manipulierte Eingaben. C trennt gemeinsame Identitätsprüfung
und Relationsinhaltsmerge ohne Verhaltensänderung; W/R-Testbytes bleiben gleich.
Die Klärungsstage lässt 17.e.W/R/C offen. Alle nachfolgenden Zähler gelten erst
nach bestandenem eigenem Apply-Gate und echtem Commit. Keine Verhaltenstests
in Dev; je Stage gefilterte fällige N=3-Gruppe plus ungefilterte Pflichtauswahl.

17.e wird als vollständiger zusammenhängender W/R/C-Schritt geliefert.
17.f behandelt danach eine eigene vollständige Lifecycle-/Originalbytepolitik
für alle Ressourcen, nicht nur Relationskandidaten; seine Abnahmen bleiben
offen, ebenso endgültige Metadaten, Zielinvarianten, CLI und Publikation.
Kein Teil von 17.e wird in diese Folgeschritte verschoben. Kein Alibi-Commit,
keine Änderung von Control-Konfiguration, Historie oder Klärungsbudget.
