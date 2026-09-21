"""Per-evaluation quantifier cursor, separate from iterative AST scheduling.

Inputs are already owned JSON values. This cursor never mutates an array or a
context root and queues no element work; the expression machine owns scheduling.
"""

from .types import require_type


class QuantifierIteration:
    """Fold every predicate in array order, stopping only at an evaluation error."""

    __slots__ = ("_op", "_items", "predicate", "_index", "result", "_rule_id", "_at")

    def __init__(self, op, items, predicate, *, rule_id, at):
        require_type(items, ("array",), rule_id=rule_id, pointer=at+"/array")
        self._op = op
        self._items = items
        self.predicate = predicate
        self._index = 0
        self.result = op != "any"
        self._rule_id = rule_id
        self._at = at

    @property
    def done(self):
        return self._index == len(self._items)

    def item_scope(self):
        # Only the current predicate receives this local lexical binding.
        return {"item": self._items[self._index]}

    def accept(self, value):
        require_type(value, ("boolean",), rule_id=self._rule_id,
                     pointer=self._at+"/where")
        if self._op == "any":
            self.result = self.result or value
        elif self._op == "all":
            self.result = self.result and value
        else:
            self.result = self.result and not value
        self._index += 1
