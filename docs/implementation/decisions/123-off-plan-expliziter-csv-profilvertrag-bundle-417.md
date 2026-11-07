# OFF-PLAN – Expliziter CSV-Profilvertrag (Bundle 417)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Expliziter CSV-Profilvertrag (Bundle 417)

Revision 10 dokumentiert **CSV-PROFILE-CONTRACT**, **delegiert gemäß
SPECROAD-DECISION-1**. Spezifikation **0.2.15, D.2.1**, schließt die
Typ-/Listen-/Null-/Abwesenheits- und Fehlergrammatik für 14.f. Der genaue
Entscheidungsbeleg einschließlich Alternativen, Grenzprüfung und noch
offenen Abnahmen steht unmittelbar bei 14.f. Der Kopf wird mit der aktiven
Planrevision und Dokumentversion konsistent geführt; historische Angaben
bleiben erhalten. Keine persönliche Einzelzustimmung oder Reviewbehauptung.

- [x] **CSV-PROFILE-CONTRACT:** Explizite CSV-Profile, Zellcodecs und Verlustgrenzen verbindlich klären. Commit: `docs(spec): CSV-Profil und Zellkonvertierung präzisieren`.

**Übergabegrenze:** Genau ein OFF-PLAN-Dokumentcommit mit Spezifikation,
Plan und notwendigen aktiven Katalog-Hashbindungen. Kein Produktcode,
Verhaltenstest, Testnummernregister oder Runner wird verändert. Historische
Evidence wird nicht umgebunden. Produktstand **585/900**, zuletzt **14.e.C**,
nächstens **14.f.W**, bleibt unverändert. Nach dem erfolgreichen parallelen
Apply-Gate setzt der Entrypoint nur den obigen Offplan-Marker und die
Bundlenummer auf 417. Das markiert keine Implementierung von 14.f.

**Prüfgrenze:** Reine normative Klärung ohne Produktverhaltensänderung;
keine erfundenen Dokumentationstests. Vollständige Collection-/Katalogprüfung
mit null ausgeführten Testkörpern sowie native Paketprüfung bleiben
erforderlich. Apply prüft vor dem eigenen Commit ausschließlich Gruppe 2/3,
Commitfolge 125, mit vier parallelen Workern. Teiltests sind kein Vollsuite-
oder Release-Nachweis. Übergabe als `spec_clarification`, anschließend Ende
des Einzelauftrags; kein Eingriff in Control, Watcher, CI oder Dienste.
