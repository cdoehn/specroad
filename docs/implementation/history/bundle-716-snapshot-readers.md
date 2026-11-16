# Bundle 716 — Snapshotbelege und vollständiger Rest 18.v.W/R/C

## Belegter Ausgangspunkt

Result 715 mit SHA-256 `287e4ec3b3a0b51dcf8d63050359e749db98df570788a63ba9b0c99cd5c3d589` bestätigt den
Klärungscommit `BOOTSTRAP-SNAPSHOT-715` nach 7.442 bestandenen Tests,
Commit `1e986d18a8900a70300807dcab3f220e7a52dd95`.
18.v.W scheiterte danach mit 18 Fehlern und 11.889 bestandenen Tests.
Der native Snapshot enthält den nicht committeten W-Zustand; R/C wurden
nicht ausgebracht. Produktfortschritt bleibt bestätigt bei 771/918.

Die Korrektur bindet genau diesen erhaltenen Zustand und den alten
Commitplan `d9cf497375d739ba7a24aaebfb70679703144e203fcdcb4d81bc6b4807d615e4`.
Alle offenen IDs `18.v.W`, `18.v.R`, `18.v.C` und ihre Rollen
`implementation` bleiben erhalten. Kein erfolgreicher Commit wird wiederholt,
kein weiterer Klärungspräfix oder neuer Planschritt wird angehängt.
Spezifikation 0.2.91 und ihre SHA-256-Bindungen bleiben bytegleich.

## Ursachen und Korrektur

- RequestReceipt v2 las veröffentlichte Pfade mit dem alten JSON-Pfadvertrag.
  Der Leser verwendet nun denselben normativen Ressourcenpfadvertrag wie
  der v2-Writer, einschließlich gebundener Sprachregisterdateien. Die exakten
  Pfade müssen weiterhin durch die vollständige native Beleggruppe bewiesen sein.
- Die gemeinsame historische Qualifikation erwartete noch flache v1-Dateieffekte.
  Sie liest nun die optionalen v2-Vorher-/Nachherbindungen einschließlich
  Löschungen und folgt nur belegten Byteketten. Revisionsgrenzen stammen aus
  den im Snapshotplan gebundenen Nachherbytes. Unbelegte Zieländerungen bleiben Fehler.
- Unbekannte Transaktionsformate werden vor einem Legacy-Fallback als ungültige
  Schreibbelege abgewiesen; ein beschädigter v2-Beleg ist kein fehlendes Altjournal.
- Der native Lock-Plattformnachweis erfolgt vor Bootstrap-/Modellbeobachtung.
  Damit bleibt `native_lock_unavailable` erhalten, ohne einen Ersatzlock einzuführen.
- Echte I/O-Abbrüche des gemeinsamen Snapshotwriters liefern Exit 5 und
  `write_state=unknown`. Tatsächliche Teilbytes, Marker und Owner bleiben erhalten.
- Der Merge-Abbruchtest unterbricht die reale Grenze `effect_synced:0` statt
  eines nicht mehr ausgeführten Spezialjournalereignisses. Der Init-Test
  erzeugt beim Schnitt `rules` einen tatsächlich zu verschiebenden Pfad;
  die Wiederverwendung leerer vorhandener Verzeichnisse bleibt an den übrigen
  Schnitten geprüft. Der Ancestry-Angriff erwartet den nativen Sicherheitscode 7
  und prüft weiterhin die vollständige Unverändertheit fremder Bytes.

## Getrennte Stufen und Abnahme

W enthält die vollständige ursprüngliche Umsetzung mit den korrigierten
Lesern und bestehenden positiven, Fehler- und Abbruchoracles. R führt alle
ursprünglichen Randfall-/Sicherheitsarbeiten fort und ergänzt zehn Fälle zu
echten v2-Belegen, gelöschten/fehlenden/veränderten Zieldateien und gefälschten
Requestpfaden. Bereits ausgelieferte Testnummern behalten ihre Position;
neue Nummern werden erst hinter dem bestehenden R-Register angehängt.
C bleibt die ursprüngliche strukturelle Bereinigung mit fortgeführten
Korrekturen. Tests, Tools und Verifikation bleiben gegenüber R bytegleich.

Dieser Snapshot ist `18.v.C`; sein prospektiver Zielwert ist 774/918,
nächster Plancommit `18.w.W`. Diese Werte gelten
erst nach dem eigenen erfolgreichen Apply-Gate und Commit.
18.w bleibt unverändert offen.

Alle 18 tatsächlich fehlgeschlagenen Fälle und ihre vollständigen Testdateien,
alle neuen/geänderten Testdateien und transitive Fixtureverbraucher gehören
zur Pflichtauswahl. Migration/Merge, aktuelle und historische Qualifikation,
Receipt-/Lock-/Pfadschutz, Bootstrap/Extraktion und bestehende Restore-Leser
bleiben ausdrücklich abgedeckt. Die bisherige Pflichtauswahl wird nicht verkleinert.
Jede Stage erhält genau ihr eigenes Gate aus fälliger gefilterter N=3-Gruppe
plus ungefilterten Pflichttests vor ihrem Commit.

In Dev laufen ausschließlich statische Prüfung, reine Collection und native
Paketvalidierung, keine Testkörper oder Fixtures. Hieraus entsteht kein
Apply-, Vollsuite-, Release- oder Plattform-Erfolgsnachweis. Keine Betriebsdaten,
Zugangsdaten oder lokalen Konfigurationen werden übertragen; keine Dienste,
Automatik oder direkten Änderungen in Apply werden durch Dev gestartet.
