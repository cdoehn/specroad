# Normative Vorbereitung und native Veröffentlichung

`specroad.work.publication` verbindet einen vorhandenen originalen Change Plan
mit dem bestehenden nativen Transaktionspfad. Der vertrauenswürdige Host liefert
Registry, aktuellen `TargetModel`, `TargetPolicy`, Actor, Request-ID und zur
Veröffentlichung eine tatsächliche `PublicationAuthority`. Das Modul registriert
keinen CLI-Handler und gewinnt keine Berechtigung aus gespeicherten Work-Daten.

`prepare_normative_work(registry, plan, model=...)` erzeugt einen gebundenen
Anfangszustand mit zwei Vorbereitungseinheiten und dem nachgewiesenen aktuellen
Build. Es legt weder Work- noch Projektdateien an. Der Host veröffentlicht den
Anfang über den vorhandenen `CheckpointStore` in einem geschützten externen
Work-Root und behält dessen unabhängige Anfangsbindung.

`advance_normative_preparation(...)` bestätigt je Aufruf eine weitere Einheit:
zunächst die vollständige fachliche Zielprüfung über das gelieferte Modell,
danach den aktuellen Veröffentlichungs-Preflight mit tatsächlichen Quellbytes,
Inventar und Rechten. Beide Generationen binden denselben Assessmenthash. Eine
abweichende neue Bewertung ersetzt keine bereits bestätigte Vorbereitung.
Jeder Aufruf veröffentlicht seinen Checkpoint dauerhaft und löst den Work-Lock.
Projektdateien, Projektwriter-Lock, Journal und Receipts werden dabei nicht
angelegt oder verändert. Die Kontrollnachweise bleiben passive Daten; sie
ersetzen keine aktuelle Autorisierung oder Nachprüfung unter dem Writer-Lock.

`publish_normative_work(..., transaction_id=..., authority=...)` prüft zuerst
das zur ursprünglichen Request-ID gehörende Receipt über den bestehenden
Idempotenzleser. Ein bestätigter früherer Commit liefert dessen gespeichertes
Ergebnis und ursprüngliche IDs ohne zweiten Schreibversuch, auch nach verlorenem
Output. Ein fehlender Receipt erlaubt allein noch keine Veröffentlichung.

Für eine neue Transaktion müssen beide Vorbereitungen vorhanden sein. Die
aktuelle Transaktionsvorprüfung muss frei sein; Work startet keine automatische
Recovery. Die vollständige Ziel-/Basisprüfung wird frisch wiederholt. Danach
laufen Building, Staging, Veröffentlichung aller Planoperationen, Nachprüfung,
Receipts und die vorhandene sichere Bereinigung synchron unter demselben nativen
Projektwriter-Lock. Die bisherigen Autorisierungs- und Dateigrenzen gelten in
jeder Phase. Der Work-Lock bleibt während dieses Aufrufs gehalten, seine Bytes
und Runtime-Bindung werden erneut geprüft. Es gibt dabei keine neue
Work-Generation und keinen freiwilligen Promptwechsel zwischen Teilwrites.

Native Fehler erhalten ihr tatsächliches Journal, vorhandene Receipts und
bereits geänderte Bytes. Ein unterbrochener Transaktionsstand blockiert normale
Work-Fortsetzung und muss über den bestehenden Recoveryvertrag behandelt
werden. Es gibt weder automatischen Retry noch Rücksetzen auf vermutete
Vorherzustände. Die Fehlertests dieses ersten Schritts verwenden echte native
Dateioperationen mit gezielt ausgelösten I/O-Fehlern; sie behaupten keinen
Prozessabbruch- oder Stromausfallnachweis.

`NormativeWorkPublication` liefert einen unveränderlichen, maschinenlesbaren
Transaktionsnachweis. Sein `result_object` stammt aus dem bestätigten nativen
Request-Receipt. Technischer Work-Abschluss und endgültige Ergebnislieferung
werden damit nicht fingiert: der Vorbereitungscheckpoint bleibt erhalten,
`work_completion_recorded` ist `false`. Der historische Replay bestätigt
keinen inzwischen geänderten aktuellen Projektstand.

Der Umfang ist ein geschlossener Host-Adapter für bestehende Change Plans.
Jede Vorbereitungsphase verarbeitet ihr vollständiges Modell noch im Speicher.
Inkrementeller großer Planaufbau, feinere speicherbegrenzte Einheiten,
CLI-/Code-8-Anbindung und der finale normative Work-Ergebnisvertrag bleiben
offen. Native Veröffentlichung wird auch später nicht in fachliche Teilcommits
zerlegt. Die Requirement-Nachweise bleiben partiell.
