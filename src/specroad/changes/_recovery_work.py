"""Pure projection of retained historical work-file tokens; no repair I/O."""


def work_file_inventory(work):
    """Project checked file tokens into the existing canonical audit fields."""
    return [{'path': path, 'size': token['size'], 'sha256': token['sha256']}
            for path, token in sorted(work.items()) if type(token) is dict]
