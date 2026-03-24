from __future__ import annotations

import sys

import numpy as np

_model_cache: dict[str, object] = {}


def get_model(model_id: str):
    """Load a KittenTTS model, caching for reuse within the process."""
    if model_id not in _model_cache:
        print(f"Loading model {model_id}...", file=sys.stderr)
        from kittentts import KittenTTS

        _model_cache[model_id] = KittenTTS(model_id)
    return _model_cache[model_id]


def generate(
    text: str, voice: str, speed: float, model_id: str
) -> tuple[np.ndarray, int]:
    """Generate audio from text. Returns (samples, sample_rate)."""
    model = get_model(model_id)
    samples = model.generate(text=text, voice=voice, speed=speed)
    return samples, 24000


def available_voices(model_id: str) -> list[str]:
    """Return list of available voice names for the given model."""
    model = get_model(model_id)
    return list(model.available_voices)
