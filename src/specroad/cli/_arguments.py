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


def bind_arguments(values, positionals):
    if not isinstance(values, Mapping):
        raise CommandUsageError("Arguments must be a mapping")
    specs = {arg.name: arg for arg in positionals}
    normalized = {}
    for name, value in values.items():
        arg = specs.get(name)
        if arg is None or not isinstance(value, str) or not value or "\0" in value:
            raise CommandUsageError("Unknown or invalid argument")
        try:
            value.encode("utf-8")
        except UnicodeError as error:
            raise CommandUsageError("Argument is not valid Unicode") from error
        if arg.choices and value not in arg.choices:
            raise CommandUsageError("Invalid argument choice")
        normalized[name] = value
    if any(arg.required and arg.name not in normalized for arg in positionals):
        raise CommandUsageError("Missing required argument")
    # Positional spelling has no holes. Structured inputs obey the same rule.
    omitted = False
    for arg in positionals:
        if omitted and arg.name in normalized:
            raise CommandUsageError("A positional argument cannot leave a gap")
        omitted = omitted or arg.name not in normalized
    return normalized


def bind_options(argv, route, options, positionals=()):
    """Decode CLI spelling, then use the same binder as structured requests."""
    option_specs = {option.flag: option for option in options}
    values = {}
    words = []
    index = 0
    literal = False
    while index < len(argv):
        token = argv[index]
        if token == '--' and not literal:
            if len(words) < len(route):
                raise CommandUsageError("Argument separator precedes command spelling")
            literal = True
            index += 1
            continue
        if literal or not token.startswith('-') or (len(words) < len(route) and token == route[len(words)]):
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
    if tuple(words[:len(route)]) != route or len(words) > len(route) + len(positionals):
        raise CommandUsageError("Unknown command or unexpected positional argument")
    arguments = {arg.name: value for arg, value in zip(positionals, words[len(route):])}
    return bind_values(values, options), bind_arguments(arguments, positionals)
