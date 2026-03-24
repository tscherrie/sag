from __future__ import annotations

import sys

import click

from sag import __version__

DEFAULT_MODEL = "KittenML/kitten-tts-nano-0.8"
DEFAULT_VOICE = "Bella"
DEFAULT_RATE = 175  # words per minute baseline


class SagGroup(click.Group):
    """Custom group that treats unknown args as text to speak."""

    def parse_args(self, ctx, args):
        # If first arg looks like a subcommand, let Click handle it normally
        if args and args[0] in self.commands:
            return super().parse_args(ctx, args)

        # Otherwise, collect non-option trailing args as the text to speak
        # We need to separate options from text arguments
        ctx.ensure_object(dict)
        ctx.obj["_text_args"] = []

        # Find where the text starts (after all options and their values)
        parsed_args = []
        text_args = []
        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith("-"):
                parsed_args.append(arg)
                # Check if this option takes a value
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
@click.option("-v", "--voice", default=DEFAULT_VOICE, help="Voice name.", show_default=True)
@click.option("--speed", default=None, type=float, help="Speed multiplier (0.5-2.0).")
@click.option("-r", "--rate", default=None, type=float, help="Words per minute (converted to speed).")
@click.option("-o", "--output", default=None, type=click.Path(), help="Save audio to file instead of playing.")
@click.option("--format", "fmt", default=None, type=click.Choice(["wav", "mp3"]), help="Output format (auto-detected from extension if omitted).")
@click.option("--model", default=DEFAULT_MODEL, help="KittenTTS model ID.", show_default=True)
@click.version_option(__version__, prog_name="sag")
@click.pass_context
def main(ctx, voice, speed, rate, output, fmt, model):
    """Neural text-to-speech from the command line.

    Usage: sag "Hello world"
    """
    ctx.ensure_object(dict)
    ctx.obj["model"] = model

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

    from sag.voices import validate_voice
    from sag.tts import generate
    from sag.audio import play, save_to_file

    validate_voice(voice, model)
    samples, sample_rate = generate(text_str, voice, speed, model)

    if output:
        save_to_file(samples, sample_rate, output, fmt)
    else:
        play(samples, sample_rate)


@main.command()
@click.pass_context
def voices(ctx):
    """List available voices."""
    from sag.voices import list_voices

    model = ctx.obj.get("model", DEFAULT_MODEL)
    list_voices(model)
