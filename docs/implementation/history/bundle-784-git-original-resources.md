# Bundle 784 — Originalressourcen im Git-Wiederanlauftest

Das native Fehler-Result hat SHA-256
`ed0899457bd8b274e85b7bd1299a73df30ab05d66bca643e218ce598e6baef5b`.
APPROVAL-BINDING-783 wurde nach 7.786 bestandenen Tests committed;
20.c.W nach 10.794 Tests als `628254b99ab4004f56931fb81a6e3c620524b4cd`.
Das anschließende 20.c.R-Gate meldet 10.890 bestandene und drei fehlgeschlagene
Tests. Beide erfolgreichen Commits bleiben erhalten. Der vollständige offene
Rest ist 20.c.R, 20.c.C, 20.e.W, 20.e.R und 20.e.C, jeweils implementation.

Alle drei Fehler entstehen im Aufbau von
`test_original_attachment_and_primary_document_are_required_in_a_fresh_git_root`:
Das Modell enthält bereits einen Anhangverweis, aber noch keinen gebundenen
Descriptor mit Originalbytes (`target_referenced_attachment_unbound`).
Die Korrektur bindet Descriptor und Bytes gemeinsam vor der Modellprüfung.
Der historische negative Evidence-Datensatz erhält einen aus den tatsächlichen
Fixture-Originalen berechneten Subject-/Konfigurationsbezug. Der gemeinsame
Git-Testadapter führt auch die anwendbaren Lifecycle-, Evidence- und
Ressourcengates durch den vollständigen nativen Validator aus. Diese im
Codepfad erkennbaren Folgeanforderungen werden nicht mit Erfolgsstubs ersetzt.

Die positiven und negativen Oracles bleiben vollständig: tatsächlicher
separater Git-Checkout, unveränderte Originalbytes und Evidence, Pflichtanhang,
Primärdokument, echte Receipts, neuer expliziter Write und unverändert gesperrter
Altroot. Es wird kein Produktvalidator abgeschwächt. Die Korrektur gilt in allen
fünf abhängigen Zielständen; die bisherigen Pflichtauswahlen bleiben enthalten.
Beide C-Stufen behalten gegenüber ihrem R-Stand identische fachliche Oracles.

Keine neue fachliche Entscheidung oder Klärungsstage. Die bereits committeden
Spec-/Reviewverträge, offenen menschlichen Abnahmen und geplanten R-48..R-75
bleiben unverändert. Dev prüft statisch, sammelt Tests und validiert das Paket;
keine Testkörper oder Fixtures werden ausgeführt. Jeder Zielstand gilt erst
nach seinem eigenen erfolgreichen Apply-Gate und Commit.
