from __future__ import annotations

import io
import sys

import numpy as np
import soundfile as sf


def play(samples: np.ndarray, sample_rate: int) -> None:
    """Play audio samples to the default output device, blocking until done."""
    import sounddevice as sd

    sd.play(samples, samplerate=sample_rate)
    sd.wait()


def play_streaming(audio_iter, sample_rate: int = 24000) -> None:
    """Play audio chunks with look-ahead generation.

    A background thread generates chunks into a queue so the next chunk
    is ready by the time the current one finishes playing. This eliminates
    the pause between chunks.

    Args:
        audio_iter: Iterator yielding np.ndarray chunks of float32 PCM.
        sample_rate: Sample rate (default 24000 for KittenTTS).
    """
    import queue
    import threading

    import sounddevice as sd

    _SENTINEL = None
    buf: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=2)

    def _producer():
        try:
            for chunk in audio_iter:
                buf.put(chunk)
        finally:
            buf.put(_SENTINEL)

    thread = threading.Thread(target=_producer, daemon=True)
    thread.start()

    while True:
        chunk = buf.get()
        if chunk is None:
            break
        sd.play(chunk, samplerate=sample_rate)
        sd.wait()


def save_to_file(
    samples: np.ndarray, sample_rate: int, path: str, fmt: str | None = None
) -> None:
    """Save audio to a file. Format is auto-detected from extension if not given."""
    if fmt is None:
        if path.endswith(".mp3"):
            fmt = "mp3"
        else:
            fmt = "wav"

    if fmt == "mp3":
        _save_mp3(samples, sample_rate, path)
    else:
        sf.write(path, samples, sample_rate)

    print(f"Saved to {path}", file=sys.stderr)


def _save_mp3(samples: np.ndarray, sample_rate: int, path: str) -> None:
    """Save as MP3 via pydub (requires ffmpeg)."""
    try:
        from pydub import AudioSegment
    except ImportError:
        print("Error: pydub is required for MP3 export. pip install pydub", file=sys.stderr)
        raise SystemExit(1)

    buf = io.BytesIO()
    sf.write(buf, samples, sample_rate, format="WAV")
    buf.seek(0)

    try:
        audio_segment = AudioSegment.from_wav(buf)
        audio_segment.export(path, format="mp3")
    except Exception as e:
        if "ffmpeg" in str(e).lower() or "ffprobe" in str(e).lower():
            print(
                "Error: MP3 export requires ffmpeg. Install with: brew install ffmpeg",
                file=sys.stderr,
            )
            raise SystemExit(1)
        raise
