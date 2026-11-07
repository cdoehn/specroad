# OFF-PLAN CI-PACKAGES-525 — manuelle CI und worksteal

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN CI-PACKAGES-525 — manuelle CI und worksteal

Autorität: ausdrücklicher Nutzerauftrag 31.10.2026; Spezifikation 2.5.1.
Produktfortschritt bleibt 653/900, nächster Produktcommit 15.m.C.
Ein gemeinsames Bundle liefert echte W/R/C-Zustände mit getrennten gezielten
parallelen Dev-Gates und jeweils einer fälligen N=3-Apply-Gruppe vor dem Commit.
W: worksteal, bestehende Messdaten, zeitgewichtete dynamische CI-Matrix,
exakte Teilbelege und vollständige Zusammenführung funktionsfähig integrieren.
R: falsche/fehlende/mehrdeutige Belege, Eingabe- und Pfadgrenzen, tatsächliche
mehrteilige Worker-Ausführung und historische CI-Kompatibilität absichern.
C: gemeinsame Ausführungs-/Messprimitive zusammenführen, ohne Fachänderung.
Die Repo-/Commit-/Attempt-Bindung und sämtliche vorhandenen Testidentitäten
bleiben erhalten. Keine Vollsuite zur Messung, keine automatische GitHub-CI.
Lokale Abnahmen und native Paketprüfung werden vor Übergabe dokumentiert;
Apply- und echte GitHub-Nachweise bleiben bis zur tatsächlichen Ausführung offen.

Lokale gezielte Abnahmen (CPython 3.14.4, vier worksteal-Worker):
W: 541 bestanden; R: 563 bestanden; C: 677 bestanden. 45 neue Tests,
Gesamtkatalog 22.617 eindeutig gesammelt. Drei echte Beispielpakete ergeben
einen vollständigen Nachweis; fehlende Pakete verhindern Gesamterfolg.
Apply-Abschluss CI-PACKAGES-525: W/R/C-Gates erfolgreich; Bundle 525 abgeschlossen.
Die manuelle CPython-Matrix 3.10–3.14 bleibt ausstehend; kein CI-Start.
