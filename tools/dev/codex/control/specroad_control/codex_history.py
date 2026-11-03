"""Bounded, metadata-first reads of one exact Codex turn and all its items.

The observer has no method that starts, resumes, interrupts, or changes work.
"""
from .errors import ControlError
from .codex_limits import (
    MAX_HISTORY_BYTES, MAX_TURN_PAGES, TURN_PAGE_SIZE, MAX_TURN_ITEMS,
    MAX_ITEM_PAGES, ITEM_PAGE_SIZE, MAX_CURSOR_BYTES, json_size as _json_size,
)

_TERMINAL = {"completed", "failed", "interrupted"}


class TurnHistory:
    def __init__(self, proxy):
        self.proxy = proxy


    def inspect(self, turn_id):
        """Read the exact turn, never resume/start/interrupt an agent.

        Codex 0.163.0 supports turn metadata and turn-filtered item pages.
        Full legacy history is a bounded compatibility path, not the default.
        No metadata/item summary is promoted into complete retry evidence.
        """
        if not isinstance(turn_id, str) or not turn_id or len(turn_id) > 160:
            raise ControlError("codex_turn_unidentified", "No exact turn identity for observation.")
        status = self.proxy.status_type(self.proxy.inspect_thread())
        if status not in ("idle", "notLoaded"):
            return {"thread_status": status, "turn": None}
        try:
            located = self._locate_turn(turn_id)
        except ControlError as exc:
            if not _unsupported(exc):
                raise
            return self._legacy_turn(turn_id)
        if located is None:
            return {"thread_status": "active", "turn": None}
        target, page_cursor = located
        try:
            items = self._target_items(turn_id)
        except ControlError as exc:
            if not _unsupported(exc):
                raise
            # Some stores implement turn pages but not item pages. Request one
            # FULL turn at a time, beginning with the known metadata page.
            try:
                found = self._locate_turn(turn_id, view="full", limit=1,
                                          initial_cursor=page_cursor, pages=TURN_PAGE_SIZE)
            except ControlError as fallback:
                if not _unsupported(fallback):
                    raise
                return self._legacy_turn(turn_id)
            if found is None:
                return {"thread_status": "active", "turn": None}
            full, _cursor = found
            _same_turn(target, full)
            items = _full_items(full, legacy=False)
        # Re-read terminal metadata after pagination: a partial/racing read is
        # never a completed snapshot merely because the last item page ended.
        refreshed = self._locate_turn(turn_id)
        if refreshed is None:
            return {"thread_status": "active", "turn": None}
        _same_turn(target, refreshed[0])
        turn = {**target, "items": items, "itemsView": "full"}
        status = self.proxy.status_type(self.proxy.inspect_thread())
        return {"thread_status": status, "turn": turn if status in ("idle", "notLoaded") else None}

    def _locate_turn(self, turn_id, *, view="notLoaded", limit=TURN_PAGE_SIZE,
                     initial_cursor=None, pages=MAX_TURN_PAGES):
        cursor = initial_cursor
        seen_cursors = {cursor} if cursor is not None else set()
        seen_ids = set()
        for _ in range(pages):
            params = {"threadId": self.proxy.config.session_id, "limit": limit,
                      "sortDirection": "desc", "itemsView": view}
            if cursor is not None:
                params["cursor"] = cursor
            page = self.proxy.call("thread/turns/list", params)
            data, following = _page(page, limit, seen_cursors)
            for turn in data:
                _turn_metadata(turn)
                if turn["id"] in seen_ids:
                    raise ControlError("codex_turn_history_invalid", "Duplicate turn identity across pages.")
                seen_ids.add(turn["id"])
            if any(turn["status"] == "inProgress" for turn in data):
                return None
            matches = [turn for turn in data if turn["id"] == turn_id]
            if matches:
                # Never retain unrelated turn items in the observer.
                return matches[0], cursor
            if following is None:
                break
            cursor = following
        raise ControlError("codex_turn_history_unavailable", "Exact turn not found within the bounded history read.")

    def _target_items(self, turn_id):
        items, ids, cursors = [], set(), set()
        total = 0
        cursor = None
        for _ in range(MAX_ITEM_PAGES):
            params = {"threadId": self.proxy.config.session_id, "turnId": turn_id,
                      "limit": ITEM_PAGE_SIZE, "sortDirection": "asc"}
            if cursor is not None:
                params["cursor"] = cursor
            page = self.proxy.call("thread/items/list", params)
            data, cursor = _page(page, ITEM_PAGE_SIZE, cursors)
            for entry in data:
                if not isinstance(entry, dict) or entry.get("turnId") != turn_id or entry.get("truncated") is True:
                    raise ControlError("codex_turn_history_invalid", "Item page does not belong to the exact turn.")
                item = entry.get("item")
                _item_identity(item, ids)
                total += _json_size(item)
                if total > MAX_HISTORY_BYTES or len(items) >= MAX_TURN_ITEMS:
                    raise ControlError("codex_turn_history_limit", "Complete turn evidence exceeds the bounded history budget.")
                items.append(item)
            if cursor is None:
                return items
        raise ControlError("codex_turn_history_limit", "Turn item pagination exceeded its bounded page budget.")

    def _legacy_turn(self, turn_id):
        thread = self.proxy.inspect_thread(include_turns=True)
        status = self.proxy.status_type(thread)
        if status not in ("idle", "notLoaded"):
            return {"thread_status": status, "turn": None}
        turns = thread.get("turns")
        if not isinstance(turns, list) or len(turns) > MAX_TURN_PAGES * TURN_PAGE_SIZE:
            raise ControlError("codex_turn_history_invalid", "Unexpected legacy turn history.")
        if thread.get("truncated") is True or thread.get("hasMore") is True or thread.get("nextCursor") is not None:
            raise ControlError("codex_turn_history_invalid", "Legacy turn history is incomplete.")
        identities = set()
        for turn in turns:
            _turn_metadata(turn)
            if turn["id"] in identities:
                raise ControlError("codex_turn_history_invalid", "Duplicate legacy turn identity.")
            identities.add(turn["id"])
        if any(turn["status"] == "inProgress" for turn in turns):
            return {"thread_status": "active", "turn": None}
        found = [turn for turn in turns if turn["id"] == turn_id]
        if len(found) != 1:
            raise ControlError("codex_turn_history_unavailable", "Exact turn not found in legacy history.")
        target = found[0]
        items = _full_items(target, legacy=True)
        status = self.proxy.status_type(self.proxy.inspect_thread())
        return {"thread_status": status, "turn": {**target, "items": items, "itemsView": "full"}
                if status in ("idle", "notLoaded") else None}

