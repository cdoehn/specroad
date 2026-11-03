"""Stable source identity and the one-turn Dev handoff contract."""
import hashlib
import json
from copy import deepcopy
from .config import Config
from .errors import ControlError
from .legacy_job_contract import legacy_prompt


SCHEMA = {"type": "object", "additionalProperties": False,
          "properties": {"source_result_sha256": {"type": "string"},
                         "status": {"type": "string", "enum": ["patch_ready", "no_work", "blocked"]},
                         "patch_sha256": {"type": "string"}, "message": {"type": "string"}},
          "required": ["source_result_sha256", "status", "patch_sha256", "message"]}


def scope(config: Config) -> str:
    values = [str(config.repository.resolve()), str(config.exchange.resolve()), config.repo_id,
              config.session_id, str(config.codex_home.resolve())]
    if config.thread_cwd is not None:
        values.append(str(config.thread_cwd.resolve()))
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


def contract(value=None):
    """Absent version is the immutable pre-014 contract, never a new grant."""
    if value is None:
        return {'version': 1, 'clarification_allowed': False}
    if isinstance(value, dict) and type(value.get('version')) is int and value['version'] in (3, 4):
        if (set(value) != ({'version', 'clarification_allowed', 'clarification_limit', 'clarifications_remaining'} | ({'clarification_continuation'} if value['version'] == 4 else set()))
                or type(value.get('clarification_allowed')) is not bool
                or type(value.get('clarification_limit')) is not int or value['clarification_limit'] != 3
                or type(value.get('clarifications_remaining')) is not int
                or not 0 <= value['clarifications_remaining'] <= 3
                or (value['clarification_allowed'] and value['clarifications_remaining'] == 0)):
            raise ControlError('request_contract_invalid', 'Invalid bounded clarification authority.')
        if value['version'] == 4 and (type(value['clarification_continuation']) is not bool
                or value['clarification_continuation'] and value['clarification_allowed']):
            raise ControlError('request_contract_invalid', 'Continuation cannot grant fresh clarification authority.')
        return dict(value)
    if (not isinstance(value, dict) or set(value) != {'version', 'clarification_allowed'}
            or type(value['version']) is not int or value['version'] not in (1, 2)
            or type(value['clarification_allowed']) is not bool
            or (value['version'] == 1 and value['clarification_allowed'])):
        raise ControlError('request_contract_invalid', 'Unknown or damaged development contract; no inferred permission.')
    return dict(value)


def new_contract(remaining=3, *, allowed=None, version=3, continuation=False):
    value = {'version': version, 'clarification_limit': 3,
             'clarifications_remaining': remaining,
             'clarification_allowed': remaining > 0 if allowed is None else allowed}
    if version == 4:
        value['clarification_continuation'] = continuation
    elif continuation:
        raise ControlError('request_contract_invalid', 'Legacy contracts cannot gain continuation authority.')
    return contract(value)


def schema_for(value=None):
    selected = contract(value)
    result = deepcopy(SCHEMA)
    if selected['version'] in (2, 3) and selected['clarification_allowed']:
        result['properties']['status']['enum'].append('spec_clarification')
    if selected['version'] == 4 and (selected['clarification_allowed'] or selected['clarification_continuation']):
        result['properties']['status']['enum'].append('patch_ready_with_clarification')
    return result


def prompt_for(source: dict, request_contract=None) -> str:
    selected = contract(request_contract)
    if selected['version'] == 4:
        from .mixed_prompt import mixed_prompt
        return mixed_prompt(source, selected)
    if selected['version'] == 3:
        return budget_prompt(source, selected)
    original = legacy_prompt(source)
    if selected['version'] == 1:
        return original
    original = original.replace('bei Unklarheit status=blocked',
        'bei einer nicht im folgenden Entscheidungsrahmen loesbaren Unklarheit status=blocked')
    return original + '\nCONTROL_DECISION_CONTRACT\n' + json.dumps(selected, sort_keys=True) + (
        '\nBegrenzte Spezifikationsklaerung: Pruefe zuerst, ob die massgeblichen '
        'SpecRoad-Projektvorgaben die delegierte Entscheidungsregel SPECROAD-DECISION-1 '
        'ausdruecklich enthalten. Dieser Control-Auftrag erteilt diese fachliche '
        'Befugnis nicht selbst und erlaubt nicht, sie selbst einzufuehren. Ohne '
        'diese Regel gelten die bisherigen Grenzen; regulaere klare Planarbeit bleibt erlaubt. '
        'Innerhalb der erteilten Befugnis: Luecke und Alternativen untersuchen, kleinste '
        'konsistente, konservative und reversible Loesung waehlen, Begruendung und '
        'Abnahmekriterien zuerst verbindlich in Spezifikation und Plan dokumentieren. '
        'Explizite Nutzerentscheidungen, Funktionsumfang, Sicherheitsanforderungen, '
        'Kompatibilitaetszusagen, notwendige menschliche Freigaben und Nachweise '
        'nicht abschwaechen. Keine Fakten, Reviews oder Risikoakzeptanzen erfinden. '
        'Fehlende unverzichtbare externe Fakten oder ein Konflikt ausserhalb der '
        'Befugnis verlangen blocked mit konkreter Frage, Empfehlung und Grenze. '
        'Ist eine eigene normative Klaerung noetig, liefere bei clarification_allowed=true '
        'genau ein OFF-PLAN-Spezifikationsbundle mit status=spec_clarification und dessen '
        'echtem patch_sha256. Der regulaere Planschritt bleibt offen. Kein zweites '
        'Bundle aus demselben Result, keine eigene Warte- oder Modellschleife. '
        'Nach dem Apply beauftragt Control den offenen Planschritt erneut. '
        'Bei clarification_allowed=false ist kein weiteres Klaerungsbundle erlaubt: '
        'implementiere die bereits geklaerte Vorgabe oder melde blocked. '
        'patch_ready bezeichnet regulaere Umsetzung oder eine technische Korrektur, '
        'niemals ein als Umsetzung getarntes weiteres Spezifikationsbundle. '
        'Nur nach erfolgreichem, sauberem Apply eines solchen normalen Bundles wird '
        'eine neue Klaerung moeglich. Unklassifizierte uebernommene Bundles setzen '
        'dieses Budget nicht zurueck. Auch bei Klaerung gelten alle W/R/C-, Test-, '
        'Vierfachbindungs- und Uebergaberegeln. Bei spec_clarification gilt wie bei '
        'patch_ready: fertige ZIP nativ pruefen, SHA melden und sofort beenden.')


