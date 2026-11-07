# OFF-PLAN CONTROL-BLOCKED-601 — nachträgliche ausdrückliche Klärungsfreigabe (C)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN CONTROL-BLOCKED-601 — nachträgliche ausdrückliche Klärungsfreigabe (C)

Manueller Nutzerauftrag vom 5. November 2026. Basis ist das erfolgreiche,
saubere Result SHA-256 `810a1c0ead271a6264ff447cb8c9c02eb4b69f094b493edc217b432ed528bb63`,
HEAD `291c67e7c8d9682f7ff4619ed18f21a9890ad721`. Bundle 600 ist vollständig
abgeschlossen. Der folgende Versuch zu 17.d wurde ausschließlich analysiert
und als paketlos blockiert abgeschlossen. Kein Produktcommit wird verworfen;
702/900 und der nächste Produktcommit 17.d.W bleiben unverändert.

Ursache: Der vorhandene Freigabebefehl verlangt einen unbeanspruchten direkten
Apply-Nachfolger. Eine nachträgliche ausdrückliche Betreiberfreigabe kann so
einen bereits beendeten paketlosen Blocker nicht lösen. History löschen oder
bestehende Vertragszeilen überschreiben würde Nachweise verlieren. Gewählt
wird ein eigener protokollierter Versuch auf derselben weiterhin gültigen
Quelle, nur nach tatsächlichem paketlosem V4-Blockabschluss und positivem
vorhandenem Budget. Kein allgemeiner Retry oder impliziter Freigabeschalter.

CONTROL-BLOCKED-601.W: vollständiger Bedienweg, bindender Projektmarker und
Spec 2.4.3.3; private additive Absicht, native Aktualitäts-/Paketprüfung,
getrennte Versuchsdateien und wirksamer V4-Vertrag bei unveränderten alten
Vertrags-/Budgetzeilen. Abnahme: Vormerken startet nichts; Pause/aktiver Thread
halten zurück; normale und gemischte Übergabe funktionieren; genau ein
Folgepaket und richtiger Budgetverbrauch/Erneuerung nach tatsächlichem Apply.
CONTROL-BLOCKED-601.R: strikte Integrität, Proxy-Promptbindung, defekte oder
konkurrierende Nachweise, spätere Pakete/Results, Unterbrechung und Race-Grenzen
vor dem Dispatch; persistierter Retryrest und negative Matrix bleiben erhalten.
CONTROL-BLOCKED-601.C: gemeinsame Nachweis-/Versuchshelfer strukturell trennen,
keine neue Fachentscheidung; W/R-Tests und alle Budgetgrenzen unverändert.

Drei echte Zwischenstände mit jeweils eigenem gefilterten N=3-Gate plus
vollständiger Control-Regression und Apply-/Katalogregressionen. In Dev nur
Syntax, Collection und native Paketvalidierung; kein Verhaltenstest und
kein vorweggenommener Abnahmeerfolg. Installation und anschließende Freigabe/
Start sind ausdrücklich beauftragte separate Bedienaktionen nach erfolgreichem
Apply. Keine lokalen Konfigurationen, echten Session-IDs oder Zugangsdaten
in der Payload. Die 17.d-Detailentscheidung bleibt dem späteren freigegebenen
Produktauftrag vorbehalten; dieses manuelle Bundle verbraucht keinen Platz.
