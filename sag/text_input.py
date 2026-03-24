import re
import sys

MAX_CHUNK_CHARS = 500
# Target size for the first chunk — small so audio starts fast
FIRST_CHUNK_TARGET = 120

# Sentence boundary: period, exclamation, question mark followed by space or end
_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')


def resolve_text(args: tuple[str, ...]) -> str:
    """Get text from CLI args, stdin pipe, or return empty string."""
    if args:
        return " ".join(args)

    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

    return ""


def _split_first_sentence(text: str) -> tuple[str, str]:
    """Split text at the first sentence boundary for fast initial playback.

    Returns (first_sentence, remainder). If no boundary found or text is
    already short, returns (text, "").
    """
    if len(text) <= FIRST_CHUNK_TARGET:
        return text, ""

    m = _SENTENCE_RE.search(text, pos=20)  # skip very short false starts
    if m and m.start() <= MAX_CHUNK_CHARS:
        return text[:m.start()].strip(), text[m.end():].strip()

    return text, ""


def chunk_text(text: str) -> list[str]:
    """Split text into chunks for streaming generation.

    Strategy:
      1. Split the first chunk at a sentence boundary for fast time-to-audio
      2. Split remainder on paragraph boundaries (\\n\\n)
      3. If any paragraph exceeds MAX_CHUNK_CHARS, sub-split on single \\n
      4. Filter out empty chunks

    This gives fast initial playback while preserving emotional context
    within paragraphs/stanzas for subsequent chunks.
    """
    # Short text — no chunking needed
    if len(text) <= FIRST_CHUNK_TARGET:
        return [text]

    chunks = []

    # Split the first paragraph to get audio playing quickly
    first_para_end = text.find("\n\n")
    if first_para_end == -1:
        first_para = text
        rest = ""
    else:
        first_para = text[:first_para_end].strip()
        rest = text[first_para_end:].strip()

    if len(first_para) > FIRST_CHUNK_TARGET:
        first, remainder = _split_first_sentence(first_para)
        chunks.append(first)
        if remainder:
            chunks.append(remainder)
    else:
        chunks.append(first_para)

    if not rest:
        return chunks

    # Chunk the rest by paragraphs
    paragraphs = rest.split("\n\n")

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
