# Korrekturbundle 613 — Auditoptionen im CLI-Vertrag, Rest 17.h.W/R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 613 — Auditoptionen im CLI-Vertrag, Rest 17.h.W/R/C

Maßgeblich ist das nativ geprüfte Fehler-Result
`specroad-apply_Result_220901_1105_daf9f3.zip`, SHA-256
`c51b2c8e5f7796a8e2114fd8187e84147f08b271c840e1e8a45a5c8cd91b0baa`.
Seine vollständige Bindung lautet repo_id
`a33ed6cf-0a97-4b73-b11a-d4239e7a2145`, HEAD
`6602f56ad8990bbf0eebc694be2e9184d36e8c56`, Fingerprint
`6327c14ed56da917`, Algorithmus `patchharbor-state-v1`.

Das eigenständige Gate von MERGE-RESOLUTION-612 bestand mit 6955 Tests;
der Klärungscommit ist der oben gebundene HEAD und bleibt erhalten.
17.h.W scheiterte vor seinem Commit mit einem Fehler und 8027 bestandenen
Tests. Der erhaltene Arbeitsstand ist vollständig der angekündigte W-Stand.
Der bestätigte Produktfortschritt bleibt damit 714/900, zuletzt 17.g.C;
die vorbereiteten W-Checkboxen sind noch kein erfolgreicher Produktcommit.

Ursache ist die allgemeine Erwartung in
`DescriptionRobustnessTests.test_current_handlers_reject_work_and_write_options_before_effects`:
Sie verbot `--actor-id` pauschal auch für `merge.resolve`. Der bereits
committete Vertrag 10.15.5 verlangt dort ausdrücklich Actor-/UTC-Auditdaten
für einen deklarativen Plan; diese erteilen keine Schreib- oder Reviewbefugnis.
Die Korrektur ergänzt genau diesen Befehlsfall im bestehenden Verhaltenstest:
Actor-/Zeitoptionen sind Pflicht, die Klasse bleibt plan_output/input_read,
ohne Writer-Lock, Projektpflicht, Schreibpfade oder externen Work-Zustand.
Work-, Resume-, Request-, Dry-run-, Projekt- und Proposal-Optionen bleiben
abgewiesen; alle bestehenden Sperren der übrigen Befehle bleiben unverändert.
Produktcode, normative Spec und Abnahmekriterien werden nicht geändert.

Diese normale Korrektur führt sämtliche offenen IDs und Rollen des Plans
`a53ffe02d5aa80b49e33829688aead556e7b8057145593ae23755a87b69ecd40`
vollständig fort: 17.h.W, 17.h.R und 17.h.C, jeweils implementation.
Kein erneuter Klärungscommit, keine neue Detailentscheidung oder Budgetänderung.
Die Vorherbytes und der komplette erhaltene W-Umfang werden neu an das
Fehler-Result gebunden. W startet erneut in derselben N=3-Gruppe 1.
Erst nach erfolgreichem eigenem Gate und Commit wird jeweils R bzw. C
ausgebracht. Ihre unveränderten fachlichen Umfänge und die strukturelle
R/C-Trennung bleiben erhalten; kein Endstand wird vorab installiert.

Die vollständige Description-Regressionsdatei und alle ursprünglichen
Pflichtdateien bleiben in jedem zugehörigen Apply-Gate ungefiltert enthalten.
Testidentitäten und dauerhafte Nummern werden nicht geändert. Dev führt
nur Syntaxprüfung, reine Collection und native Paket-/Rekonstruktionsprüfung
aus, keine Verhaltenstests. Der jeweilige Zielzähler 715/716/717 und die
Abschluss-Bundlenummer 613 werden erst mit dem entsprechenden erfolgreichen
Apply-Commit wirksam. 17.i–17.l sowie die Gesamtfreigabe von M17 bleiben offen.
