"""Pre-014 prompt bytes retained for historical dispatch and recovery proofs."""
import json


def legacy_prompt(source: dict) -> str:
    facts = {key: source[key] for key in ("path", "sha256", "binding", "run_id")}
    return ("Einmaliger SpecRoad-Entwicklungsdurchlauf N, KEINE S-Schleife. "
            "Die externe Linux-Steuerung wartet auf Apply. Pruefe genau dieses vollstaendig "
            "gebundene Result und dessen technische Basis:\n" + json.dumps(facts, ensure_ascii=False)
            + "\nLies die generierte CHAT_INSTRUCTIONS.md im ZIP-Root, context.json, environment.json, "
            "manifest.json, logs/run.json, Ausfuehrungslogs und Snapshot sowie den bestaetigten "
            "Implementierungsplan und die Spezifikation. Beachte die aktuellen Dev-AGENTS.md und "
            "deren W/R/C- und Testregeln. Kein direkter Zugriff zur Aenderung von specroad-apply, "
            "kein Git-Push/Commit/Fetch in Dev, kein Start von CI, Watcher oder Control. "
            "Erzeuge hoechstens EIN kanonisches Folgebundle, ausschliesslich an die obigen vier "
            "Bindungswerte gebunden, und veroeffentliche die fertige ZIP atomar im gemeinsamen Exchange. "
            "Pruefe, dass das Result noch massgeblich ist; bei Zweifel status=blocked, kein Patch. "
            "Warte danach NICHT auf Tests/Result, keine wiederholten Statusabfragen, keine "
            "Hintergrundfortsetzung. Beende den Auftrag sofort nach Uebergabe. "
            "Deine letzte Antwort ist das angeforderte JSON: source_result_sha256 unveraendert, "
            "status=patch_ready nur fuer eine wirklich fertige ZIP, deren vollstaendiger SHA-256 "
            "in patch_sha256 steht. Bei abgeschlossenem Plan status=no_work, bei Unklarheit "
            "status=blocked, dann patch_sha256 leer. message kurz begruenden. "
            "Keine lokalen Konfigurationen, Zugangsdaten oder Session-IDs in Payload/Bundle kopieren.")
