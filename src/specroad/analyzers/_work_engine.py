"""One real model per owned serial invocation; no journal or process control."""
from ._model_session import ModelSession
from ._reference_backend import _engine, _scores
from ._text_policy import request_policy, text_length
from ._values import AnalyzerError
from .registry import builtin_descriptor
from .engine_identity import engine_identity
from .language_scores import ScoreDecision, decide_scores
from .language_policy import observe_subject
from .reports import subject_result
from ._work_values import static_engines, select, unit_value


class WorkEngine:
    def __init__(self, request):
        self.request = request
        self.session = ModelSession()
        self.rows = static_engines(request, 'external_result_only')
        self.policy = None
        self.engine = None
        self.unavailable = None
        self.registry = None

    def __enter__(self):
        try:
            if any(e['descriptor'] == builtin_descriptor().data for e in self.request.data['analyzers']):
                data, entry, self.policy = request_policy(self.request)
                from ..storage.language_registry import bundled_language_registry
                self.registry = bundled_language_registry()
                if any(text_length(s['value']) >= self.policy['min_text_codepoints'] for s in data['subjects']):
                    try:
                        self.session.model()
                        self.engine = _engine(entry['descriptor'])
                    except AnalyzerError as error:
                        self.unavailable = error.reason
                identity = engine_identity(self.engine)
                if self.engine is not None and not identity.reproducible:
                    self.unavailable = 'numeric_inventory_unavailable'
                for row in self.rows:
                    if row['analyzer_id'] == 'specroad.py3langid':
                        row.update(engine=identity.data, inventory=identity.inventory,
                                   reason=self.unavailable)
            return self
        except BaseException:
            self.session.close()
            raise

    def __exit__(self, *error):
        self.session.close()

    def subject(self, pair):
        entry, original = select(self.request, pair)
        engine = next(e for e in self.rows if e['analyzer_id'] == pair['analyzer_id'])
        if entry['descriptor'] != builtin_descriptor().data:
            subject, findings = subject_result(original, status='open', payload={}), []
        else:
            if text_length(original['value']) < self.policy['min_text_codepoints']:
                decision = ScoreDecision('undetermined', 'insufficient_text', None, ())
            elif self.unavailable is not None:
                decision = ScoreDecision('unavailable', self.unavailable, None, ())
            else:
                try:
                    decision = decide_scores(_scores(self.session.model(), original['value']),
                        min_score=self.policy['min_score'], min_margin=self.policy['min_margin'])
                except AnalyzerError as error:
                    decision = ScoreDecision('failed' if error.reason == 'invalid_backend_output'
                        else 'unavailable', error.reason, None, ())
            subject, findings = observe_subject(original, decision, self.policy, self.registry)
        return unit_value(self.request, pair, engine, subject, findings)
