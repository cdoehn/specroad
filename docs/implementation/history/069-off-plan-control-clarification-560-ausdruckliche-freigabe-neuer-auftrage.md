# OFF-PLAN CONTROL-CLARIFICATION-560 — ausdrückliche Freigabe neuer Aufträge

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN CONTROL-CLARIFICATION-560 — ausdrückliche Freigabe neuer Aufträge

Ausdrücklicher Nutzerauftrag vom 3. November 2026: den protokollierten Übergang
auf Vertrag 4 ergänzen; den angefangenen Produktplanschritt zurückstellen.
Geprüfte Basis: Result 5a7df9, SHA-256
`c4b1e2eac77931fe9edbbb7e63b212b7ea46d284dc9e76b5d533c1c448677ae5`,
sauberer Abschluss `7a66ba048339defe719560979a7cb2b2803131ba`.
Bundle 559 ist erfolgreich; sein W/R/C-Stand bleibt vollständig erhalten.
16.d.W wurde ausschließlich analysiert, ohne Produktänderung, Patch oder
Commit. Er bleibt offen, Stand 669/900 und nächster Produktcommit 16.d.W.
Kein Git-Reset, keine Löschung von Betriebsbelegen oder Testhistorie.

Ursache: Der neue V4-Marker war installiert, aber die wiederaufgenommene
Kette erbte V3/clarification_allowed=false aus unbekannten manuellen
Übergaben. Drei Restplätze sind keine Befugnis. Eine automatische Lockerung
würde alte Aufträge umdeuten; ein Löschen/Neuinitialisieren der History würde
Nachweise und Budgets verlieren. Gewählt wird eine ausdrückliche Bedien-
absicht für genau ein neues sauberes Result mit überprüfbarer direkter
Apply-Herkunft. Keine pauschale Konfigurationsoption zur Umgehung von Fehlern.

W: vollständiger neuer Befehl authorize-clarification, gebundene private
Absicht, echte normale Apply-/Snapshotnachweise, budgeterhaltender neuer
V4-Auftrag, atomarer Wechsel nach freiem Thread und offenem Betriebsgate.
Abnahmen: kein Modell-/Dienst-/Apply-Start durch den Befehl; alter Auftrag
und Versuche bleiben, gleicher Befehl idempotent, Pause erhält Absicht,
positives Restbudget unverändert, optionaler Klärungspräfix im nächsten
Auftrag erlaubt, normale Arbeit ohne Klärung weiterhin möglich.
R: beschädigte/konkurrierende Absichten, fehlende/geänderte Archivbelege,
Konfigurations-/Versuchswechsel und Unterbrechung der Übernahme strikt
ablehnen; atomarer Rollback und erneute Nachweisprüfung vor Ausgabe.
C: rein strukturelle Trennung der passiven Quell-/Paketprüfung von Queue,
Worker und Persistenz; sämtliche R-Abnahmen und Tests unverändert erhalten.

Spezifikation 0.2.54 und aktive Katalogbindungen werden zuerst in W ergänzt.
Vorbereiteter C-Zustand: passive Nachfolgerprüfung in eigenem Modul;
Verhalten, Tests und Nachweise des R-Zustands bleiben unverändert.
Drei echte Zustände mit je eigenem N=3-plus-Pflichtauswahl-Gate. Alle neuen/
geänderten Tests sowie Control-, Recovery-, Budget-, Mixed- und Apply-
Regressionen sind verpflichtend. Dev führt keine Verhaltenstests aus.
Der Code ist bis zum erfolgreichen Apply unbestätigt. Installation und
Bedienfreigabe benötigen den tatsächlichen Erfolgsnachfolger; die Payload
kopiert keine echten Betriebsdaten und führt keine Bedienaktion aus.
