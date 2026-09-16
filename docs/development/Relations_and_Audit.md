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

## 2.h.R – Bindung und Fehlergrenzen

`observe_artifact_history` und `observe_relation_history` binden Beobachtungen
an die ID aus den tatsächlich übergebenen UTF-8-JSON-Bytes und deren SHA-256;
bei Relationen gehört die explizite Quellidentität dazu. Es werden keine Dateien
geöffnet, Referenzen aufgelöst, Programme ausgeführt oder Quellen authentifiziert.
`require_same_history` weist Konflikte, andere Identitäten und ungeklärte Herkunft
ab. Ein positives Ergebnis ist nur eine notwendige Identitätsvorbedingung.

Die Common-Schicht validiert angegebene Relationsidentitätsfelder paarweise.
Ihre vollständige Abwesenheit bleibt in der ausdrücklich partiellen Common-
Projektion zulässig. Das ist keine vollständige Relation oder Graphfreigabe.
Der spätere vollständige Relationsvertrag muss beide Pflichtfelder verlangen.