def budget_prompt(source, selected):
    original = legacy_prompt(source).replace('bei Unklarheit status=blocked',
        'bei einer nicht im folgenden Entscheidungsrahmen loesbaren Unklarheit status=blocked')
    return original + '\nCONTROL_DECISION_CONTRACT\n' + json.dumps(selected, sort_keys=True) + (
        '\nBegrenzte Spezifikationsklaerung mit Vertrag 3: Die massgeblichen '
        'SpecRoad-Projektvorgaben muessen SPECROAD-DECISION-1 und ausdruecklich '
        'Vertrag 3 mit bis zu drei aufeinanderfolgenden Klaerungsbundles erlauben. '
        'Control erteilt diese fachliche Befugnis nicht selbst. Eine alte Grenze '
        'von einem Klaerungsbundle darf nicht eigenmaechtig erweitert werden. '
        'Ohne diese neue Projektfreigabe keine gesonderte automatische Klaerung; '
        'regulaere klare Planarbeit bleibt erlaubt. '
        'Innerhalb der Befugnis: Luecke und Alternativen pruefen, die kleinste '
        'konsistente, konservative und reversible Loesung waehlen und zuerst '
        'Begruendung, normative Spezifikation und Planabnahmen fortschreiben. '
        'Explizite Nutzerentscheidungen, Scope, Sicherheitsanforderungen, '
        'Kompatibilitaet, menschliche Reviews und erforderliche Nachweise nicht '
        'abschwaechen. Keine Fakten, Reviews oder Risikoakzeptanzen erfinden. '
        'Fehlende unverzichtbare Fakten oder Grenzen der Befugnis verlangen '
        'blocked mit konkreter Frage, Empfehlung und Begruendung. '
        'clarifications_remaining ist das gespeicherte Restbudget fuer '
        'spec_clarification; clarification_allowed=false sperrt weitere Klaerung '
        'auch bei positivem Restbudget. Bei Erlaubnis liefere genau ein '
        'state-gebundenes OFF-PLAN-Spezifikationsbundle mit spec_clarification, '
        'echter source_result_sha256 und patch_sha256. Der Planschritt bleibt offen. '
        'Der Watcher uebernimmt Apply und Tests. Nur Control beauftragt danach '
        'den naechsten Schritt. Kein zweites Bundle aus derselben Quelle und '
        'keine eigene Warte-, Modell- oder Apply-Schleife. '
        'Jede Klaerungsuebergabe verbraucht einen Platz; nach drei aufeinanderfolgenden '
        'Klaerungen ist nur Umsetzung oder blocked erlaubt. Fehler, unbekannte '
        'Handoffs, Retry, Pause und Neustart erteilen kein neues Budget. '
        'Nur erfolgreiches sauberes Apply mit Abschlusscommit eines als patch_ready '
        'klassifizierten regulaeren Umsetzungs- oder echten technischen '
        'Korrekturbundles oeffnet wieder drei Plaetze. Klaerung nicht als '
        'patch_ready oder Alibi-Produktcommit verbergen. '
        'Bestehende Test-, W/R/C- und Uebergaberegeln gelten. Die vier Antwortfelder '
        'bleiben unveraendert. Fertige ZIP nativ pruefen, SHA melden und sofort beenden.')


def continuation_prompt(source, evidence, request_contract=None):
    original = prompt_for(source, request_contract).split('\n', 2)
    return ('Fortsetzung des erhaltenen SpecRoad-Entwicklungsauftrags nach bestaetigtem Overload.\n'
            + original[1] + '\n'
            + 'Bezug: ' + json.dumps({key: evidence[key] for key in
                ('turn_id', 'workspace_sha256', 'history_sha256')}, sort_keys=True) + '\n'
            + 'Pruefe ZUERST den erhaltenen Zwischenstand und die Aktionen des vorigen Turns: '
            'Dateien, Index, bestehende Commits, Testbelege, temporaere Artefakte und Exchange. '
            'Setze denselben Auftrag am belegten Arbeitsstand fort. Keine Wiederholung von N, '
            'kein Reset, kein Verwerfen oder Wiederherstellen alter Dateien. Bereits ausgefuehrte '
            'Befehle und Seiteneffekte NICHT blind wiederholen. Fehlgeschlagene Tests sind keine '
            'erfolgreichen Belege; weitere Tests nur bei Bedarf. Ein bereits fertiges gebundenes '
            'Bundle hat Vorrang: nur dessen SHA melden, kein zweites Bundle erzeugen. '
            'Bei unklaren externen Wirkungen oder fremder Arbeit status=blocked. '
            'Dieser Turn ist ein eigener begrenzter Folgeversuch, keine eigene Retry-Schleife. '
            + original[2])
