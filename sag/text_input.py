import sys


def resolve_text(args: tuple[str, ...]) -> str:
    """Get text from CLI args, stdin pipe, or return empty string."""
    if args:
        return " ".join(args)

    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

    return ""
