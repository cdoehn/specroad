"""Argument binding from the same OptionSpec objects used by command metadata."""

from .contracts import CommandUsageError


def bind_options(argv, route, options):
    option_specs = {option.flag: option for option in options}
    values = {}
    words = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if not token.startswith("-") or token in route:
            words.append(token)
            index += 1
            continue
        flag, equals, attached = token.partition("=")
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
            if not value or value.startswith("--") or (option.choices and value not in option.choices):
                raise CommandUsageError("Invalid option value")
        else:
            if equals:
                raise CommandUsageError("Flag does not accept a value")
            value = True
        values[flag] = (*values.get(flag, ()), value) if option.repeatable else value
        index += 1
    if tuple(words) != route:
        raise CommandUsageError("Unknown command or unexpected positional argument")
    for option in options:
        if option.required and option.flag not in values:
            raise CommandUsageError("Missing required option")
        if option.flag in values and any(other in values for other in option.excludes):
            raise CommandUsageError("Mutually exclusive options")
    return values

