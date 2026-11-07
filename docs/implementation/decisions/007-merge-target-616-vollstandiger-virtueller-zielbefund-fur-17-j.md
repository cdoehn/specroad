# MERGE-TARGET-616 — vollständiger virtueller Zielbefund für 17.j

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## MERGE-TARGET-616 — vollständiger virtueller Zielbefund für 17.j

Delegiert gemäß SPECROAD-DECISION-1, 2.4.3.1 und Vertrag 4;
clarification_allowed=true, Restbudget 3. Das nativ geprüfte saubere Result
021a46 bestätigt 17.i.W/R/C mit 8160/8206/8229 bestandenen Tests und
Abschlusscommit eb2ee51c97c23e68e75bfa2f726da03b1928ea26, 720/900.
Keine menschliche Einzelbestätigung, Review- oder Releasefreigabe wird erfunden.

Lücke: 17.j und SR-REQ-0365/0373 verlangen vollständige Zielvalidierung;
10.15.6 liefert erst einen Metadatenkandidaten. Eingabe-/Befundbindung,
Blockierung bei fehlenden Spezialisten und die Grenze zur Schreibbefugnis
sind für diesen neuen Übergang noch nicht festgelegt. Geprüft wurden
10.15.1–6, K.3, 17.j–17.l, die gemeinsame Modellvalidierung, native
Restore-Spezialisten und reale Quell-/Zielmodellkonstruktoren.

Alternativen: Kandidatenwurzel als Erfolg behandeln; eine zweite Merge-
Validierungsengine oder temporäre Projekte bauen; oder die vorhandene
vollständige native Pipeline auf die originalen virtuellen Zielbytes anwenden.
Gewählt wird die letzte, kleinste konservative Lösung. Der native Befund
bleibt erhalten und seine Bewertung folgt der bestehenden Zielprojektpolicy.
Benötigte Spezialisten liefern echte native Eingaben statt Erfolgscallbacks.
Unvollständigkeit, Quellenwechsel oder ein semantischer Konflikt sperren
Dateizugriff. Jeder gespeicherte Erfolg muss neu aus Originalen berechnet werden.

Die Präzisierung 10.15.7 ändert weder Metadatenpolitik noch Scope, bestehende
Formate/CLI-Verträge, Freigaben, Sicherheitsniveau oder menschliche Reviews.
Sie benötigt keine unbekannten externen Fakten: fehlende echte Provider
bleiben ein negativer Befund. Neue passive Befundbytes sind versioniert;
Bestandsdaten und historische Nachweise bleiben unverändert und erhalten.
Die Änderung ist ohne Datenverlust rücknehmbar. Alle Grenzen aus 2.4.1 gelten.

Dieser Präfix schreibt Spec, Planabnahmen und aktive Katalogbindungen zuerst
fort und lässt 17.j offen. Danach W: voller nativer Zielbefund inklusive
Profil/Scope/Referenzen und fail_on-Policy; R: neu kombinierte Invarianzfehler,
fehlende/wechselnde Provider, gespeicherte Manipulationen und späte
Quellenwechsel; C: passive Befundwerte von nativer Orchestrierung trennen.
Jede Stage erhält eigenes N=3-plus-Pflichtauswahl-Gate vor dem Commit.
17.k–17.l einschließlich tatsächlicher Transaktion und CLI/Work bleiben offen.
Dev führt keine Verhaltenstests aus; Collection und Paketprüfung sind keine
Abnahme. Die dokumentierten Sollkriterien werden erst durch Apply nachgewiesen.
