# OFF-PLAN – Explizite NDJSON-Objekthülle (Bundle 421)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Explizite NDJSON-Objekthülle (Bundle 421)

Revision 11 dokumentiert **NDJSON-OBJECT-CONTRACT**, **delegiert gemäß
SPECROAD-DECISION-1**. Spezifikation **0.2.16, D.3.1**, klärt Hülle,
Versions-/Kindzuordnung, native Payload-/Hash-Erhaltung und Stromabschluss.
Der Entscheidungsbeleg samt Alternativen, Grenzprüfung und noch offenen
Verhaltensabnahmen steht unmittelbar bei 14.g. Historische Angaben bleiben
erhalten; keine persönliche Einzelzustimmung oder Reviewbehauptung.

- [x] **NDJSON-OBJECT-CONTRACT:** NDJSON-Objekthülle und vollständige Stromgrenzen verbindlich klären. Commit: `docs(spec): NDJSON-Objekthülle und Stromgrenzen präzisieren`.

**Übergabegrenze:** Genau ein OFF-PLAN-Dokumentcommit mit Spezifikation,
Plan und notwendigen aktiven Katalog-Hashbindungen. Kein Produktcode,
Verhaltenstest, Testnummernregister, Runner oder Workflow wird verändert.
Historische Evidence wird nicht umgebunden. Produktstand **588/900**,
zuletzt **14.f.C**, nächstens **14.g.W**, bleibt unverändert. Erst nach dem
erfolgreichen parallelen Apply-Gate setzt der Entrypoint ausschließlich
den obigen Offplan-Marker und die Bundlenummer auf 421. Das markiert keine
Implementierung von 14.g.

**Prüfgrenze:** Reine normative Klärung ohne Produktverhaltensänderung;
keine erfundenen Dokumentationstests. Vollständige Collection-/Katalogprüfung
mit null ausgeführten Testkörpern und native Paketprüfung bleiben erhalten.
Apply prüft vor dem eigenen Commit ausschließlich **Gruppe 0/3**,
Commitfolge **129**, mit **5.969 Tests** und vier parallelen Workern.
Teiltests sind kein Vollsuite- oder Release-Nachweis. Übergabe als
`spec_clarification`, danach Ende des Einzelauftrags; kein Eingriff in
Control, Watcher, CI oder Dienste. Der nächste Produktauftrag implementiert
den geklärten offenen Schritt; dieses Bundle enthält keine zweite Phase.

**Tatsächlich geprüft in Dev:** Vollständige Collection-/Katalogprüfung mit
**17.906 erfassten Identitäten**, **0 Testkörpern**, Prozesscode **0**,
keinen Katalogfehlern und `full_suite_passed=null`. Sämtliche Testdateien,
Nummern, Fixtures, Runner und Produktquellen blieben bytegleich zur
bestätigten Basis; an 743 aktiven Katalogdokumenten änderte sich allein
die Spezifikations-Hashbindung. Keine bestehende Testabdeckung wird dadurch
als Nachweis der neuen NDJSON-Regel umgedeutet.
Quellstand `ed4a9b1a9c0e0212d2afcc35f4a70b81bfce83d5f63f27f008e8cb2a1d8f6d69`,
Katalog `d7f33a717756a61d82de320f1e6938e991cd112afbf22e3cb1abb009217c9f38`,
Spezifikation `cad61bee632c33f6ccc1310f83f8c02aa222f1b20b1e6b03e5c23f318cccf3bb`.
Die hier genannten künftigen NDJSON-Verhaltensabnahmen bleiben unausgeführt;
der spätere parallele Apply-Teiltest wird nicht vorweggenommen.
