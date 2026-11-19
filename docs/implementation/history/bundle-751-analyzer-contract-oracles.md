# Bundle 751 — vollständige Befehls- und Schemaoracles

19. November 2026. Maßgebliches natives Fehler-Result:
SHA-256 `c363c6e8eae95eb636f7eb2afaf860544fe7b72f1f3f344408becf9668c035a1`,
HEAD `83382391a0c1cac367d63840ce4b9f25e6b2b65b`.
19.g.W meldet vier fehlgeschlagene und 10.915 bestandene Tests. In Bundle 750
wurde kein Commit erzeugt; alle sechs Produktstufen bleiben offen.
Der bereits früher übernommene ANALYZER-CLI-749-Commit bleibt erhalten;
bestätigter Produktfortschritt ist 819/918, nächste Position 19.g.W.

Die vier Fehler betreffen veraltete maschinenlesbare Testverträge:
Zwei unabhängige vollständige Befehlsinventare fehlen um die sieben nach T.5
vorgesehenen Analyzerbefehle; das unabhängige Schema-Fabrikinventar fehlt um
deren sieben registrierte Schemas. Der Optionsvertrag setzt Projektpflicht
mit Zulässigkeit von --project gleich und übersieht die explizite Projektvariante
der vollständig datentragenden run/import/show/evaluate-Aufrufe.

Die Korrektur ergänzt die expliziten vollständigen Inventare; Mengengleichheit,
Eindeutigkeit, vollständige Schemainhalte und Hashprüfungen bleiben bestehen.
Der Optionsfall prüft zusätzlich den projektlosen Basisvertrag, die einzige
Projektvariante, PROJECT_READ, fehlende Work-/Transporteffekte und ihre echte
Registrybindung. Verbotene Work-/Schreiboptionen bleiben vor Effekten abgelehnt.
Keine Subset-Erwartung, kein Ableiten der Sollmenge aus dem geprüften Katalog,
keine entfernten Fälle, Skips oder Ersatzvalidatoren. Testidentitäten und
Nummern bleiben unverändert; Produktcode und Spezifikation werden nicht
zur Anpassung an ein falsches Oracle geändert.

Korrekturbindung: `349b8d5a42efe687929cbbeb3f761ec811bf55eb2f9cf91b6a22674b62acfb90`.
Der vollständige ursprüngliche Rest 19.g.W/R/C und 19.h.W/R/C wird mit
unveränderten IDs, Rollen implementation, Commitnachrichten und Abnahmen
fortgeführt. Alle 33 uncommitteten Quellpfade gehören zum ersten Commitumfang;
die Vorherbindung stammt vollständig aus dem neuen effektiven Snapshot.
Keine neue Klärung, keine Wiederholung erfolgreicher Commits, keine Budgetänderung.
Die Berichte 749 und 750 bleiben unveränderte historische Vorbereitung/Evidenz.

Zielstand **19.h.W** zählt erst nach seinem eigenen Apply-Gate und Commit
**823/918**; danach folgt **19.h.R**. Alle bisherigen Pflichtdateien und
die vier korrigierten Testdateien bleiben ungefiltert in jedem Gate; die
fällige gefilterte N=3-Gruppe kommt hinzu. C bewahrt die W/R-Testbytes und
extrahierten Funktionsdefinitionen. Dev prüft nur statisch, per reiner
Collection und nativem Paketvertrag. Diese Vorbereitung ist kein Testpass.
Nach vollständigem Erfolg folgt 19.i.W; spätere Work-/Worker- und Release-
Abnahmen sowie menschliche Freigaben bleiben unverändert erforderlich.
