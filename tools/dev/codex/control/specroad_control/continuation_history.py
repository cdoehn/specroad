"""Modern bounded observation for a continuation of the exact latest turn."""
from .errors import ControlError
from .codex_history import TurnHistory, _page, _same_turn, _turn_metadata
from .continuation_evidence import sha
from .overload_wait import background_identity
from .codex_limits import MAX_HISTORY_BYTES, json_size


class ContinuationHistory(TurnHistory):
    def observe_wait(self, turn_id):
        """Full evidence may contain known unfinished commands, never a new turn."""
        status = self.proxy.status_type(self.proxy.inspect_thread())
        if status not in ('idle', 'notLoaded', 'systemError'):
            raise ControlError('continuation_inactive_unproven', 'The failed turn is not exclusively observable.')
        before = self._latest(turn_id)
        background_before = self._background()
        items = self._target_items(turn_id)
        after = self._latest(turn_id)
        _same_turn(before, after)
        background = self._background()
        if not {sha(item) for item in background} <= {sha(item) for item in background_before}:
            raise ControlError('overload_background_changed', 'New background work appeared during observation.')
        status = self.proxy.status_type(self.proxy.inspect_thread())
        return {'thread_status': status, 'turn': {**before, 'items': items, 'itemsView': 'full'},
                'latest_turn_id': turn_id, 'background_terminals': background}

    def _background(self):
        items, seen, cursor = [], set(), None
        total = 0
        for _ in range(8):
            params = {'threadId': self.proxy.config.session_id, 'limit': 16}
            if cursor is not None:
                params['cursor'] = cursor
            data, cursor = _page(self.proxy.call('thread/backgroundTerminals/list', params), 16, seen)
            total += json_size(data)
            if total > MAX_HISTORY_BYTES:
                raise ControlError('overload_background_unproven', 'Background inventory exceeds its bounded byte budget.')
            items.extend(background_identity(item) for item in data)
            if cursor is None:
                if len({item['processId'] for item in items}) != len(items):
                    raise ControlError('overload_background_unproven', 'Duplicate background inventory.')
                return items
        raise ControlError('overload_background_unproven', 'Background inventory exceeds its bounded read.')

    def inspect(self, turn_id):
        """Stricter modern API only: latest exact turn plus no live terminals."""
        status = self.proxy.status_type(self.proxy.inspect_thread())
        if status not in ('idle', 'notLoaded', 'systemError'):
            return {'thread_status': status, 'turn': None}
        before = self._latest(turn_id)
        self._no_background()
        items = self._target_items(turn_id)
        after = self._latest(turn_id)
        _same_turn(before, after)
        self._no_background()
        status = self.proxy.status_type(self.proxy.inspect_thread())
        return {'thread_status': status, 'turn': {**before, 'items': items, 'itemsView': 'full'},
                'latest_turn_id': turn_id, 'background_terminals': []}

    def _latest(self, turn_id):
        page = self.proxy.call('thread/turns/list', {'threadId': self.proxy.config.session_id,
                               'limit': 1, 'sortDirection': 'desc', 'itemsView': 'notLoaded'})
        data, _ = _page(page, 1, set())
        if not data:
            raise ControlError('continuation_latest_unproven', 'No latest turn was returned.')
        turn = data[0]
        _turn_metadata(turn)
        if turn['status'] == 'inProgress':
            raise ControlError('dev_turn_active', 'An active turn must not be replaced.')
        if turn['id'] != turn_id:
            raise ControlError('continuation_intervening_turn', 'Another turn followed the failed attempt.')
        return turn

    def _no_background(self):
        page = self.proxy.call('thread/backgroundTerminals/list',
                               {'threadId': self.proxy.config.session_id, 'limit': 1})
        data, following = _page(page, 1, set())
        if data or following is not None:
            raise ControlError('continuation_background_active', 'Background work must finish before continuation.')
