# Bundle 647 — 18.b.R/C-Korrektur und Control-Vollzugriff

9. November 2026. Maßgebliches Fehler-Result:
`bed038acb88eba8de5bc0c5468a003ffdafc2b15e643d2dcec1945af1cb0b236`,
Base-Commit `b292024d2d4f375e577dbf3ab7d6a7b853c08914`.
Bundle 646 hat **18.b.W erfolgreich committed**: 7.285 bestandene Tests.
18.b.R scheiterte mit 87 Fehlern und 7.294 bestandenen Tests. Der erhaltene
uncommittete R-Stand bildet bytegenau die technische Basis dieser Korrektur.
W wird nicht wiederholt. Alle verbleibenden IDs und Rollen bleiben erhalten:
18.b.R und 18.b.C, jeweils `implementation`, mit getrenntem Apply-Gate.

Diese Datei beschreibt den vorbereiteten Zielzustand **18.b.R**.
Der zugehörige Planfortschritt wird erst nach dem erfolgreichen Gate und Commit
wirksam. Dev führt keine Verhaltenstests aus. Eine Collection oder Hostprüfung
ersetzt keine Verhaltensabnahme.

## Korrektur der Testfehler

Sieben Proposal-Testfälle hatten ungültige synthetische Daten: ungültiger
Erweiterungsschlüssel, fehlende Positionsangaben, unzulässige Relationspaare
und ein ungeeigneter Zielknoten. Die Fixtures verwenden jetzt native gültige
Kontrollabhängigkeiten; zwei typfremde duplicates-Fälle prüfen weiterhin die
früher greifende native Endpoint-Diagnose. Alle 81 bestehenden Proposal-
Testidentitäten bleiben erhalten. Validatoren und Schreibschutz bleiben echt;
kein fachliches Gate wird zur Erzeugung grüner Tests abgeschwächt.

80 Fehler betrafen Git-Quellen auf einem Remote-Testhost, dessen Git 2.43 die
bestehende Pflichtoption `--no-lazy-fetch` nicht unterstützt. Der separat
beauftragte Hosteingriff hat System-Git auf 2.56.0 aktualisiert; beide üblichen
Systempfade akzeptieren die benötigten Optionen, der native Hostcheck ist ready.
Dies ist ein Umgebungsnachweis, kein bestandener Wiederholungstest. Sämtliche
betroffenen Git-Testdateien gehören ungefiltert zur Pflichtauswahl. Keine lokale
Hostkonfiguration oder Installation wird mit diesem Produktbundle verteilt.

## Zusätzlicher ausdrücklicher Nutzerauftrag

Der Betreiber hat am 9. November ausdrücklich beauftragt, die Control-
Rechtekorrektur **in derselben noch unveröffentlichten ZIP** umzusetzen.
[CONTROL-ACCESS-647](../../../tools/dev/codex/control/spec/SPECIFICATION.md#off-plan-control-access-647-expliziten-vollzugriff-beibehalten)
definiert den optionalen dauerhaften Vollzugriff und seine Abnahmen.
Der bisherige Rechtewechsel bei jedem Turn wird durch eine gespeicherte Wahl
ersetzt: `configure --access-mode full-access`; beide Transporte, Probes und
zulässige Fortsetzungen halten sie ein. Ohne Option bleibt die gespeicherte
Wahl erhalten, alte Konfigurationen behalten den eingeschränkten Modus.

Diese beauftragte OFF-PLAN-Korrektur wird im offenen R-Zustand mit umgesetzt;
sie zählt **keine zusätzliche Produktplanposition**. C übernimmt die bereits
angekündigte Proposal-Scope-Bereinigung und zentralisiert ausschließlich die
Codex-CLI-Kodierung der in R festgelegten Policy. Kein neues C-Verhalten.
Der native Korrekturvertrag mit genau den zwei offenen IDs/Rollen wird weder
erweitert noch gelockert. Kein künstlicher Klärungscommit, keine Änderung des
Klärungsbudgets, kein dienstseitiger Konfigurations-/Installationsschritt.

Pflichtauswahl je Stage: ursprüngliche vollständige Proposal-/Scope-/CLI-
Regressionen, alle vom Fehler-Result betroffenen Git-Dateien und die gesamte
Control-Suite einschließlich neuer Rechte-, Transport- und Fortsetzungsfälle.
Neue Testnummern werden nur angehängt; bestehende Nummern und Historien bleiben.
Apply prüft die Vereinigung mit der fälligen gefilterten N=3-Gruppe vor jedem
Commit und bringt erst danach den nächsten Zustand aus.

Aktivierung von Full Access benötigt nach vollständig erfolgreichem Apply ein
geprüftes Offline-Deploy und die ausdrücklich gewählte lokale Konfiguration.
Diese Übergabe startet weder Control noch Watcher, Apply oder CI. M18 und der
Gesamtplan sind nicht abgeschlossen; 18.c und spätere Positionen bleiben offen.
