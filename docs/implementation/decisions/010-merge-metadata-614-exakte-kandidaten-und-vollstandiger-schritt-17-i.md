# MERGE-METADATA-614 — exakte Kandidaten und vollständiger Schritt 17.i

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## MERGE-METADATA-614 — exakte Kandidaten und vollständiger Schritt 17.i

Autorität: SPECROAD-DECISION-1, 2.4.3.1 und Vertrag 4, clarification_allowed=true,
Restbudget 3. Result 3250d1 ist nativ geprüft, sauber und vollständig erfolgreich;
17.h.W/R/C sind committed, 717/900. Technische Bindung siehe Bundle-Vertrag.
Keine menschliche Freigabe oder in Dev ausgeführte Verhaltensabnahme wird behauptet.

Lücke: K.3 legt die Metadatenarithmetik fest, aber noch nicht Kandidatenformat,
unabhängige Nachrechnung, die Zuordnung mehrerer Auflösungsakteure oder die
belegte historische Revisionsobergrenze. Geprüft: 10.15.1–5, K.1/K.3,
17.i–17.l, native Quellinventare, Baseline-Originale und zentraler Metadatenpfad.
Alternativen: Caller-Werte vertrauen; fertige Zielbytes ohne Herkunft übernehmen;
oder die vollständigen gebundenen Originale in beiden Vorbereitungen nachrechnen.
Gewählt ist die letzte konservative reversible Lösung. Das letzte explizite
betroffene Ereignis bestimmt den Akteur; alle vorherigen Auditereignisse bleiben.
Nur tatsächlich referenzierte Ours-Baseline-Originale und Base/Ours bestimmen
bekannte Revisionen, keine erfundene Historie oder frei übergebene Maximalzahl.

10.15.6, diese Abnahmen und aktive Katalogbindungen werden zuerst fortgeschrieben.
Dieser Klärungscommit lässt 17.i offen. Anschließend folgen vollständige W/R/C-
Stände desselben Schritts: W baut alle vier Klassen und volle native Dateiprojektion;
R vervollständigt historische Revisionen, Ursprungs-/Zeitgrenzen und unabhängige
Writer-Nachprüfung; C extrahiert passive Werte ohne Verhaltensänderung.
Jede Stage braucht ein eigenes Apply-Gate und einen echten Commit. Die spätere
Zielvalidierung/Publikation wird nicht vorgezogen oder für erledigt erklärt.
Scope, Sicherheits-/Kompatibilitätsgrenzen, Reviews und Nachweise bleiben erhalten.
