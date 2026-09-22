"""Iterative AST machine with per-frame lexical and candidate root bindings."""

from .operators import UNARY_OPERATORS, BINARY_OPERATORS, QUANTIFIER_OPERATORS
from .errors import SrxError
from ._quantifier_iteration import QuantifierIteration
from ._operations import apply_values, boolean_value, leaf_value
from .graph_validation import GRAPH_OPERATORS
from .graph_operations import direct_graph_operation, ReachabilityIteration


def evaluate_expression(expression, roots, *, rule_id, graph=None, pointer="/expression", item_scope=None):
    # Every continuation carries roots and item; nested BFS never recurses here.
    work = [("visit", expression, pointer, item_scope, roots)]
    values = []
    while work:
        action, node, at, scope, current_roots = work.pop()
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
                work.append(("boolean", (op, args, index+1), at, scope, current_roots))
                work.append(("visit", args[index+1], at+"/args/"+str(index+1), scope, current_roots))
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
                work.append(("quantifier_item", cursor, at, scope, current_roots))
                work.append(("visit", cursor.predicate, at+"/where", cursor.item_scope(), current_roots))
            continue
        if action == "reachable_item":
            node.accept(values.pop())
            if node.done:
                values.append(node.result)
            else:
                candidate = node.next_roots()
                work.append(("reachable_item", node, at, scope, current_roots))
                work.append(("visit", node.node["where"], at+"/where", scope, candidate))
            continue
        op = node["op"]
        if op in GRAPH_OPERATORS:
            if op == "reachable":
                cursor = ReachabilityIteration(node, current_roots, graph=graph, rule_id=rule_id, at=at)
                candidate = cursor.next_roots()
                work.append(("reachable_item", cursor, at, scope, current_roots))
                work.append(("visit", node["where"], at+"/where", scope, candidate))
            else:
                values.append(direct_graph_operation(node, current_roots, graph=graph, rule_id=rule_id, at=at))
        elif op in ("literal", "field"):
            values.append(leaf_value(node, current_roots, rule_id=rule_id, at=at, item_scope=scope))
        elif op in UNARY_OPERATORS:
            work.append(("apply", (op, 1), at, scope, current_roots))
            work.append(("visit", node["arg"], at+"/arg", scope, current_roots))
        elif op in BINARY_OPERATORS:
            work.append(("apply", (op, 2), at, scope, current_roots))
            work.append(("visit", node["args"][1], at+"/args/1", scope, current_roots))
            work.append(("visit", node["args"][0], at+"/args/0", scope, current_roots))
        elif op in QUANTIFIER_OPERATORS:
            work.append(("quantifier_array", (op, node["where"]), at, scope, current_roots))
            work.append(("visit", node["array"], at+"/array", scope, current_roots))
        elif op in ("and", "or"):
            args = node["args"]
            if not args:
                values.append(op == "and")
            else:
                work.append(("boolean", (op, args, 0), at, scope, current_roots))
                work.append(("visit", args[0], at+"/args/0", scope, current_roots))
        else:
            raise SrxError("unsupported_operator", rule_id=rule_id, pointer=at+"/op",
                           expected="supported operator", actual="string")
    return values[0]
