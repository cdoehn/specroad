"""Ordered set/unset conversion using the real JSON-Patch execution semantics."""
from ._patch_values import JsonPatchError, _snapshot, _tokens, _strict_value
from .json_patch import JsonPatch, _ABSENT, _index, _read, _apply_one


def compile_field_patch(document, options):
    """Convert ordered (--set, pointer=JSON) / (--unset, pointer) pairs.

    Set replaces an existing array slot; it never inserts there. A missing object
    member is added. '-' or the array's exact length appends; holes are errors.
    No implicit parents, unquoted strings, shell expansion or schema defaults.
    """
    if type(options) not in (list, tuple):
        raise JsonPatchError("ordered_options_required", pointer="/options")
    current = _snapshot(document, "/document").data
    operations = []
    for index, pair in enumerate(options):
        at = "/options/" + str(index)
        if type(pair) not in (list, tuple) or len(pair) != 2 or any(type(v) is not str for v in pair):
            raise JsonPatchError("option_pair_required", pointer=at)
        option, argument = pair
        if option == "--set":
            pointer, separator, text = argument.partition("=")
            if not separator:
                raise JsonPatchError("set_assignment_required", pointer=at)
            value = _strict_value(text, at)
            tokens = _tokens(pointer, at)
            def fail(reason):
                raise JsonPatchError(reason, pointer=at, document_pointer=pointer)
            if not tokens:
                kind = "add" if current is _ABSENT else "replace"
            else:
                parent = _read(current, tokens[:-1], fail)
                key = tokens[-1]
                if type(parent) is dict:
                    kind = "replace" if key in parent else "add"
                elif type(parent) is list:
                    position = _index(key, len(parent), insert=True, fail=fail)
                    kind = "add" if position == len(parent) else "replace"
                else:
                    fail("pointer_parent_not_container")
            item = {"op": kind, "path": pointer, "value": value}
        elif option == "--unset":
            item = {"op": "remove", "path": argument}
            _tokens(argument, at)
        else:
            raise JsonPatchError("unknown_field_option", pointer=at)
        # Execute the actual normalized operations, so later options see the
        # exact preceding values. No dictionary merge or reordering of flags.
        current = _apply_one(current, item, index)
        operations.append(item)
    return JsonPatch(operations)
