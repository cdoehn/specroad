# Korrekturbundle 579 — vollständiger Rest 16.i.R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 579 — vollständiger Rest 16.i.R/C

Das maßgebliche native Fehler-Result hat SHA-256
`02ae83d6f8e63aabfe4e58f1d490454afc99fe3937b8818291d04095c0af07df`,
HEAD `b3e452022899f419b0a427017bb68abfc4ac3173` und den erhaltenen
Dirty-Fingerprint `685622155c49182b`. Bundle 578 stoppte in 16.i.R nach
gültiger Collection von 24763 Tests, aber vor jedem Testkörper mit
apply_partition_rejected. Kein Commit entstand. Der erhaltene Arbeitsstand
entspricht exakt der angekündigten R-Stage. Der bereits bestätigte W-Commit
bleibt erhalten; tatsächlicher Produktstand weiterhin 685/900.

Ursache: _apply_registry verglich den kompletten seit HEAD angehängten
Nummernblock mit einer erneut alphabetisch sortierten Menge. Am letzten
Commit waren 24718 Nummern registriert. Der fehlgeschlagene R-Stand hatte
bereits 49 weitere vergeben; Bundle 578 hängte sechs neue Regressionen an.
Alle 24773 Nummern sind eindeutig, der vollständige committed-Präfix bleibt
unverändert, und die 55 Ergänzungen entsprechen exakt der Collection.
Nur ihre globale Neusortierung würde 30 Positionen verschieben. Das ist
mit der dauerhaften Nummernvergabe und der Erhaltung des Fehlerstands nach
AGENTS und 2.5.2 unvereinbar. Die bisherige Dev-Paketprüfung gegen den letzten
Arbeitsstand übersah, dass Apply gegen den älteren committed-Stand prüft.

Technische Korrektur: Bei bereits bestehender N=3-Registry prüft der
Validator die exakte Ergänzungsmenge, ohne zuvor angehängte Blöcke erneut
zu sortieren. Der vollständige vorherige Präfix, eindeutige IDs, vollständige
Zuordnung zur aktuellen Collection sowie Nummerierungs- und Rotationsanker
bleiben zwingend. Unbekannte Ergänzungen und fehlende aktuelle IDs bleiben
Fehler. Erste Nummerierung, historische Zweierrotation und deren erstmaliger
Übergang zu N=3 behalten die bisherigen strengen Sortierregeln. Die reale
Registry bleibt in dieser Korrektur vollständig bytegleich; weder alte noch
neue Testnummern werden geändert, entfernt oder wiederverwendet.

Die bestehende Regression für Ergänzungen und reservierte alte Nummern wird
um zwei nachfolgende Korrekturen vor dem nächsten Commit erweitert. Dabei
sortieren die neuen Identitäten vor schon vergebenen, werden aber am Ende
angehängt. Beide Vergleichsbasen — letzter Commit und erhaltener Versuch —
müssen dieselben Nummern ergeben. Alle drei Gruppen, ihre Wiederholung am
gleichen HEAD, exakte Auswahlbelege und fehlende Umnummerierung werden
geprüft. Änderungen am erhaltenen Präfix und nicht gesammelte Ergänzungen
bleiben verboten; historische Verträge werden nicht neu ausgelegt. Keine
neuen Testidentitäten erforderlich; alle bestehenden Regressionen bleiben.

Zusätzlich validiert die native Paketvorbereitung nun die tatsächlichen
Registry-/Collection-Artefakte gegen beide Basen, einschließlich der im
Apply maßgeblichen committed-Registry. Das ist Metadatenprüfung, keine
Ausführung von Testkörpern. Alle Rotation-, Registry-, Laufzeitfilter- und
Commitplan-Regressionen werden für Apply ausdrücklich verpflichtend gewählt.
N=3, Pflichtvereinigung, Laufzeitdatenbank und erfolgreiche Commitrotation
bleiben unverändert; kein Gate wird übersprungen oder als grün behauptet.

Sämtliche Produkt- und Recoverykorrekturen aus Bundle 578 bleiben je Stage
bytegleich. Spezifikation 0.2.59 und aktive Katalogbindungen bleiben erhalten;
keine neue normative Detaillücke, Klärung oder Budgetänderung. Die vollständigen
IDs 16.i.R und 16.i.C behalten role=implementation. correction_of bindet
Planhash `c066a222848097cfc2e08e4b334804ed147d0c1a96453ba7d4e56182b7050123`
und genau diesen Rest. Erste Stage und Vorherbytes umfassen den gesamten
erhaltenen Dirty-Stand. R erhält Gruppe 1 und C anschließend Gruppe 2,
jeweils mit eigener vollständiger ungefilterter Pflichtauswahl vor dem Commit.
C bleibt die bereits angekündigte reine Extraktion der Beweisfunktionen;
Funktions-ASTs sind zu R identisch, Tests und Kataloge bytegleich.

Dev führt keine Verhaltenstests aus. Vorbereiteter Zwischenstand: C;
Häkchen und Zähler gelten erst nach erfolgreichem Apply-Gate und echtem
Commit. Vollständiger Abschluss ergäbe 687/900; danach bleibt 16.j.W offen.
Kein CI-, Watcher-, Control- oder Dienststart, keine lokale Konfiguration
in der Payload und keine eigene Warte-/Apply-Schleife.
