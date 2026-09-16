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

## 2.i.W – Explizite Auditwerte

`Revision`, `Actor` und `UtcTimestamp` sind unveränderbare Werte. Die Actorarten
sind `human`, `ai`, `ci`, `tool`; die ID bleibt ein nichtleerer Unicode-Wert.
Es erfolgt keine Anmeldung, Identitätsprüfung oder Ableitung aus Umgebungsdaten.
UTC-Zeitwerte bewahren alle Nachkommastellen und werden nicht auf die sechs
Nachkommastellen eines Python-datetime abgerundet. Schaltsekunden werden nur als
syntaktisch mögliche Juni-/Dezember-Kandidaten geprüft, nicht online bestätigt.

`new_artifact_audit(actor=..., planned_at=...)` liefert Revision 1 sowie identische
Erstellungs-/Änderungswerte aus genau diesen gebundenen Inputs. Der Aufruf legt
kein Artefakt an. `artifact_audit` liest bestehende Werte ohne Neustempelung.
JSON-Zahlen mit ganzzahligem Wert wie 1.0 bleiben als Revision gültig; bool ist
keine Revision. Die numerische JSON-Serialisierungsgrenze bleibt unabhängig.

