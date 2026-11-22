# Bundle 786 — frisches Distributionsziel für 20.f und 20.g

22. November 2026. Quelle ist das native Fehler-Result mit SHA-256
`72f02c9850d4c0e62d6b67df854ea9b0b2eb9b2892cadb6834e90ad50ece9291`.
Bundle 785 hat keinen Commit erzeugt: Das Gate für **20.f.W** meldet
15.715 bestandene Tests und 48 Setupfehler. Die gemeinsame Fixture übergab
den von `tmp_path_factory.mktemp()` schon angelegten Ordner an den Core-Builder.
Dieser verweigert vertragsgemäß vorhandene Ausgabeziele mit `FileExistsError`;
die 48 Modul-/PYZ-Paritätsfälle erreichten dadurch ihren Testkörper nicht.
Der native erhaltene Arbeitsstand entspricht vollständig dem angekündigten W.
Bestätigt bleiben 879/918 Produktcommits bis einschließlich 20.e.C; die
Erledigtmarkierung im erhaltenen W-Zielstand ist keine erfolgreiche Abnahme.

Die Fixture baut die Distribution jetzt in ein noch nicht vorhandenes
Unterverzeichnis ihres privaten temporären Elternordners. Der Builder, seine
Überschreibsperre, Modul-/PYZ-Erzeugung, Testidentitäten, sämtliche Varianten
und alle Verhaltensoracles bleiben unverändert. Dieselbe Korrektur gilt in
allen sechs Zielständen, einschließlich der importierenden Cache-Randfälle
und Sicherheitsprüfungen.

Die statische Folgeprüfung zeigt außerdem einen bisher durch den Setupfehler
verdeckten Unterschied in den Voraussetzungen des W-Paritätsoracles:
`observe_operational_preflight` beobachtet das Vorhandensein von `.specroad/cache`,
während der Referenzlauf bisher vor dessen Anlage im Kindprozess stattfand.
Der Testhost legt nun den leeren privaten Cache-Elternordner vor dem Referenzlauf
an. Die echten Cachebytes entstehen weiterhin erst in der gebauten Distribution;
der vollständige Ergebnis-/Diagnose-/Preflightvergleich entfernt keine Felder.
Cache-Off-Sperre, echter Cachetreffer, aktuelle Originalbytes und unverändertes
Dateiinventar werden weiterhin geprüft. Es liegt keine normative
Spezifikationslücke vor; kein weiterer Testfehler wird als beobachtet behauptet.

Der vollständige belegte Rest **20.f.W/R/C, 20.g.W/R/C** wird mit unveränderten
IDs, Rollen `implementation` und exakten Commitnachrichten fortgeführt.
`correction_of` bindet den öffentlichen Plan von 785; vollständige Vorherbytes
und alle vier Zustandswerte binden das neue Fehler-Result. Kein erfolgreicher
Commit wird wiederholt. Jeder Zustand behält sein eigenes Apply-Gate vor dem
Commit; der Endstand wird nicht vorab ausgebracht. Die ursprünglichen
Pflichtauswahlen bleiben erhalten, hinzu kommen die vorhandenen Build- und
Distributionsregressionen für das unveränderte Zielverzeichnisverhalten.

Dev prüft ausschließlich statisch, Syntax, reine Collection, Stage-Rekonstruktion
und native Bundle-/Fortsetzungsbindung. **Keine Verhaltenstests in Dev.**
Der Planfortschritt des jeweiligen Zielstands gilt erst nach dessen erfolgreichem
Apply-Gate und Commit. Erst nach allen sechs Stages sind 885/918 erreicht;
danach folgt 20.h.W. Menschliche Reviews, Leistungsmessungen und Releasegates
bleiben offen. Der [ursprüngliche Bericht 785](bundle-785-work-security.md)
bleibt als Vorbereitungshistorie erhalten; ein Erfolg von 785 wird nicht behauptet.
