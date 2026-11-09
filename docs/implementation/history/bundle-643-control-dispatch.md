# Korrektur 643 — parallele Proxy-Worker und offener Control-Fix

Bundle 642 scheiterte beim Start der zweiten Weiterleitung über denselben
execnet-Proxy, vor dem ersten Testkörper; kein Commit entstand. Native Quelle:
`e0689c6d24e1e10eeb2334e213c5a59a12ea200a58c35b88c281c778fcc646bf`.
Der Fehler `concurrent remote_exec would cause deadlock for main_thread_only
execmodel` betrifft den gemeinsam verwendeten Proxy. Die bisherige synthetische
Integration nutzte nur einen Worker hinter diesem Proxy.

Der Proxy verwendet nun ausdrücklich execnets `thread`-Modell, damit mehrere
Weiterleitungskanäle gleichzeitig bedient werden. Die eigentlichen pytest-Worker
bleiben getrennte Prozesse mit xdist-eigenem `main_thread_only`. Produktion und
synthetische Integration verwenden dieselbe kleine Gateway-Beschreibung.
Der bestehende Erfolgstest startet bis zu zwei Worker innerhalb der ermittelten
CPU-Grenze und prüft zusätzlich, dass die Testkörper auf ihrem Hauptthread laufen.
Sechs native Tests, alle 18 Phasen, Hostbelege, Quellenbindung und der vorhandene
Absturzfall bleiben erhalten. Alle bisherigen Testkennungen bleiben unverändert.

Der vollständige offene Commit `CONTROL-DISPATCH-FIX`, Rolle `correction`,
behält seine Control-Änderungen und zehn Regressionen. Alle zuvor eingebrachten
Dateien sind mit vollständigen Vorherbytes an das neue Fehler-Result gebunden.
Die Pflichtauswahl umfasst zusätzlich alle Hostpool-Tests und deren relevante
Runner-/Messregressionen. Gefilterte N=3-Gruppe und Commitgate bleiben erhalten.
Keine Verhaltenstests in Dev, keine neue normative Klärung. Produktfortschritt
bleibt 729/900; 18.a.W bleibt offen. Control wird erst nach erfolgreicher
Apply-Abnahme aus dem geprüften Release installiert und ausdrücklich gestartet.
