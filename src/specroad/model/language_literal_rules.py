"""Named literal rules reuse the existing LiteralPolicy data contract.

policy_id/version identify a rule; SHA-256 binds its complete canonical value.
Parsing is passive. Actual field selection and execution remain explicit.
"""
from .canonical import canonical_json_bytes
from .errors import ModelError


def parse_literal_rules(values):
    from ._language_package_parser import LanguagePackageError
    if type(values) is not list:
        raise LanguagePackageError("literal_rules_array_required")
    if not values:
        return ()
    from ..lint.values import LiteralPolicy
    rules = []
    for index, value in enumerate(values):
        try:
            policy = LiteralPolicy(canonical_json_bytes(value))
        except ModelError as error:
            raise LanguagePackageError("literal_rule_invalid", pointer="/literal_rules/" + str(index) + error.pointer) from error
        rules.append(policy)
    return tuple(rules)
