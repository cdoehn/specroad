# Korrekturbundle 615 — Relationenidentität und vollständiger Rest 17.i.W/R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 615 — Relationenidentität und vollständiger Rest 17.i.W/R/C

Maßgeblich ist das nativ geprüfte Fehler-Result `specroad-apply_Result_001533_1106_27b7b4.zip`,
SHA-256 `a3443f49206a674f045cca62f5690e82a084cc6866227d26d5fae5774f0fed44`.
Bindung: repo_id `a33ed6cf-0a97-4b73-b11a-d4239e7a2145`,
HEAD `4fd62556ad4ea5c7b10ea733f49c3352236f7fc8`,
Fingerprint `8aa2035a3b00ccdf`, Algorithmus `patchharbor-state-v1`.

MERGE-METADATA-614 bestand sein eigenständiges Gate mit 6989 Tests und wurde
als obiger HEAD committed. Danach scheiterte 17.i.W vor seinem Commit mit
zwei Fehlern und 8167 bestandenen Tests. R und C wurden nicht begonnen.
Der erhaltene Arbeitsstand entspricht vollständig dem angekündigten W-Stand.
Der bestätigte Produktfortschritt bleibt 717/900, zuletzt 17.h.C; vorbereitete
Checkboxen und Zielzähler sind noch keine erfolgreichen Produktcommits.

Beide Fehler entstehen beim Sortieren der eingebetteten Relationsobjekte:
Das native Payload-Feld heißt `relation_id`, nicht `id`. Die Korrektur verwendet
dieses vorhandene Feld in W, R und C. Die Artefakt- und Inventaridentitäten
bleiben unverändert. Der Test für disjunkte Relationen prüft die feste erwartete
Reihenfolge der vollständigen Originalobjekte, einschließlich fehlender
optionaler Auditfelder, statt die fehlerhafte Sortierberechnung zu wiederholen.
Der Auflösungstest erhält explizite gültige gemeinsame Erstellungszeit und
Erstellungsakteur: Bisher griff seine nachgelagerte Erwartung auf ein gar nicht
vorhandenes optionales `created_at` zu. Er prüft nun das vollständige aufgelöste
Relationsobjekt mit unveränderter Erstellungsherkunft und weiterhin die neue
Besitzerrevision sowie den gebundenen Auflösungsakteur. Keine gemockte
Validierung, keine normative Änderung oder abgeschwächte Abnahme.

Diese normale Korrektur führt alle offenen IDs und Rollen aus Plan
`73ee670dedf7a886372568ef21e236bcdc102af03872642d17b74f2710635611`
fort: 17.i.W, 17.i.R und 17.i.C, jeweils implementation. Der erfolgreiche
Klärungscommit wird nicht wiederholt; keine neue Klärung oder Budgetänderung.
Die vollständigen Vorherbytes und der erhaltene W-Umfang binden an dieses
Fehler-Result. W behält N=3-Gruppe 2. Erst nach erfolgreichem eigenem Gate
und Commit folgt jeweils der nächste Zustand; der Endstand wird nie vorab
installiert. Die vollständigen W/R/C-Umfänge und die R/C-Strukturtrennung
bleiben erhalten. Die folgende ursprüngliche Bundle-614-Beschreibung bleibt
als Entwurfsnachweis bestehen; maßgebliche Übergabe ist diese Korrektur 615.

Alle ursprünglich verpflichtenden Testdateien bleiben ungefilterte
Pflichtauswahl, insbesondere die gesamte geänderte Metadaten-Testdatei.
Testidentitäten und dauerhafte Nummern bleiben unverändert. Dev führt nur
Syntaxprüfung, reine Collection und native Paket-/Rekonstruktionsprüfung aus,
keine Verhaltenstests. Zielzähler 718/719/720 und Abschluss-Bundlenummer 615
werden erst durch das entsprechende erfolgreiche Apply-Gate und den echten
Commit wirksam. 17.j–17.l, M17-Gesamtfreigabe und menschliche Reviews bleiben
offen; keine Vollsuite- oder Releaseabnahme wird behauptet.