def _unsupported(exc):
    return exc.code == "codex_request_rejected" and exc.details.get("rpc_code") in (-32601, -32602)


def _page(page, limit, seen):
    if not isinstance(page, dict) or not isinstance(page.get("data"), list) or len(page["data"]) > limit:
        raise ControlError("codex_turn_history_invalid", "Unexpected history page.")
    if "nextCursor" not in page or page.get("truncated") is True or page.get("hasMore") is True and page["nextCursor"] is None:
        raise ControlError("codex_turn_history_invalid", "Incomplete history page.")
    cursor = page["nextCursor"]
    if cursor is not None:
        if not isinstance(cursor, str) or not cursor or len(cursor.encode("utf-8")) > MAX_CURSOR_BYTES or cursor in seen:
            raise ControlError("codex_turn_history_invalid", "Invalid history continuation cursor.")
        if not page["data"]:
            raise ControlError("codex_turn_history_invalid", "Empty page with an unproven continuation.")
        seen.add(cursor)
    return page["data"], cursor


def _turn_metadata(turn):
    if (not isinstance(turn, dict) or not isinstance(turn.get("id"), str) or not turn["id"] or
            len(turn["id"]) > 160 or turn.get("status") not in _TERMINAL | {"inProgress"}):
        raise ControlError("codex_turn_history_invalid", "Malformed turn metadata.")
    if turn.get("truncated") is True or turn.get("hasMore") is True:
        raise ControlError("codex_turn_history_invalid", "Turn evidence was truncated.")


def _same_turn(before, after):
    keys = ("id", "status", "error", "startedAt", "completedAt")
    if any(before.get(key) != after.get(key) for key in keys):
        raise ControlError("codex_turn_history_changed", "Exact turn changed during history observation.")


def _item_identity(item, ids):
    if (not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] or
            len(item["id"]) > 256 or item["id"] in ids or not isinstance(item.get("type"), str) or
            item.get("truncated") is True or item.get("hasMore") is True):
        raise ControlError("codex_turn_history_invalid", "Malformed, duplicate, or incomplete turn item.")
    ids.add(item["id"])


def _full_items(turn, *, legacy):
    if turn.get("itemsView") != "full" and not (legacy and "itemsView" not in turn):
        raise ControlError("codex_turn_history_unavailable", "Full turn items were not supplied.")
    items = turn.get("items")
    if not isinstance(items, list) or len(items) > MAX_TURN_ITEMS:
        raise ControlError("codex_turn_history_invalid", "Invalid full turn item list.")
    ids, total = set(), 0
    for item in items:
        _item_identity(item, ids)
        total += _json_size(item)
        if total > MAX_HISTORY_BYTES:
            raise ControlError("codex_turn_history_limit", "Complete turn evidence exceeds its bounded byte budget.")
    return items
