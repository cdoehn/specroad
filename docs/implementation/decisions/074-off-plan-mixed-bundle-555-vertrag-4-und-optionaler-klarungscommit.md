# OFF-PLAN MIXED-BUNDLE-555 — Vertrag 4 und optionaler Klärungscommit

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN MIXED-BUNDLE-555 — Vertrag 4 und optionaler Klärungscommit

Vorbereiteter Zustand MIXED-BUNDLE-555.C; erst nach seinem erfolgreichen Apply-Gate committed.

Ausdrücklicher Nutzerauftrag vom 3. November 2026: Zuerst diese SpecRoad-
Änderung, anschließend ein getrenntes Control-Bundle. Ohne notwendige
Spezifikationsklärung ausschließlich Plancommits; bei zulässigen normalen
Detail­lücken ein OFF-PLAN-Klärungscommit zuerst, danach vollständige sinnvolle
Plancommits in derselben ZIP. Keine automatische Befugniserweiterung aus
einem alten Vertrag. Verbindlicher Vertrag: Spezifikation 2.4.3.1.

Geprüfte technische Basis ist Result 72894e, SHA-256
`b3e090440068352bcfe98ecb89dfb4685f7be14e2d528cea4761e5ab08f46b29`.
Bundle 554 hat alle vier Gates bestanden und sauber abgeschlossen;
Produktstand 669/900, nächster Produktcommit 16.d.W. Dieser OFF-PLAN-Auftrag
ändert den Produktzähler nicht. Alternativen: Nur den Prompt ändern würde
Klassifikation/Budget/Recovery widersprechen; eine neue Apply-Engine wäre
unnötig. Gewählt wird der additive Rollenvertrag der bestehenden Commitfolge.

MIXED-BUNDLE-555.W: v2-Plan/Stage-Rollen und optionaler Klärungspräfix,
Vorbereitung/Entrypoint, versionierter Projektmarker und normative Regel.
Abnahme: normale Folge ohne Dokumentcommit sowie gemischte Folge mit einem
Dokumentcommit; Installation, Gate, Commit und nächster Zustand bleiben strikt
geordnet. V1 bleibt unverändert unterstützt.
MIXED-BUNDLE-555.R: unzulässige Rollen, versteckte/mehrfache/nachgestellte
Klärung, reine Klärung, falscher Scope, Verlust der Rollenbindung und erhaltene
Restfolge nach Fehler sicher ablehnen; keine Wiederholung erfolgreicher Stages.
MIXED-BUNDLE-555.C: interne Vertragsprüfung strukturieren, W/R-Verhalten und
Testbytes unverändert. Alle neuen/geänderten Testdateien sowie vorhandene
Apply-/Katalog-/Runnerregressionen sind pro betroffener Stage Pflicht.

Dev-Verhaltenstests bleiben nicht ausgeführt. Reine Collection, statische
Prüfung und native Paketrekonstruktion sind keine Apply-Abnahme. Installation
ändert keinen Control-Zustand und startet keinen Dienst. Control folgt als
separate Lieferung auf seiner eigenen Resultbindung. Alte Aufträge und
Recovery-Belege bleiben erhalten; neue V4-Aufträge brauchen installierte
Unterstützung und den zulässigen Versionsübergang.
