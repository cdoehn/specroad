# OFF-PLAN – Partial-Lesegraph (Bundle 477)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Partial-Lesegraph (Bundle 477)

Revision 22 dokumentiert **PARTIAL-READ-GRAPH**, delegiert gemäß
SPECROAD-DECISION-1. Die Produktposition bleibt **631/900**, zuletzt
**15.f.W**, nächstens **15.f.R**. Entscheidungsbeleg und offene fachliche
Abnahmen stehen bei 15.f.R, normative Regeln in Spezifikation 0.2.27/E.3.3. Die echten
Dokumentzustände erhalten gemäß 2.1 eigene Patchversionen: W 0.2.25,
R 0.2.26 und die strukturelle C-Fassung 0.2.27.
Diese eine Klärungs-ZIP enthält drei echte Dokumentzwischenstände desselben
Vertrags, keine Produktimplementierung und keine nominellen Produktcommits:

- [x] **PARTIAL-READ-GRAPH.W:** Objekt-/Relationsdomäne und lokale Traversierung festlegen. Commit: `docs(spec): Partial-Lesegraph festlegen`.
- [x] **PARTIAL-READ-GRAPH.R:** Fehler-, Kontext- und Grenzfallabnahmen vervollständigen. Commit: `docs(spec): Partial-Lesegraph absichern`.
- [x] **PARTIAL-READ-GRAPH.C:** Gemeinsame Grenzen zentral ordnen, ohne Semantikänderung. Commit: `docs(spec): Partial-Lesevertrag strukturieren`.

Jeder Zustand erhält seine eigene gezielte parallele Dev-Verhaltensprüfung
und danach erst im externen Apply seine genau eine parallele Testgruppe:
Sequenz **181/Gruppe 1** (7.005), **182/Gruppe 2** (7.007),
**183/Gruppe 0** (7.007). Erst das erfolgreiche jeweilige Gate erlaubt
seinen Dokumentcommit und den zugehörigen Marker; erst C setzt Bundle 477.
Keine nachfolgende Phase wird vor dem vorherigen Commit installiert.
Fehler erhalten erfolgreiche Commits und den tatsächlichen Arbeitszustand.
Vorgesehene Apply-Gates sind keine bereits beobachteten Erfolge. Die
Teilgruppen laufen auf verschiedenen Dokument-/Katalogständen; dies ist
kein Vollsuite- oder Releasebeleg. Übergabe: **spec_clarification**.
Der reguläre Planschritt bleibt offen; nach der atomaren ZIP-Veröffentlichung
endet der Einzelauftrag ohne eigenes Apply, Statuspolling oder Fortsetzung.
