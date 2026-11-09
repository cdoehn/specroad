# Korrektur 644 — Testdoppelgänger und Busy-Wartevertrag

Das native Result von Bundle 643
`1ee62f21cb70afdf12bc69a4707d55786a64c0b52060151fa6b25a892fa3e32b`
belegt 8.004 ausgeführte Tests: 7.895 bestanden, 109 fehlgeschlagen, kein Commit.
Die parallelen Proxy-Worker und ihre Integration liefen erfolgreich. 108 Fehler
stammen aus demselben fehlenden `TypedCodex.check` im isolierten Testdoppelgänger;
ein bestehender Recoverytest erwartet noch ein Anhalten bei bekannt aktivem
Chat, obwohl der neue vollständige Vorstartpfad dort ohne Claim wartet.

Der Testdoppelgänger erhält den bereits von `FakeCodex` verwendeten lesenden
Check-Vertrag. Echte Transport-, Metadaten-, Aktivitäts- und Dispatchprüfungen
bleiben in der vorhandenen unabhängigen Integration. Der Recoverytest prüft
nun das Warteergebnis, unveränderten bereitstehenden Auftrag ohne Fehler,
keinen Modellaufruf während der Aktivität, erhaltene Originalbytes des Versuchs
und genau einen Aufruf nach freiem Chat. Kein Produktguard wird abgeschwächt.

Der vollständige offene Commit `CONTROL-DISPATCH-FIX`, Rolle `correction`,
bleibt erhalten. Alle zuvor eingebrachten Dateien und Vorherbytes werden an
das neue Fehler-Result gebunden. Control- und Hostpool-Code bleiben bytegleich;
nur die beiden Teststellen, Bundlezählung und dieser Nachweis ändern sich.
Die vollständige Pflichtauswahl einschließlich aller Control- und Hostpool-
Regressionen plus fällige gefilterte N=3-Gruppe bleibt erhalten.

Dev führt keine Verhaltenstests aus. Bestehende Testkennungen und fachlicher
Planfortschritt 729/900 bleiben unverändert; 18.a.W bleibt offen. Erst ein
vollständig erfolgreicher sauberer Apply erlaubt Commit, Control-Deployment
und die ausdrücklich beauftragte Wiederaufnahme der Automatik.
