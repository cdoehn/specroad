# Dev2-Bundles 001–005: abgeschlossene Apply-Abnahmen

Statusnachtrag vom 11. November 2026. Dieser Beleg ersetzt die früheren
Vorbereitungs-/Offen-Aussagen zu den hier genannten OFF-PLAN-Arbeiten.
Er verändert weder die 900 Produktpositionen noch Betriebsfreigaben oder
historische Result-Artefakte. Die Statusnachpflege ist Teil der gesonderten Integration nach Dev.

## Control und getrennte Laufzeithistorien

Die Folgen `RUNTIME-LANES.W/R/C`, `CONTROL-X.W/R/C`,
`CONTROL-INSTANCES.W/R/C` und `CONTROL-MONITOR.W/R/C` sind vollständig
über die Dev2-Bundles 001–004 committed. Korrekturen führten jeweils den
offenen Rest fort; erfolgreiche Commits wurden erhalten.

Abschluss: Commit `c06a35a2484199d5fae48fb96b0cb2481659882e`,
10. November 2026 um 20:31:55 Uhr MEZ, sauberer Apply2-Endzustand.
Result: `specroad-apply2_Result_185543_1110_e0cef3.zip`.
SHA-256: `0f219ccb77298653c4b72558e050ebc7ae63897f776ad00fcf869b7ca2f149e6`.

## Testoptimierungen und Profiling

Bundle 005 enthält die Optimierungen aller zehn untersuchten M17-Tests und
das Profilingwerkzeug für alle Tests, Top-N und freie Testauswahlen.
Die sechs Gates bestanden insgesamt 47.493 Testausführungen:

| Commit-ID | Commit | Bestandene Testausführungen |
| --- | --- | ---: |
| TEST-PERFORMANCE.W | `924fa0e94d1acf6a542e874b480b033bd29dfb33` | 8.573 |
| TEST-PERFORMANCE.R | `012f3959643307d8864af7d8fc5a363eab660273` | 8.448 |
| TEST-PERFORMANCE.C | `f8a0fb6147660b01250afa89857233c8e4c0a6e8` | 8.656 |
| TEST-PROFILING.W | `5e8e39f6870c6ef46a56ce29802cc7e33d424c8d` | 7.175 |
| TEST-PROFILING.R | `39dea145db7981386cd169f63b8a0f5e24e97c1a` | 7.206 |
| TEST-PROFILING.C | `7850d52ae4e25f90fac0cabdd90d288308d93ef8` | 7.435 |

Abschluss: 10. November 2026 um 23:59:57 Uhr MEZ, sauberer Apply2-Endzustand,
kein offener Rest und vollständiger Bundle-Erfolgsmarker.
Result: `specroad-apply2_Result_211012_1110_d4fd9c.zip`.
SHA-256: `8a7916c7fb417ef6950a290c2a76eaf278ec42d862e2fe50d8523783675e0895`.
Dies sind sechs N=3-plus-Pflichtauswahl-Gates auf aufeinanderfolgenden
Quellständen, keine ungefilterte Vollsuite und kein Geschwindigkeitsbenchmark.

## Verbleibende Punkte

- Geprüfte Control-Version samt Monitor installieren und Betriebsintegration
  prüfen. Repository-Abnahme allein aktualisiert keine installierte Version.
- Vorher-/Nachher-Laufzeiten der zehn Tests unter Beachtung von Host,
  Parallelität und Instrumentierung vergleichen; vorhandene Rohprofile erhalten.
- Dev2 bleibt manuell. Einrichtung einer weiteren Control-Instanz oder Start
  der Automatik ist kein Bestandteil dieses Abschlusses.

Die Vorbereitung der Integration nach Dev ist ein getrennter Auftrag.
Dieser Statusnachtrag behauptet weder einen Merge noch eine Übernahme der
Dev2-Abnahmen als Abnahme eines zusammengeführten Quellstands.
