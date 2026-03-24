from __future__ import annotations

import click


def list_voices(model_id: str, select: bool = False) -> None:
    """Print available voices as a numbered list. If select=True, prompt to set default."""
    from sag.tts import available_voices
    from sag.config import get_default, set_default

    voices = sorted(available_voices(model_id))
    current = get_default("voice", "Bella")

    click.echo("Available voices:\n")
    for i, voice in enumerate(voices, 1):
        marker = " *" if voice == current else ""
        click.echo(f"  {i}. {voice}{marker}")

    if not select:
        click.echo(f"\nCurrent default: {current}")
        click.echo("Use 'sag voices --select' to change the default.")
        return

    click.echo()
    choice = click.prompt("Select voice number", type=int)
    if 1 <= choice <= len(voices):
        selected = voices[choice - 1]
        set_default("voice", selected)
        click.echo(f"Default voice set to: {selected}")
    else:
        click.echo("Invalid selection.", err=True)
        raise SystemExit(1)


def validate_voice(voice: str, model_id: str) -> None:
    """Exit with error if voice is not available."""
    from sag.tts import available_voices

    voices = available_voices(model_id)
    if voice not in voices:
        click.echo(f"Error: Unknown voice '{voice}'. Available voices:", err=True)
        for v in sorted(voices):
            click.echo(f"  {v}", err=True)
        raise SystemExit(1)
