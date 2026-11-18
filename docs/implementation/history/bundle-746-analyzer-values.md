# Bundle 746 — passive Analyzerwerte

18. November 2026. Das maßgebliche erfolgreiche Result hat SHA-256
`b14b227a542ab40f5611933da0ade2f265fa942f945c6bc98dc5c92751a3da20` und HEAD
`d9636605d0e0481cdf1d7e55d782591ef8717aa7`. Es bestätigt 18.r.R mit 9.425
und 18.r.C mit 9.795 bestandenen Tests und einen sauberen Endstand.
801/918 Produktpositionen sind damit bestätigt; kein alter Commit wird wiederholt.

Die notwendige Detailfestlegung [ANALYZER-CONTRACT-746](../decisions/analyzer-contract-746.md)
geht den vollständigen Gruppen 19.a.W/R/C und 19.b.W/R/C voraus. Jede der
sieben Stages installiert nur ihren eigenen Zustand, durchläuft N=3 plus
ungefilterte begründete Pflichtauswahl und erhält erst danach ihren Commit.

Diese Datei beschreibt den Zielstand **19.a.C** mit **804/918**
nach dessen eigenem erfolgreichen Gate. Nächste Produktposition ist **19.b.W**.
Die Vorbereitung enthält keine in Dev ausgeführten Verhaltenstests. Syntax,
statische Analyse und reine Collection sind keine Verhaltensabnahme.

19.a.W implementiert den geschlossenen, kanonisch gehashten Descriptor,
unveränderliche Werte und den Vergleich mit dem bekannten eingebauten
Descriptor. R vervollständigt exakte Identitäts-/Versions-/Hashbindung,
Capabilityauswahl und Manipulationsabnahmen. Ein importierter Descriptor
erteilt weder Import- noch Ausführungsrecht. C trennt die Registry von der
Descriptorvalidierung; die verschobenen Funktionen und W/R-Testbytes bleiben gleich.

19.b.W bildet datentragende Requests aus vollständig expliziten Eingaben,
vergibt eine AN-ID vor der Snapshotbildung und bindet exakt die sechs
Fachkomponenten. Reader reparieren keine Kennungen oder Hashes. R prüft
Analyse-ID und Snapshothash unabhängig, fremde ID-Typen, verschachtelte
Bindungen, Betriebsfelder, Entropieausfall und einen echten isolierten
Prozessrundweg. C trennt die Identitätstypen/-zuteilung vom Requestparser;
W/R-Testbytes und verschobene Definitionen bleiben unverändert.

Projekt-Subjectauswahl, Ergebnisimport, CLI, Work-Fortsetzung und tatsächlich
installierter Sprachworker verbleiben an den späteren geplanten Positionen.
Die Registry meldet den hier noch nicht implementierten Worker ausdrücklich
als nicht ausführbar. Vollsuite und separate CPython-3.10–3.14-/Plattformmatrix
bleiben für die Meilenstein-/Releasefreigabe erforderlich. Keine Betriebsdaten,
Dienststarts oder vorweggenommenen menschlichen Freigaben sind Teil des Bundles.
