# Bundle 758 — vollständiger Workerrest und Hostprofilgröße

19. November 2026. Maßgebliches natives Fehler-Result SHA-256:
`b95734ca541a7ac39112db31fde46da515f3f98e421ec37d4cd9f163c6d68e7a`.
HEAD `3975512044566bb7e8b2c830e044e83a2a63b7a0`; der vollständige erhaltene
Arbeitsstand ist die Korrekturbasis. 19.k.W/R/C sind mit 11651, 11801 und
11769 bestandenen Tests committed. Bestätigt sind damit **834/918**.
19.l.W wurde ausgebracht, aber vor Teststart mit `apply_partition_rejected`
abgewiesen; weder sein Testgate noch 19.l.R/C sind erfolgreich nachgewiesen.
Der ursprüngliche öffentliche Plan ist an SHA-256
`0a31bd870b25a4dd65f40d89574a606882633d12a95429a1191cc65fb2a31da2` gebunden.

## Diagnose und vollständige Korrektur

Das Result nennt die allgemeine Preflight-Abweisung ohne konkreten inneren
Exceptiontext. Die erhaltene gültige Collection, der Auswahl-Snapshot und
die lesend ausgewertete vorhandene Laufzeithistorie belegen unabhängig davon
ein zwingendes Größenproblem: 21641 ausgewählte Tests einschließlich 19840
Pflichttests, fünf Hosts, 105480 passende Hostprognosen und 21638 Baselines.
Schon diese drei Dictionaries benötigen mit der bisherigen Schlüsselalias-
Kodierung **23020344 Byte**, mehr als die Dateigrenze von **16000000 Byte**.
Hostkonfiguration und private Laufpfade sind darin noch nicht enthalten.
Dies ist eine statische Datenanalyse, kein nachgeholter Testlauf und keine
Behauptung eines nicht protokollierten Exceptiontexts.

Die interne Dateikodierung gruppiert bei weiterhin zu großen Profilen die
bestehenden Prognosen nach Testidentität. Der Schlüsselanteil vor dem letzten
Zeilenumbruch wird einmal gespeichert; die bestehenden Hostnamen und ihre
numerischen Werte bleiben je Test vollständig erhalten. Auswahl, separate
stabile IDs, Baselines, Worker, Umgebung und Quellenbindungen ändern sich
nicht. Kleine historische Profile und `selected-key-alias-v1` bleiben lesbar
und werden weiter verwendet, solange sie passen. Die neue Darstellung heißt
`selected-key-alias-and-forecasts-v1`; sie gilt nur für an ausgewählte IDs und
vorhandene Workerhosts gebundene Prognosen. Nicht darstellbare historische
freie Schlüssel werden niemals weggelassen oder umgedeutet.

Die Dateigrenze bleibt 16000000 Byte. Zusätzlich wird die expandierte
JSON-Darstellung vor Aufbau des Prognosedictionaries auf 32000000 Byte
begrenzt, entsprechend der maximalen Verdopplung durch die vorhandenen
Auswahlaliase. Fremde IDs/Hosts, leere oder falsche Gruppen, ungültige Zahlen,
Doppelschlüssel und zusätzliche Felder bleiben Fehler. Keine rekursive
Kompression, externen Verweise, Grenzanhebung, entfernten Tests, verlorenen
Prognosen oder Änderungen an Hostbelegung und Messhistorie. Eine nicht
passende Darstellung wird vor Schreiben der Profildatei abgewiesen.

Die Korrektur setzt den bestehenden Hostvertrag und die zuvor dokumentierte
Profilgrenze um. Es gibt keine neue normative Detaillücke oder Klärungsstage;
Spezifikation, Entwicklungsvertrag, Budgets und Freigaben bleiben unverändert.

## Fortsetzung und Abnahmen

Der vollständige offene Präfix besteht unverändert aus **19.l.W, 19.l.R,
19.l.C**, jeweils `implementation`, mit den ursprünglichen Commitnachrichten,
Fachumfängen und eigenen Gates. Die Korrektur gilt bereits in W und bleibt in
R/C bytegleich. Der bekannte echte Workerstart, seine R-Fehler-/Umgebungsgrenzen
und die reine C-Strukturierung bleiben getrennte Zustände. Erfolgreiches 19.k
wird nicht wiederholt. `correction_of` nennt ausschließlich diesen offenen
Dreierrest. Danach bleibt die nächste Produktposition **19.m.W**.

Die Pflichtauswahl erhält sämtliche bisherigen Dateien und ergänzt alle
Profil-, Hostpool-, Laufzeit-, Auswahl-, Live-/MOVE-/SPECULATE- und
Commit-Gate-Abnahmen. Neue Tests verlangen die verlustfreie Speicherung eines
vollständig relevanten Fünfhostprofils oberhalb der bisherigen Grenze,
beide historischen Formate, separate IDs, sämtliche negativen Eingaben und
eine begrenzte Expansion. Ein echter isolierter execnet-Proxytest prüft den
neuen Dateileser samt unveränderter Auswahl und nativen Workerbelegen.
Alle neuen und geänderten Tests laufen ausschließlich im jeweiligen Apply.

Dev führt nur Syntax, statische Prüfung, reine Collection und native
Paket-/Übergabeprüfung aus. Kein Testkörper, keine Fixture, kein Testprozess
wurde in Dev ausgeführt. Lokale Hostkonfigurationen und Laufdaten sind nicht
Teil der Payload. Die offenen echten Plattform-, Klassifikations- und
Releaseabnahmen aus [Bundle 757](bundle-757-language-distribution-worker.md)
bleiben erhalten. Die folgenden Zielwerte sind erst nach dem jeweiligen
vollständigen erfolgreichen Apply-Gate und Commit bestätigt.

Stageziel `19.l.W`: 835/918, erst nach eigenem Gate.
