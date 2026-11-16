# Bundle 708 — Korrektur des vollständigen Restes 18.u.W/R/C

Datum: 15. November 2026. Grundlage ist ausschließlich das native Fehler-Result
`specroad-apply_Result_173331_1115_288703.zip`, SHA-256
`3f34e850e287fae50c3d1caf68bd1f9abae60da5ac4326c909afa3d217525e79`,
Basiscommit `fc398fd4217296aa7832261f4ddb93549e023a64`, Fingerprint
`a579be623bde2091` nach `patchharbor-state-v1`, Repository
`a33ed6cf-0a97-4b73-b11a-d4239e7a2145`.

Bundle 707 scheiterte im eigenen W-Gate: 87 fehlgeschlagene und 13.989 bestandene
Tests, kein Commit. Die offenen IDs und Rollen bleiben vollständig erhalten:
18.u.W, 18.u.R, 18.u.C, jeweils implementation. Die Korrektur bindet den alten
öffentlichen Plan `cb43802358b334af8c9b82a74ca68837efacabf4f6a313ec47ad1a36b015b6ff`
und übernimmt alle tatsächlichen uncommitteten W-Dateien als Vorherstand.
Kein bereits erfolgreicher Commit wird wiederholt.

Die vorhandenen Verträge C.2.1, N und P.6 bestimmen die Korrekturen; keine neue
Detailentscheidung, kein Klärungspräfix und keine Budgetänderung.

| Befund | Korrektur und vorbereitete Abnahme |
| --- | --- |
| Unklassifizierte Betriebsdateien wurden wie eine belegte unterbrochene Transaktion behandelt. | Die Diagnose unterscheidet unknown von beschädigten Markern/aktiven Altjournalen. Beides sperrt unverändert normale Arbeit, ohne automatische Reparatur. |
| Work-Abbruch hielt den echten Rootmutex, dessen erneuter Probezugriff die eigene Prüfung blockierte. | Ein kurzlebiger nativer Lesekontext verwendet exakt diesen noch gehaltenen Mutex. Rootidentität und Prozessbesitz bleiben geprüft; keine Ownerdatei entsteht, keine Sperre wird vorzeitig gelöst, Marker und unbekannte Dateien bleiben blockierend. Neue Verhaltenstests prüfen falschen Root, freigegebenen Kontext, reale konkurrierende Sperre und erhaltene Bytes. |
| Normale Work-Publikation und Prompt prüften die Requestbelege vor ihrer eigenen Abbruchsperre. | Beide prüfen zunächst den gemeinsamen nativen Preflight und erhalten den Work-Fehlervertrag ohne neue Autorisierung oder Nebenwirkung. |
| Ein W-Abschluss mit tatsächlichem PublicationPreflight und geprüften Zielbytes war fälschlich als nur historisch gekennzeichnet. | Die W-Projektion meldet die erfolgte aktuelle Zielprüfung; historische Wiederholung bleibt current_target_verified=false und replayed=true. R behält seine zusätzlichen vollständigen Eingangs-, Namespace-, Byte- und Inodeprüfungen. |
| Dokument- und Proposaltests lasen alte Journal-/Receiptfelder oder erwarteten automatische Reparatur. | Die bestehenden Testidentitäten prüfen die neuen vollständigen Writebelege, unveränderte fachliche Ergebnisse und echte Vorher-/Teil-/Nachherbytes. Abbrüche erhalten Marker/Owner und sperren die Wiederholung. Reale No-replace-Dateiveröffentlichung wird am tatsächlich verwendeten nativen Primitiv beobachtet. |
| Work-Tests behandelten fertige Receiptbytes oder Markerentfernung vor Lockfreigabe schon als erfolgreichen Prozessabschluss. | Bestehende echte Prozessabbrüche bleiben erhalten und müssen blockieren. Zwei zusätzliche Fälle verlieren die Ausgabe erst nach Rückkehr des nativen Writers und tatsächlicher Lockfreigabe; nur diese dürfen das Originalergebnis ohne zweite Änderung ausliefern. |

Zusätzlich meldet das Result einen vor seiner Collection ausgefallenen Worker
gw81, ohne zugeteilten Test. Die vorhandenen Laufartefakte liefern keinen
belegten konkreten Reparaturansatz für diesen Startabbruch. Worker-, Collection-,
Ressourcen- und Hostpool-Nachweise bleiben daher vollständig verpflichtend;
keine Fehlermeldung wird ignoriert und kein Erfolg daraus abgeleitet.

W enthält den vollständigen korrigierten normalen Adapterausschnitt. R führt
alle bisherigen Randfall- und Receiptbeweisergänzungen mit den Korrekturen fort.
C behält die strukturelle Konsolidierung; sämtliche Testbytes bleiben gleich R.
Jede Stage wird einzeln hergestellt, mit ihrer fälligen N=3-Gruppe plus
ungefilterter Pflichtauswahl geprüft und erst danach committed. Der Endstand
wird nicht vorab installiert. Die komplette alte Pflichtauswahl, alle geänderten
Tests und transitive Nutzer geänderter Testhelfer bleiben enthalten.

Die im Fehler-Result bereits zugewiesenen Testnummern bleiben unverändert.
Neue Identitäten werden je tatsächlich anstehender Stage angehängt; die noch
nicht ausgeführten R-Ergänzungen folgen den neuen W-Tests. Keine bestehende
Testidentität oder parametrisierte Variante entfällt.

Dev führt nur Syntax, statische Prüfung, reine Collection und native
Paketvalidierung aus. Die erste Collection mit dem Systeminterpreter fand die
Testabhängigkeiten execnet/xdist nicht; die unveränderte vorhandene Dev-venv ist
für die vollständige Collection maßgeblich. Keine Testkörper oder Fixtures
wurden in Dev ausgeführt. Neue Verhaltensabnahme steht ausschließlich in Apply an.

Der bestätigte Fortschritt bleibt vor Apply bei 768/918. Die vollständige
Restgruppe ist bereits umfangreich; es gibt keinen künstlich verkürzten
Planschritt und keinen neuen Spezialwriter-Anhang. 18.v.W ist der nächste
Schritt nach erfolgreichem Abschluss der gesamten Folge. Die Planwerte in
jedem Zwischenstand sind weiterhin an dessen eigenes erfolgreiches Gate und
Commit gebunden. Historie von Bundle 707 bleibt unverändert erhalten.

Vorbereiteter Zustand **18.u.C**: Ziel nach eigenem Gate **771/918**, danach **18.v.W**.
