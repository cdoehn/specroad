# Bundle 795 — Markdown-Planquellen

22. November 2026. Das maßgebliche native Result mit SHA-256
`95d1f86b62e24b3247b7420073275fbc1709e93ba5d79e78aa8389e294acb993`
bestätigt 21.a.R mit 25.056 und 21.a.C mit 25.098 bestandenen Tests,
beide Commits und den sauberen Stand
`a395c08e6b1f385af0e179120d30843dc7e2341d`. **891/996** Positionen sind
bestätigt; es gibt keinen offenen Korrekturrest.

Diese Stage **21.b.R** gehört zur vollständigen Gruppe 21.b. Ihr Häkchen
und Fortschritt gelten erst nach ihrem eigenen erfolgreichen Apply-Gate
und Commit. Dev-Verhaltenstests: **0**. Syntax, reine Collection, native
Paket- und passive Übergabeprüfung sind keine Verhaltensabnahme.

- W liest genau eine aktuelle UTF-8/LF-Quelle über `ProjectSource.read_plan`
  und die bestehende Dateigrenze. Der iterative Parser erkennt reservierte
  Metadaten, echte ATX-/Listeneinträge und ihre Hierarchie; er ignoriert
  Markierungen in Code, Zitaten und Kommentaren. Die vorhandenen typisierten
  Projektionen und Identitätsprüfungen bleiben maßgeblich. Freitext, Quellspannen,
  vollständiger Dateihash, Projektionhashes und `plan-context-v1` bleiben getrennt.
  Ungültige Quellen liefern lokalisierte Diagnosen und keinen Teilplan;
  ihre Originalbytes bleiben ausdrücklich lesbar. Es entsteht kein Cachewrite.
- Reine feld-/spanbasierte Kandidaten ändern nur beauftragte Bereiche und
  prüfen Dateihash, vollständige Vorherbytes, Grenzen und Überlappungen.
  No-op erhält sämtliche Bytes. Sie erzeugen weder Auditstempel noch Revision,
  Git-Aufruf oder Schreibfreigabe. Eine explizite benachbarte Vergleichsbasis
  ermöglicht SRV206; ohne Basis wird keine historische Revision bewiesen.
- R erhält unveränderte JSON-Tokens einschließlich Escapes und Formatierung
  auch bei einzelnen Metadatenänderungen. Fehlerpositionen folgen den
  physischen UTF-8-Quellen. Zusätzliche Oracles betreffen RTL, Unicode,
  tiefe Listen, Fences, doppelte IDs/Schlüssel, konkurrierende Byte- oder
  Konfigurationsänderungen, native Linkgrenzen und unerwünschte Strukturinjektion.
- C trennt die unveränderten Scanner-, Diagnose- und Editwertdefinitionen.
  Sämtliche W/R-Testquellen bleiben bytegleich; kein neues Fachverhalten.

Die unabhängigen R-76-Oracles verwenden echte Dateien mit zwei Plänen,
RTL und Listen jenseits Ebene 6, unveränderte Code-/Kommentarbytes und dieselben
IDs nach Umnummerierung. Gemeinsame Modell-, Schema-, Pfad-, JSON-, JCS-,
Konfigurations-, Bootstrap-, Nur-Lese- und Sicherheitsregressionen bleiben
in den drei verpflichtenden Apply-Auswahlen. Alle alten Testnummern und
Katalogoracles bleiben erhalten. Keine Dokument- oder Layouttests.

Der abgeschlossene Ausschnitt ist der vollständige Parser einschließlich
seiner verlustarmen Quellkandidaten. Die folgende Gruppe 21.c umfasst den
gesamten transaktionalen Authoringvertrag samt übernommenen Altanforderungen
und bleibt als eigene vollständige W/R/C-Gruppe als Nächstes vorgesehen.
Die spätere gemeinsame Graph-/Scopeintegration 21.h wird nicht durch den
expliziten Quellenleser ersetzt. Normative Spezifikation, Pflichtreviews,
Freigaben, vollständige Plattform-/Releasebelege und die priorisierte
Gesamtfolge bleiben unverändert. Keine neue Detailklärung.

Erst nach erfolgreichem 21.b.C sind **894/996** Positionen abgeschlossen;
danach folgt **21.c.W**. Keine Vollsuite oder menschliche Abnahme behauptet.
