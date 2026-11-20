# REPOSITORY-REVIEWS-768 — modulare öffentliche Abnahmen

20. November 2026. Ausdrücklicher Nutzerauftrag: eine platzsparende Offline-
HTML-Seite und JSON-Bewertungen mit Name/E-Mail im Repository unter `reviews/`,
eine automatisch erzeugte Markdownübersicht mit Mehrfachbewertungen und ein
Hinweis auf offene Reviews in der Projekt-README. Ergänzend verlangt der Nutzer,
dass der Sprachkorpus ein Modul bleibt und weitere Abnahmen hinzukommen können.
Der Nutzer stellt die persönliche Korpusprüfung vorerst zurück und beauftragt
anschließende weitere Implementierung unter einer vorläufigen Arbeitsannahme.

Dies ist eine ausdrücklich beauftragte Scope-/Reihenfolgeänderung, keine
optionale delegierte Detailklärung. SPECROAD-DECISION-1 und Vertrag 4 bleiben
unverändert; keine fachliche Zustimmung wird aus einem Control-Schalter abgeleitet.
Ein separater Klärungspräfix ist nicht erforderlich. Die drei OFF-PLAN-Stages
haben die Rolle implementation und die Übergabeart patch_ready. Sie starten
keine Automatik, keinen Test, keine CI und keine Betriebsinstallation im Dev.

## Wahl und Grenzen

Ein separates HTML pro Abnahme würde UI-Code und Wartung vervielfachen; ein
Server oder ein Framework würde die gewünschte Clone-/Offline-Nutzung erschweren.
Die gewählte kleine gemeinsame Oberfläche liest passive Module über den lokalen
Dateidialog. JSON ist die maßgebliche Quelle. Ein Result pro UUID verhindert
gegenseitiges Überschreiben beim Zusammenführen unabhängiger Beiträge. Ein
stdlib-Pythonwerkzeug validiert und erzeugt den Markdownstand; Git/PR bleibt
der ausdrückliche Übernahmeweg. Neue Module brauchen keinen ausführbaren Plugin-
Code. Details und geschlossene Datenverträge: Spezifikation 2.5.7 und reviews/GUIDE.md.

Keine vorhandenen menschlichen Bewertungen werden erfunden. Der erste Datensatz
enthält 225 bereits privat vorbereitete KI-Entwürfe, deren Textbytes und
Originalhashes vollständig erhalten sind. Herkunft und Nutzungs-/Lizenzentscheidung
haben einen zusätzlichen offenen Prüfpunkt. Die Reviewidentitäten sind selbst
angegeben und im Beitragsreview zu prüfen; sie sind keine technische Identitäts-
oder Befugnisbeglaubigung. E-Mail-Veröffentlichung und persönliche Prüfung müssen
vor Export ausdrücklich bestätigt sein. Keine Zugangsdaten oder Sessiondaten.

## Vollständige OFF-PLAN-Folge

- [x] **REVIEWS.W** — `REVIEWS.W feat(reviews): modulare Offline-Abnahmen aufbauen`.
  Vollständig benutzbare gemeinsame Oberfläche, generisches Modulschema, erstes
  Korpusmodul, eigene JSON-Resultate, unabhängige Reviewerzählung, Einwände,
  Text-/Kriterienbindung, lesende Validierung und atomare Übersicht. Namens-/E-Mail-
  und persönliche Bestätigungen, Clone-/Beitragsablauf, README und Planänderung.
  Gate: echte JSON-/Dateiverhaltenstests einschließlich eigenständiger CLI ohne
  SpecRoad-Installation; Quellidentität und Remote-Snapshot umfassen reviews/.
- [x] **REVIEWS.R** — `REVIEWS.R feat(reviews): Reviewbindungen und Fortsetzungen absichern`.
  Explizite eigene Ablösung je Prüfpunkt, erhaltene widersprechende Fremdreviews,
  alte/fehlende Bindungen, strikte Formen, Dateilinks/Sonderdateien, begrenzte
  Eingaben und Fehler ohne Überschreiben vorheriger Ergebnisse. Browserimport
  erkennt doppelte Schlüssel, lässt veraltete Punkte offen und erfordert eine
  erneute persönliche Bestätigung. Alle W-Tests bleiben Pflicht.
- [x] **REVIEWS.C** — `REVIEWS.C refactor(reviews): Datenvertraege und Auswertung trennen`.
  Nur Trennung der unveränderten Verträge, Bewertungsaggregation, Dateizugriffe
  und Darstellung hinter derselben API. Funktions-/Klassen-AST und Testbytes
  bleiben gleich; das eigene Gate prüft die vollständigen W/R-Orakel erneut.

Diese Checkliste beschreibt vorbereitete Zielzustände. Ein Häkchen im jeweiligen
Stageziel gilt erst nach dessen erfolgreichem Apply-Gate und Commit. Keine
Anrechnung auf die 918 Produktpositionen; keine vorweggenommene Abnahme.

## Vorläufige Produktreihenfolge

Nach REVIEWS.C folgt **19.u.W**, anschließend die bestehenden vollständigen
Gruppen 19.u, 19.v, 19.w und 19.x. 19.u.W darf dafür ausdrücklich auf dem bestätigten
19.s.C aufbauen. **19.t.W/R/C bleibt unvollständig und ohne Erfolgszählung.**
Nach 19.x.C kehrt die Folge zu 19.t.W zurück; vor 19.y müssen 19.t einschließlich
menschlicher sprachkundiger Prüfung, dokumentierter Herkunft/Nutzungsbedingungen,
Freeze und echter unveränderter Korpusabnahme abgeschlossen sein. Keine
Releasefreigabe durch die vorläufige Arbeitsannahme. Die bestehenden echten
Sicherheits-, Funktions- und Ressourcentests laufen weiterhin normal; sie werden
nicht durch angenommene Erfolge, Mocks oder ausgelassene Prüfungen ersetzt.

Die Modulprüfung liefert lediglich Reviewabdeckung. Selbst vollständige
Reviewabdeckung friert den Korpus nicht automatisch ein und besteht keinen
py3langid-Test. Die unveränderten T.10-Ziele (unter anderem 18/20 je Hauptsprache,
keine entschiedene Falschsprache im Rest, separate Kurzfälle und Ressourcen-
verträge) bleiben erforderlich. Nach einem verfehlten Modellziel keine heimliche
Auswahl günstigerer Texte. SR-TC-0720 bleibt bis zu echten Belegen offen.
