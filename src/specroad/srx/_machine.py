"""Private iterative machine over validated owned AST/context values."""

from .operators import UNARY_OPERATORS, BINARY_OPERATORS, QUANTIFIER_OPERATORS
from .errors import SrxError
from ._quantifier_iteration import QuantifierIteration
from ._operations import apply_values, boolean_value, leaf_value


def evaluate_expression(expression, roots, *, rule_id):
    # Each work frame owns its lexical binding, never a mutable global root.
    work = [("visit", expression, "/expression", None)]
    values = []
    while work:
        action, node, at, scope = work.pop()
        if action == "apply":
            op, count = node
            operands = values[-count:]
            del values[-count:]
            values.append(apply_values(op, operands, rule_id=rule_id, at=at))
            continue
        if action == "boolean":
            op, args, index = node
            value = values.pop()
            boolean_value(value, rule_id=rule_id, at=at+"/args/"+str(index))
            if (op == "and" and value is False) or (op == "or" and value is True):
                values.append(value)
            elif index + 1 == len(args):
                values.append(op == "and")
            else:
                work.append(("boolean", (op, args, index+1), at, scope))
                work.append(("visit", args[index+1], at+"/args/"+str(index+1), scope))
            continue
        if action in ("quantifier_array", "quantifier_item"):
            if action == "quantifier_array":
                op, where = node
                cursor = QuantifierIteration(op, values.pop(), where, rule_id=rule_id, at=at)
            else:
                cursor = node
                cursor.accept(values.pop())
            if cursor.done:
                values.append(cursor.result)
            else:
                work.append(("quantifier_item", cursor, at, scope))
                work.append(("visit", cursor.predicate, at+"/where", cursor.item_scope()))
            continue
        op = node["op"]
        if op in ("literal", "field"):
            values.append(leaf_value(node, roots, rule_id=rule_id, at=at, item_scope=scope))
        elif op in UNARY_OPERATORS:
            work.append(("apply", (op, 1), at, scope))
            work.append(("visit", node["arg"], at+"/arg", scope))
        elif op in BINARY_OPERATORS:
            work.append(("apply", (op, 2), at, scope))
            work.append(("visit", node["args"][1], at+"/args/1", scope))
            work.append(("visit", node["args"][0], at+"/args/0", scope))
        elif op in QUANTIFIER_OPERATORS:
            work.append(("quantifier_array", (op, node["where"]), at, scope))
            work.append(("visit", node["array"], at+"/array", scope))
        elif op in ("and", "or"):
            args = node["args"]
            if not args:
                values.append(op == "and")
            else:
                work.append(("boolean", (op, args, 0), at, scope))
                work.append(("visit", args[0], at+"/args/0", scope))
        else:
            raise SrxError("unsupported_operator", rule_id=rule_id, pointer=at+"/op",
                           expected="supported operator", actual="string")
    return values[0]
