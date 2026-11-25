# Bundle 818 — Bindungsfehler beim belegten Work-Lock

Maßgebliche Quelle ist das native Fehler-Result
`0d33afe6ea7791d863aa20c785435571770121c4fb60ea73e093a5e940fe9619`.
Bundle 817 hat **21.e2.W** mit **26.458** bestandenen Tests als
`8a04ed84a2175c47c491bc307bd42a507f9de802` committed. Die 92 zuvor
fehlgeschlagenen Fälle waren Pflichtauswahl und bestanden. Im anschließenden
R-Gate bestanden **26.478** Tests; genau **ein** Test schlug fehl, ohne
Skip/XFail, Timeout oder Abbruch. R wurde nicht committed, C nicht installiert.
Bestätigt sind **904/999** Positionen. Der erfolgreiche W-Commit und der
frühere Klärungscommit bleiben erhalten und werden nicht wiederholt.

## Ursache und Korrektur

Der Fall `test_work_owner_selection_is_not_ignored_after_observation_changed`
mit Variante `wrong-owner` hält einen echten Work-Lock und wählt ausdrücklich
einen abweichenden Eigentümerhash. Die native Inspektion erkennt die
Abweichung, gab im bereits belegten Lockpfad jedoch den ursprünglichen
BlockingIOError weiter. Dadurch wurde der vorhandene Vertrag für eine
geänderte ausdrückliche Eigentümerbindung nicht erreicht.

Die Inspektion meldet bei einer vorhandenen, aber nicht passenden Auswahl
jetzt den bestehenden WorkBindingViolation, wie bereits der freie
Inspektionspfad. Ohne ausdrückliche Auswahl bleibt der bisherige
BlockingIOError erhalten. Nichtinspektierende Zugriffe bleiben unverändert.
Ein passender Hash benötigt weiterhin die vollständige Beobachtung, eigene
Attemptablage und alle aktuellen Datei-/Checkpointprüfungen. Der fremde Lock
wird weder übernommen noch freigegeben; eine falsche Auswahl erzeugt keinen
Override und keinen eigenen Fortsetzungsversuch. Der bestehende Fehlercleanup
schließt nur die eigenen Deskriptoren.

Die Regression bleibt bytegleich und verlangt weiterhin die genaue
Fehlerklasse, unveränderte Originalbytes und das Ausbleiben eines Forceklons.
Auch alle übrigen Tests, Varianten und stabilen IDs bleiben unverändert.
Die vollständigen bisherigen Pflichtmengen, Work-Lock-/Paket-/Fortsetzungs-
und Forceprüfungen sowie betroffene Aufrufer bleiben verpflichtend.
Es ist keine neue normative Detailentscheidung erforderlich; Spezifikation
0.2.109, aktive Katalogbindungen und sämtliche historischen Belege bleiben.

## Vollständiger Rest

Das Korrekturbundle führt genau **21.e2.R**, danach **21.e2.C** fort,
jeweils mit ursprünglicher Rolle implementation und Commitnachricht.
R erhält den gesamten geplanten Robustheitsumfang; C übernimmt die Korrektur
und die bereits geplante strukturelle Bereinigung mit unveränderten R-Tests.
Keine neue Klärung, Teilung oder Scopeerweiterung.

Jede Stage behält ihr eigenes gefiltertes N=3-plus-Pflichtauswahl-Gate vor
ihrem Commit. R bleibt in Gruppe 2; erst sein erfolgreicher Commit schaltet
zu C-Gruppe 0 weiter. Die Zielstände 905/906 gelten erst nach dem jeweiligen
Gate und Commit; anschließend folgt 21.f.W. Die finale CPU-/RSS-Abnahme
bleibt pending. Dev führt ausschließlich statische Prüfung, reine Collection
und native Paketvalidierung durch; dies ist keine bestandene Apply-Abnahme.
