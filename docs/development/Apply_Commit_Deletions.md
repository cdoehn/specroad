# Gebundene Dateilöschungen im Apply-Commitplan

Der separate Infrastrukturauftrag ergänzt den bestehenden Commitplan v2 um
explizite Löschungen. Produktumfang, Klärungsbefugnis, Budgets und Testgates
bleiben unverändert. Die Entfernung fachlicher APIs benötigt weiterhin ihren
eigenen bestätigten Planschritt. Der Produktplan wird dadurch nicht vorgezogen.

## Vertrag

Eine Stage mit Löschungen enthält zusätzlich zwei nichtleere Maps:

- `deletions`: Repositorypfad → SHA-256 der vollständigen ursprünglichen Datei.
- `delete_preimages`: dieselben Pfade → vollständige ursprüngliche Bytes in Base64.

Die Maps müssen exakt zusammenpassen. `after` und `payloads` enthalten weiter
nur existierende Zieldateien und dürfen keinen Löschpfad enthalten. Der Scope
ist die Vereinigung aus `after` und `deletions`. `before` bindet alle im
aktuellen Quellzustand existierenden Dateien dieses Scopes. Ein normaler
Löschpfad muss darin mit demselben Hash enthalten sein. Eine reine Löschstage
ist zulässig; ihre begründete Pflichtauswahl muss trotzdem nichtleer sein.

Die öffentlichen Plan-/Fortschrittsbelege enthalten Löschpfade und Hashes,
aber weder `payloads` noch `delete_preimages`. Der gebundene native Quell-Snapshot
und die ursprüngliche ZIP liefern die vollständigen Vorherbytes. Alte Stages
ohne die beiden Felder behalten ihren bisherigen öffentlichen Plan und Hash.
Version 1, Klärungsstages und unvollständige oder unbekannte Felder unterstützen
keine Löschung. Es gibt keine implizite Löschung durch ein fehlendes Payload.

`verification/apply_deletion_contract.json` muss bereits im bestätigten
Quellstand vorhanden sein. Das Infrastruktur-Bootstrapbundle selbst enthält
nur normale Schreiboperationen und kann daher noch mit dem alten v2-Vertrag
übergeben werden. Die passive Control-Unterstützung wird erst nach erfolgreichem
Apply separat installiert; Vorbereitung allein stellt keinen Dienst um.

## Dateigrenzen und Commit

Nur einzelne reguläre Dateien im Modus 0644 mit genau einem Hardlink werden
entfernt. Verzeichnisse, Symlinks, fremde Pfade, Git-Metadaten, Umbenennungen
und Moduswechsel sind keine Löschoperation. Elternverzeichnisse bleiben stehen.
Der native Apply besitzt weiterhin die Repositorysperre. Der eingefrorene
Entrypoint öffnet Eltern über No-follow-Deskriptoren, prüft Inode und vollständige
Vorherbytes unmittelbar vor dem Unlink und synchronisiert das Elternverzeichnis.
Es gibt keinen rekursiven Löschaufruf und keinen Rückgriff auf Shell-Patchcode.

Jede Stage hat weiterhin ihre eigene Materialisierung, N=3-plus-Pflichtauswahl,
unabhängige Gateprüfung und erst danach ihren Commit. Geprüft werden sowohl
die verbleibenden Zielbytes als auch die Abwesenheit gelöschter Dateien vor
und nach dem Gate, im Index und im tatsächlichen Commitbaum. Ein Fehler hält
an; vorherige Commits und der tatsächliche Arbeits-/Indexstand bleiben erhalten.

## Fehler und Fortsetzung

Nur die erste offene Stage einer an das native Fehler-Result gebundenen
Korrektur darf einen bereits fehlenden Löschpfad ohne `before` enthalten. Die
ursprüngliche Löschabsicht samt Hash und vollen Vorherbytes bleibt gebunden;
IDs, Rollen und die vollständige offene Folge bleiben erhalten. Eine neue
fehlende Datei kann nicht als angeblich frühere Löschung ausgegeben werden.
Eine wieder aufgetauchte Datei ist ein Fehler und wird nicht pauschal entfernt.
Keine automatische Wiederherstellung und kein Wiederholen erfolgreicher Commits.

Control rekonstruiert vollständige Textänderungen, Textzugänge und reguläre
Dateilöschungen aus dem nativen Snapshot, einschließlich leerer Dateien und
bereits gestagter Änderungen. Binäre Löschungen benötigen die vollständigen
nativen Basisbytes und deren Blobidentität. Binäre Zugänge sowie widersprüchliche
Index-/Arbeitsbaumänderungen desselben Pfads bleiben abgelehnt. Die passive
Rekonstruktion führt weder Git-Patches noch Repositorycode aus.

## Testdateien und Nachweis

Der Builder nimmt neue/geänderte, weiterhin vorhandene Testdateien automatisch
in die Pflichtauswahl auf. Gelöschte Tests werden nicht als ausführbare Selektoren
übernommen. Die Stage muss stattdessen fachlich passende, weiter gesammelte
Regressionen ausdrücklich benennen. Angeforderte verschwundene Selektoren
bleiben Fehler; `resolve_required` wird nicht abgeschwächt. Historische
Testnummern werden niemals gelöscht oder neu vergeben.

W implementiert Vertrag, Materialisierung, passive Rekonstruktion und die
vollständige erfolgreiche/fehlgeschlagene Gatefolge. R ergänzt robuste Eingabe-,
Dateiwechsel- und Fortsetzungsgrenzen mit adversarialen Regressionen. C trennt
den eingefrorenen Dateilöschhelfer strukturell ab; R-Tests bleiben bytegleich.
Die privaten Zustände und Collections sind keine bestandene Apply-Abnahme.
