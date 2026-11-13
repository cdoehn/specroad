# Bundle 681 — Prozessabbruchtests ohne künstliche Zeitgrenze

13. November 2026. Quelle ist das vollständig geprüfte Fehler-Result 680,
SHA-256 `623429e24db5942cc8610ed126511fea951eb6a409252a4c3d7e9e763262bf5d`.
18.k.R meldet 14048 bestandene und zwei fehlgeschlagene Tests in 5132,72
Sekunden; kein neuer Commit entstand. 18.k.C wurde nicht ausgebracht.
18.k.W bleibt als `306db567b8119b1933da0c34fbb5e55f1069aea9` committed.
Bestätigter Produktfortschritt ist deshalb weiterhin 760/900. Vorbereitete
R-/C-Planwerte werden erst durch das jeweilige erfolgreiche Apply-Gate wirksam.

## Belegter Fehler und begrenzte Reparatur

Beide Varianten von
`test_real_process_loss_requires_native_recovery_then_exactly_one_apply`
scheitern an derselben Assertion nach `child.join(300)`: Der frisch gestartete
Kindprozess lebt nach fünf Minuten noch. Die gesamte Call-Phase beträgt
910,25 beziehungsweise 995,34 Sekunden einschließlich der nativen Vorbereitung
im Elternprozess. Erfolgreiche verwandte Applytests desselben Laufs benötigen
bis zu 1745,2 Sekunden. Diese Messungen sind keine Messung der noch offenen
Kindprozesslaufzeit und kein Beweis für einen Deadlock. Die Annahme im Bericht
680, der Wechsel von fork auf spawn allein behebe die Abbruchfälle, ist damit
nicht als erfolgreicher Nachweis bestätigt.

Die Tests warten jetzt mit `child.join()` auf den tatsächlichen Prozessausgang
statt eine nicht spezifizierte Fünf-Minuten-Frist als fachlichen Fehler zu
werten. Das entspricht der bestehenden Testregel ohne künstliche Test- oder
Suite-Timeouts. Das äußere Apply behält seine Abbruchzuständigkeit; kein Runner,
Hostbudget oder lokaler Dienst wird durch dieses Bundle verändert. Eine andere
feste Frist würde nur dieselbe unbegründete Grenze verschieben.

Erhalten bleiben beide Testidentitäten, spawn mit ausschließlich echten
aufbewahrten Originalbytes, der echte os._exit(91) nach prepared/published,
die Exitcodeprüfung, Kill/Join/Close bei Unterbrechung des Elternprozesses,
die Recoverybarriere ohne Dateiveränderung, native gebundene Recovery,
schreibfreies bestätigtes Replay beziehungsweise expliziter neuer Retry sowie
genau eine Proposalrevision und sämtliche Fachobjektassertions. Ein früher
Kindprozessfehler bleibt ein Fehler; ein laufender Kindprozess gilt niemals
als bestandener Test. Es werden keine Ausnahmen, Skips oder Ersatzbelege erzeugt.

## Vollständiger Rest und Nachweisgrenze

Die ZIP führt ausschließlich die offenen IDs 18.k.R und 18.k.C mit ihren
bisherigen Rollen implementation, Commitnachrichten und vollständigen Abnahmen
fort. Alle im Result erhaltenen R-Dateien und die vorherigen Fehlerkorrekturen
bleiben enthalten. C behält die echte Strukturtrennung des Writeradapters ohne
neues Fachverhalten. Jeder Zustand wird einzeln ausgebracht, geprüft und erst
nach seinem eigenen N=3-plus-Pflichtauswahl-Gate committed.

Die vollständige bisherige Pflichtauswahl einschließlich der geänderten
Testdatei bleibt ungefiltert erforderlich. Testnummern und Testmenge bleiben
unverändert. Dev prüft nur Syntax, reine Collection, Stage-/Vorherbytes,
Commitumfang und die native ZIP. Keine Testkörper, Fixtures oder Testprozesse
werden in Dev ausgeführt; die reparierten Crash-/Recoveryfälle sind noch nicht
als bestanden belegt. Spezifikation und historische Berichte bleiben bytegleich;
es besteht keine normative Detaillücke und kein neuer Klärungspräfix.

Der ausdrücklich beauftragte native Control-Korrekturbudgetreset bleibt ein
separater OFF-PLAN-Folgeauftrag nach R/C. Diese Fortsetzung verändert weder
Budgets noch Control-Betriebsdaten und startet keinen Dienst.
