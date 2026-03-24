from __future__ import annotations

import click

from sag import __version__
from sag.config import AVAILABLE_MODELS, get_default, set_default

DEFAULT_MODEL = "KittenML/kitten-tts-micro-0.8"
DEFAULT_VOICE = "Jasper"
DEFAULT_RATE = 175  # words per minute baseline


class SagGroup(click.Group):
    """Custom group that treats unknown args as text to speak."""

    def parse_args(self, ctx, args):
        # If first arg looks like a subcommand, let Click handle it normally
        if args and args[0] in self.commands:
            return super().parse_args(ctx, args)

        # Otherwise, collect non-option trailing args as the text to speak
        ctx.ensure_object(dict)
        ctx.obj["_text_args"] = []

        parsed_args = []
        text_args = []
        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith("-"):
                parsed_args.append(arg)
                param = None
                for p in self.params:
                    if isinstance(p, click.Option) and arg in p.opts:
                        param = p
                        break
                if param and not param.is_flag:
                    i += 1
                    if i < len(args):
                        parsed_args.append(args[i])
            else:
                text_args.append(arg)
            i += 1

        ctx.obj["_text_args"] = tuple(text_args)
        return super().parse_args(ctx, parsed_args)


@click.group(cls=SagGroup, invoke_without_command=True)
@click.option("-v", "--voice", default=None, help="Voice name (default from config or Bella).")
@click.option("--speed", default=None, type=float, help="Speed multiplier (0.5-2.0).")
@click.option("-r", "--rate", default=None, type=float, help="Words per minute (converted to speed).")
@click.option("-o", "--output", default=None, type=click.Path(), help="Save audio to file instead of playing.")
@click.option("--format", "fmt", default=None, type=click.Choice(["wav", "mp3"]), help="Output format (auto-detected from extension if omitted).")
@click.option("--model", default=None, help="KittenTTS model ID (default from config).")
@click.option("--no-server", is_flag=True, help="Skip background server, load model in-process.")
@click.version_option(__version__, prog_name="sag")
@click.pass_context
def main(ctx, voice, speed, rate, output, fmt, model, no_server):
    """Neural text-to-speech from the command line.

    Usage: sag "Hello world"
    """
    ctx.ensure_object(dict)

    # Resolve defaults from config
    if model is None:
        model = get_default("model", DEFAULT_MODEL)
    if voice is None:
        voice = get_default("voice", DEFAULT_VOICE)

    ctx.obj["model"] = model
    ctx.obj["voice"] = voice
    ctx.obj["no_server"] = no_server

    if ctx.invoked_subcommand is not None:
        return

    from sag.text_input import resolve_text

    text_args = ctx.obj.get("_text_args", ())
    text_str = resolve_text(text_args)
    if not text_str:
        click.echo(ctx.get_help())
        return

    # Resolve speed from --rate if --speed not given
    if speed is not None and rate is not None:
        click.echo("Warning: both --speed and --rate given; using --speed.", err=True)
    if speed is None:
        if rate is not None:
            speed = max(0.5, min(2.0, rate / DEFAULT_RATE))
        else:
            speed = 1.0

    from sag.text_input import chunk_text

    chunks = chunk_text(text_str)

    def generate_one(chunk_text_str):
        """Generate audio for a single chunk, server-first with fallback."""
        result = None
        if not no_server:
            from sag.client import try_generate
            result = try_generate(chunk_text_str, voice, speed, model)
        if result is None:
            from sag.voices import validate_voice
            from sag.tts import generate

            validate_voice(voice, model)
            result = generate(chunk_text_str, voice, speed, model)
        return result

    if output:
        # File output: generate all chunks, concatenate, save once
        from sag.audio import save_to_file

        all_samples = []
        sample_rate = 24000
        for chunk in chunks:
            samples, sample_rate = generate_one(chunk)
            all_samples.append(samples)

        import numpy as np
        combined = np.concatenate(all_samples)
        save_to_file(combined, sample_rate, output, fmt)
    else:
        # Streaming playback: generate and play chunks as they arrive
        if len(chunks) == 1:
            from sag.audio import play
            samples, sample_rate = generate_one(chunks[0])
            play(samples, sample_rate)
        else:
            from sag.audio import play_streaming

            def _audio_chunks():
                for chunk in chunks:
                    samples, _sr = generate_one(chunk)
                    yield samples

            play_streaming(_audio_chunks())


@main.command()
@click.option("--select", is_flag=True, help="Interactively set the default voice.")
@click.pass_context
def voices(ctx, select):
    """List available voices or select a default."""
    from sag.voices import list_voices

    model = ctx.obj.get("model", get_default("model", DEFAULT_MODEL))
    list_voices(model, select=select)


@main.command()
@click.option("--select", is_flag=True, help="Interactively set the default model.")
@click.pass_context
def models(ctx, select):
    """List available models or select a default."""
    current = get_default("model", DEFAULT_MODEL)

    click.echo("Available models:\n")
    for i, model_id in enumerate(AVAILABLE_MODELS, 1):
        size = {
            "nano-0.8-int8": "15M params INT8, smallest & fastest",
            "nano-0.8-fp32": "15M params FP32, highest precision nano",
            "nano-0.8": "15M params, fast",
            "micro": "40M params, balanced",
            "mini": "80M params, best quality",
        }
        label = next((v for k, v in size.items() if k in model_id), "")
        marker = " *" if model_id == current else ""
        click.echo(f"  {i}. {model_id} ({label}){marker}")

    if not select:
        click.echo(f"\nCurrent default: {current}")
        click.echo("Use 'sag models --select' to change the default.")
        return

    click.echo()
    choice = click.prompt("Select model number", type=int)
    if 1 <= choice <= len(AVAILABLE_MODELS):
        selected = AVAILABLE_MODELS[choice - 1]
        set_default("model", selected)
        click.echo(f"Default model set to: {selected}")
    else:
        click.echo("Invalid selection.", err=True)
        raise SystemExit(1)


@main.command(hidden=True)
@click.option("--idle-timeout", default=60, type=int, help="Seconds to wait before auto-exit.")
def serve(idle_timeout):
    """Run the background model server (internal use)."""
    from sag.server import run_server

    run_server(idle_timeout=idle_timeout)
