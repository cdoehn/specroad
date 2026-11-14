# WORKER-LIMIT-12 und CONTROL-BUDGET-20 — Bundle 683

Ausdrückliche Nutzeraufträge vom 13. und 14. November 2026. Die zunächst
private Vorbereitung ist mit dem Folgeauftrag vom 14. November jetzt zur
Übernahme in Apply freigegeben. Normativ gelten Spezifikation 2.4.3.6 und 2.5.3.

## Umfang und Entscheidung

Neue volle Klärungsbudgets und der Standard neuer Korrekturfolgen umfassen
zwanzig Plätze. Verifizierte neue Folgeaufträge erlauben bei positivem Rest
optionale Klärung auch nach Apply-Fehlern. Der geprüfte Projektmarker grenzt
diese neue Folgeentscheidung von historischen Drei-/Fünferverträgen ab.
Explizites Abschalten, belegte offene Präfixe, vollständige Korrektur-IDs/Rollen
und alte Promptbytes bleiben verbindlich. Installation, Konfigurationsänderung,
Teilcommit und Neustart füllen keinen vorhandenen Zähler auf.

Der gemeinsame Workerstandard ist zwölf, einschließlich ausgelassener
Host-worker-Angaben und Profiling. Explizite Grenzen, CPU-Kapazität, Nested=1,
Nice-/I/O-Priorität und die separat explizite manuelle CI-Grenze zehn bleiben.

Bloß höhere Zahlen würden die bisherige Folge-Sperre behalten; ein Umschreiben
alter Zähler würde deren Belege entwerten. Die additive, markergebundene Regel
erhält beides. Der direkte Nutzerauftrag ist die fachliche Befugnis; kein
künstlicher delegierter Klärungspräfix und keine zusätzliche Produktposition.

## Getrennte Commitabnahmen

- W: Vollständiger neuer normaler Ablauf mit Marker und Standardbudgets20,
  CLI/Konfiguration, budgetabhängiger Folgefreigabe, historischen Verträgen,
  expliziter Abschaltung und unveränderter Präfixfortsetzung. Workerstandard12
  für Runner, Hostkonfiguration und Profiling unter den bestehenden Grenzen.
- R: Ganze Reparatur- und Klärungsfolgen bis zum zwanzigsten Verbrauch,
  Sperre vor einem weiteren Versuch, Erhalt alter verbrauchter Budgets,
  Ablehnung eines zweiten Präfixes sowie native Reset-/Erhaltungsbelege.
  Der synthetische Zeitstempel-Helfer unterstützt dabei zweistellige Stunden.
- C: Wiederholte Budgetgrenzen in einem gemeinsamen Modul und Workerdefaults
  in den vorhandenen gemeinsamen Helfern konsolidieren; sämtliche W/R-Tests
  und Ergebnisse bleiben unverändert.

Umsetzungsstand dieses Commitziels: **W**. Erst das erfolgreiche eigene
Apply-Gate und der tatsächliche Commit bestätigen diesen Zustand. Dev führt
keine Verhaltenstests aus. Jede Stage prüft N=3 plus vollständige Pflichtauswahl.

Quelle ist das erfolgreiche Hauptlinien-Result nach Import682, SHA-256
`5fdf1fac898ccf06d91a5cf040d8b4b3c504c4cf88f411b0d6ba96d1a45d4124`.
Die Recovery-Entscheidung006, ihre offenen Katalogeinträge und die Reihenfolge
18.s–18.x vor18.l bleiben erhalten:762/918 abgeschlossen, nächste Position18.s.W.
Die private Originalvorbereitung bleibt unverändert. Keine Dienstinstallation,
Betriebskonfiguration, Control-Fortsetzung oder Betreiberreset als Nebenwirkung.
Bestehende explizite kleinere Konfigurationswerte benötigen später eine
ausdrücklich gewählte Betriebsumstellung; dieses Bundle überschreibt sie nicht.
