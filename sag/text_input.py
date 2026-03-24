import sys

MAX_CHUNK_CHARS = 500


def resolve_text(args: tuple[str, ...]) -> str:
    """Get text from CLI args, stdin pipe, or return empty string."""
    if args:
        return " ".join(args)

    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

    return ""


def chunk_text(text: str) -> list[str]:
    """Split text into chunks for streaming generation.

    Strategy:
      1. Split on paragraph boundaries (\\n\\n)
      2. If any paragraph exceeds MAX_CHUNK_CHARS, sub-split on single \\n
      3. Filter out empty chunks

    This preserves emotional context within paragraphs/stanzas while
    still allowing streaming playback for long texts.
    """
    # Short text — no chunking needed
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]

    # Split on double newlines (paragraphs / stanzas)
    paragraphs = text.split("\n\n")
    chunks = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(para) <= MAX_CHUNK_CHARS:
            chunks.append(para)
        else:
            # Sub-split long paragraphs on single newlines
            lines = para.split("\n")
            current = []
            current_len = 0
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # If adding this line would exceed limit, flush current
                new_len = current_len + len(line) + (1 if current else 0)
                if current and new_len > MAX_CHUNK_CHARS:
                    chunks.append("\n".join(current))
                    current = [line]
                    current_len = len(line)
                else:
                    current.append(line)
                    current_len = new_len
            if current:
                chunks.append("\n".join(current))

    return chunks if chunks else [text]
