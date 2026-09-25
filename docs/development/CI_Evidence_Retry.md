# CI-Evidence: wiederholbare lesende Übertragung

Bundle 021: lokaler Apply erfolgreich, alle fünf Matrixjobs erfolgreich. Das
Execution-Log enthält SHA-gebundene Berichte für 3.11 bis 3.14 und das komplette
GitHub-Logarchiv, aber der Download des Python-3.10-Artefakts lieferte
`CIObservationError: gh_api_exit_1`. Ursache (DNS, Verbindung, Server, Rechte)
ist daraus nicht bestimmbar. Der Beobachter behauptete deshalb keine vollständige
Testevidence. Diese konservative Trennung bleibt unverändert.

Vorher verwendeten Run-/Job-/Logabfragen die bestehenden drei Versuche, die
Artefaktliste und die einzelnen Downloads dagegen nicht. Jetzt verwendet auch
`collect_artifacts` dieselbe vom Beobachter übergebene Retryfunktion. Sie umschließt
nur GETs und die vollständige Listenabfrage, nicht Hash-, Identitäts- oder
Reportprüfung. Alle Wiederholungen eines ZIP-Downloads betreffen dieselbe bereits
geprüfte Artefakt-ID. Das abschließende Run-/Attempt-Recheck bleibt erhalten.

Dauerhafte Fehler bleiben unvollständige Evidence. Ein dritter fehlgeschlagener
Versuch bricht den betroffenen Abruf ab; andere Berichte werden weiterhin
bewahrt. Interrupts werden nicht abgefangen, um Tests neu zu starten oder die CI
abzubrechen. Kein anderer Run, keine anderen Credentials, kein automatischer
Rerun. Es kommen keine Test- oder Suite-Timeouts hinzu. Die bestehende technische
API-Frist wird nicht geändert. Zugangsdaten oder rohe gh-Fehlertexte werden nicht
in Retryereignisse aufgenommen.

Lokale Regressionen verwenden ausschließlich synthetische Transporte. Ein echter
Online-Download aus dem privaten Repository ist damit nicht nachgewiesen. Die
Korrektur verbessert den nächsten Abruf; sie rekonstruiert keinen fehlenden alten
Report und garantiert nicht das Verschwinden eines dauerhaften Netzwerkproblems.
