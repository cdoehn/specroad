# FORCE-CONTRACT-804 — geschlossene gemeinsame Transportbindung

23. November 2026; delegiert gemäß SPECROAD-DECISION-1 und Vertrag 4,
mit ausdrücklich zugelassener optionaler Klärung vor Umsetzung.

X.12 bestimmt Forceverhalten und Raw-Ziele, lässt aber die genaue Feldform,
Hashdomäne und Version der negativen Ausführungsbelege offen. Ohne diese
Festlegung könnten API, gespeicherter Plan und Request-Replay denselben
Auftrag unterschiedlich identifizieren. Die Änderung präzisiert X.12.1.

Alternativen: freie optionale Zusatzfelder würden widersprüchliche Bindungen
zulassen; normale Erfolgsversionen für negative Forcebefunde könnten Leser
zu einer unberechtigten positiven Aussage verleiten. Gewählt sind geschlossene
additive 1.3.0-Felder und eigene passive Forcebeleg-Versionen. Alte 1.2.0-Bytes
und ihre Hashdomäne bleiben erhalten. Dies ist die kleinste getrennt lesbare,
reversible Vertragserweiterung ohne zusätzliche Produktoperation.

21.d setzt den gemeinsamen Request-/Gate-/Envelope-/Writer-/Lesekern um.
21.e bleibt die ausdrücklich geplante Anbindung sämtlicher Fachadapter und
Marker-/Lock-Sonderfälle; keine vollständige Erfüllung von SR-REQ-0783 wird
vorweg behauptet. W führt die konkrete gemeinsame Schreibstrecke ein, R
vervollständigt Byte-/Quellwechsel-/Receiptfehler und partielle Lesbarkeit,
C verschiebt reine Ergebnisvalidatoren ohne Änderung der Fachoracles.
R-86/R-87 bleiben vollständige spätere Integrationsabnahmen. Der gemeinsame
Kern hat reale normale Ablehnungs-/Force-Ziel-Fälle und unabhängige Bytebelege.

Keine menschliche Reviewentscheidung, Messung, Apply-Abnahme oder Freigabe
wird durch diesen Klärungscommit behauptet. Für jeden Produktbuild bleiben
die echten aktuellen Messbelege und das eigene native Apply-Gate erforderlich.

<a id="planabnahmen-21d"></a>
## Ergänzende verbindliche Planabnahmen für 21.d

Diese Detaildatei gehört über den Planeinstieg zum vollständigen Plan.
Sie ergänzt den unveränderten Umfang und die Abnahmen von M21/21.d vor
der Umsetzung; Positionsnummern, Voraussetzungen und Commitnachrichten bleiben.
Die genaue Feld- und Hashnorm hat ausschließlich X.12.1 als maßgebliche Stelle.

- **W:** Explizite Raw-/strukturierte CLI- und API-Anforderung, konkrete
  vollständige Zielbytes, ursprüngliche negative oder unbekannte Diagnosen,
  normaler Ablehnungsvergleich und unabhängige Hostverweigerung. Gateklassen
  inventarisieren und den gemeinsamen vorhandenen Writer-/Readpfad verwenden;
  keine künstliche Zustimmung, kein implizites Force und kein Erfolg bei
  unvollständiger Veröffentlichung. Abweichende Requestbindung ist kein Replay.
- **R:** Leere/binäre/neue/gelöschte Ressourcen, explizite Reparatur einer
  unlesbaren Konfiguration, veraltete Byte-/Modellhashes, aktuelle Quellwechsel,
  partielle beziehungsweise blockierte Validierung und physische I/O-Fehler
  prüfen. Vollständige Original-Receiptketten mit exakten Zielbytes erhalten;
  fehlende, manipulierte oder umgebundene Nachweise dürfen nichts freigeben.
- **C:** Alle W/R-Oracles bleiben verpflichtend und die Testquellen bytegleich
  zu R; reine Ergebnisfunktionen strukturell auslagern, ohne Fachverhalten oder
  zulässige Seiteneffekte zu verändern.

Alle Fachadapter und Marker-/Lock-Sonderfälle bleiben im vollständigen
Anschlussschritt 21.e; R-86/R-87 erhalten ihre spätere komponentenübergreifende
Integration. Jeder Zustand verlangt weiterhin sein eigenes Apply-Gate samt
aktuellem Build-Messbeleg. Diese Abnahmen sind keine bestandenen Nachweise.
