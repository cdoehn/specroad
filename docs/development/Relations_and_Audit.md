# Relationsidentität und Auditwerte

## 2.h.W – Relationsidentität und Historienvergleich

`allocate_relation_identity(RelationInventory(...))` verwendet 16 Bytes aus der
kryptografischen Zufallsquelle und die kanonische REL-Base32-Grammatik. Die drei
ID-Inventare werden ausdrücklich übergeben, nicht automatisch gescannt oder
persistent reserviert. Quell-/Ziel-IDs und Position sind keine Generatorinputs.
`derived128-v1` bleibt für Bestandsidentitäten lesbar, ist aber kein regulärer
Erzeugungsmodus. Die bestehende Migrationsimplementierung wird nicht vorgezogen.

`HistoryOrigin(subject_id, namespace, creation_event)` ist eine interne,
ausdrücklich zu bindende Herkunftsbeobachtung, KEIN neues Artefaktfeld und kein
Authentizitätsnachweis. Der spätere vertrauenswürdige Quelladapter muss den
ursprünglichen Erzeugungsvorgang aus echter Historie bestimmen. Branchname,
aktueller Commit, Anzeigename oder gleiche Auditzeiten reichen allein nicht.

`compare_histories` unterscheidet `different_identity`, `identical_copy`,
`same_history`, `identity_conflict` und `unresolved`. Fehlende Herkunft bleibt
ungeklärt, auch bei gleichen Bytes. Unterschiedliche bekannte Ursprünge unter
gleicher ID sind Konflikte, auch bei gleichen Bytes. Gleiche Historie besagt
nicht, dass geänderte Inhalte konfliktfrei gemerged werden dürfen.

