# Korrekturbundle 602 — echte Releaseprüfung im Test, vollständiger R/C-Rest (C)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 602 — echte Releaseprüfung im Test, vollständiger R/C-Rest (C)

Basis: natives Fehler-Result SHA-256 `27a2527111bcfcf697914297fa626f0e340482088af9221b1f3a75b5cc571e99`,
HEAD `fb3bd6e8111c7f4d7dc621b7b2e0ac7226f98380`, dirty Fingerprint
`04585fea6361be23`. CONTROL-BLOCKED-601.W ist nach 7.651 bestandenen
Tests committed und wird nicht wiederholt. Der vollständige erhaltene R-Stand
entspricht bytegenau der angekündigten R-Stage. Das R-Gate bestand 7.677 Tests;
ein Test scheiterte vor dem R-Commit. C wurde noch nicht ausgebracht.

Ursache: Der Test importierte require_release erst nach dem Fixture-Setup,
das genau diese Funktion für die isolierten Bedienfälle ersetzt. Dadurch
prüfte der spezielle Release-Negativtest den Ersatz statt der echten Funktion.
Die Korrektur bindet die echte Funktion bereits beim Modulimport, wie die
bestehenden Release-Negativtests. Der Test ruft weiterhin die produktive
Fähigkeitsprüfung auf; nur deren externe Installations-/Receipt-Eingaben
bleiben kontrolliert. Kein Skip, kein Xfail, keine abgeschwächte Erwartung und
keine Änderung des Control-Produktcodes oder der normativen Spezifikation.

Offene IDs, Rollen, Reihenfolge und Nachrichten bleiben CONTROL-BLOCKED-601.R
und CONTROL-BLOCKED-601.C, jeweils implementation. R enthält den gesamten
erhaltenen uncommitted Scope samt dieser Korrektur; C erhält die angekündigte
rein strukturelle Bereinigung. 702/900 und 17.d.W bleiben unverändert.
Beide Stages bekommen erneut ihr eigenes N=3-plus-vollständige-Pflichtauswahl-
Gate. In Dev keine Verhaltenstests; dieser Text behauptet keinen Erfolg.
