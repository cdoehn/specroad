# 4.j.W-FIX1 – CI-Buildhash-Nachweis korrigieren (Bundle 018)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## 4.j.W-FIX1 – CI-Buildhash-Nachweis korrigieren (Bundle 018)

- [x] **4.j.W-FIX1** – `Fix: 4.j.W-FIX1 test(build): Profilressourcen im Buildhash-Nachweis berücksichtigen`

Der CI-Lauf für 444708919d391eba123c1f49871133eacf0349b4 zeigt in allen fünf
Python-Versionen denselben Fehler des unabhängigen Buildhash-Tests. Der Builder
bindet die in 4.j.W hinzugefügten vier Profil-JSON-Dateien ein; die Testinventur
berücksichtigte sie bisher nicht. Der Fix korrigiert die Testinventur und ergänzt
Rohbyte-/Dateimengenregressionen, ohne Builder, Produktdateien oder Hashvertrag
zu verändern. Keine Test-Skips, keine Hochstufung von Anforderungsreife.

Genau ein separat getesteter Fix-Commit; Produktfortschritt unverändert 165/885,
letzter Plan-Commit 4.m.C, nächster 4.n.W. Damals lokale Ausführung ausschließlich der
benannten Testdateien mit vier Workern; am Abschluss volle parallele GitHub-CI.
Bei Lieferressourcenänderungen sind test_identity.py und test_payload_identity.py
damals Teil der gezielten lokalen Regressionsauswahl; diese Auswahlregel ist durch TD-002 aufgehoben. Die Änderung der
abgeschlossenen Bundle-Nummer auf 18 erfolgt erst nach dem erfolgreichen Gate.
Details: [`CI_Payload_Identity_Repair.md`](../../development/CI_Payload_Identity_Repair.md).
