from __future__ import annotations

import sys

import click


def list_voices(model_id: str) -> None:
    """Print available voices to stdout."""
    from sag.tts import available_voices

    voices = available_voices(model_id)
    for voice in sorted(voices):
        click.echo(voice)


def validate_voice(voice: str, model_id: str) -> None:
    """Exit with error if voice is not available."""
    from sag.tts import available_voices

    voices = available_voices(model_id)
    if voice not in voices:
        click.echo(f"Error: Unknown voice '{voice}'. Available voices:", err=True)
        for v in sorted(voices):
            click.echo(f"  {v}", err=True)
        raise SystemExit(1)
