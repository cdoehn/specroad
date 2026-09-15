"""One semantic option binder, with CLI tokens and structured data as adapters."""

from typing import Mapping

from .contracts import CommandUsageError


def bind_values(values, options):
    """Validate types, multiplicity, choices and exclusions without side effects."""
    if not isinstance(values, Mapping):
        raise CommandUsageError("Options must be a mapping")
    specs = {option.flag: option for option in options}
    normalized = {}
    for flag, value in values.items():
        option = specs.get(flag)
        if option is None:
            raise CommandUsageError("Unknown option")
        if option.repeatable:
            if not isinstance(value, (list, tuple)) or not value:
                raise CommandUsageError("A repeated option needs a nonempty sequence")
            items = tuple(value)
        else:
            if isinstance(value, (list, tuple)):
                raise CommandUsageError("A scalar option cannot repeat")
            items = (value,)
        for item in items:
            if option.takes_value:
                if (not isinstance(item, str) or not item or '\0' in item
                        or item.startswith('--') or (option.choices and item not in option.choices)):
                    raise CommandUsageError("Invalid option value")
                try:
                    item.encode('utf-8')
                except UnicodeError as error:
                    raise CommandUsageError("Option value is not valid Unicode") from error
            elif item is not True:
                raise CommandUsageError("Flag must be true or omitted")
        normalized[flag] = items if option.repeatable else items[0]
    for option in options:
        if option.required and option.flag not in normalized:
            raise CommandUsageError("Missing required option")
        if option.flag in normalized and any(other in normalized for other in option.excludes):
            raise CommandUsageError("Mutually exclusive options")
    return normalized


def bind_options(argv, route, options):
    """Decode CLI spelling, then use the same binder as structured requests."""
    option_specs = {option.flag: option for option in options}
    values = {}
    words = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if not token.startswith('-') or token in route:
            words.append(token)
            index += 1
            continue
        flag, equals, attached = token.partition('=')
        option = option_specs.get(flag)
        if option is None or (flag in values and not option.repeatable):
            raise CommandUsageError("Unknown or repeated option")
        if option.takes_value:
            if equals:
                value = attached
            else:
                index += 1
                if index >= len(argv):
                    raise CommandUsageError("Missing option value")
                value = argv[index]
        else:
            if equals:
                raise CommandUsageError("Flag does not accept a value")
            value = True
        values[flag] = (*values.get(flag, ()), value) if option.repeatable else value
        index += 1
    if tuple(words) != route:
        raise CommandUsageError("Unknown command or unexpected positional argument")
    return bind_values(values, options)
