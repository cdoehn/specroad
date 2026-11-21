"""Known-adapter observation checks, independent of Work channel framing."""
from ._values import require, shape
from ._report_values import ENGINE_FACTS


def check_language_unit(request, entry, engine, original, value):
    """Validate known-adapter semantics, not merely generic report geometry."""
    from .registry import builtin_descriptor
    from .language_scores import ScoreDecision, SCORE_SEMANTICS
    from ._reference_candidates import CANDIDATES
    from ._score_values import format_units, parse_threshold
    from ._text_policy import request_policy, text_length
    from .language_policy import observe_subject
    from ..storage.language_registry import bundled_language_registry
    if entry['descriptor'] != builtin_descriptor().data:
        from .reports import subject_result
        require(value['subject'] == subject_result(original, status='open', payload={})
                and value['findings'] == [], 'analyzer_work_external_execution', exit_code=5)
        return
    _, _, policy = request_policy(request)
    shape(value['subject']['payload'], ('specroad.language_detection',))
    payload = value['subject']['payload']['specroad.language_detection']
    shape(payload, ('decision', 'comparison'))
    decision = payload['decision']
    shape(decision, ('status', 'reason', 'language', 'score_semantics', 'scores'))
    require(decision['score_semantics'] == SCORE_SEMANTICS
        and type(decision['status']) is str and decision['status'] in
        ('detected','undetermined','unavailable','failed'), 'analyzer_work_decision', exit_code=5)
    scores = decision['scores']
    require(type(scores) is list and len(scores) in (0,2), 'analyzer_work_scores', exit_code=5)
    ranks = []
    for row in scores:
        shape(row, ('language','score'))
        require(row['language'] in (*CANDIDATES,'und','zxx'), 'analyzer_work_scores', exit_code=5)
        units = parse_threshold(row['score'], 'work_score')
        require(row['score'] == format_units(units), 'analyzer_work_scores', exit_code=5)
        ranks.append((row['language'], units))
    require(len({r[0] for r in ranks}) == len(ranks)
        and ranks == sorted(ranks, key=lambda r:(-r[1],r[0])), 'analyzer_work_scores', exit_code=5)
    short = text_length(original['value']) < policy['min_text_codepoints']
    status, reason, language = decision['status'], decision['reason'], decision['language']
    if short:
        require((status, reason, language, ranks) == ('undetermined','insufficient_text',None,[]),
                'analyzer_work_short_text', exit_code=5)
    elif status in ('failed','unavailable'):
        require(not ranks and language is None and type(reason) is str and bool(reason)
            and (status != 'failed' or reason == 'invalid_backend_output'),
            'analyzer_work_technical_failure', exit_code=5)
    else:
        require(len(ranks) == 2 and engine['reason'] is None
            and all(engine['engine'][k]['value'] is not None for k in ENGINE_FACTS),
            'analyzer_work_engine_unavailable', exit_code=5)
        (best, score), (_, second) = ranks
        expected_reason = ('backend_abstention' if best == 'und' else 'non_linguistic'
            if best == 'zxx' else 'low_score_or_margin'
            if score < parse_threshold(policy['min_score'],'min_score')
            or score-second < parse_threshold(policy['min_margin'],'min_margin') else None)
        require((status, reason, language) ==
            (('detected', None, best) if expected_reason is None
             else ('undetermined', expected_reason, None)), 'analyzer_work_decision', exit_code=5)
    parsed = ScoreDecision(status, reason, language, tuple((r['language'],r['score']) for r in scores))
    subject, findings = observe_subject(original, parsed, policy, bundled_language_registry())
    require(subject == value['subject'] and findings == value['findings'],
            'analyzer_work_observation_policy', exit_code=5)
