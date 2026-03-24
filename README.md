# sag — Neural text-to-speech from the command line

Local TTS that works like macOS `say` — speak to speakers or save audio files, powered by [KittenTTS](https://github.com/KittenML/KittenTTS). No API key needed.

## Install

Via Homebrew (includes ffmpeg):
```bash
brew install tscherrie/tap/sag
```

Or via pip:
```bash
pip install .
```

Requires Python 3.9+. The first run downloads the TTS model (~60 MB).

## Usage

Speak text aloud:
```bash
sag "Hello world"
```

Choose a voice:
```bash
sag -v Luna "Hello world"
```

Save to file:
```bash
sag -o output.wav "Save to file"
sag -o output.mp3 "Save as MP3"
```

Pipe input:
```bash
echo "piped input" | sag
```

Adjust speed:
```bash
sag --speed 1.5 "Faster speech"
sag -r 250 "Rate-based speed"
```

## Voices

Eight built-in voices: Bella (default), Bruno, Hugo, Jasper, Kiki, Leo, Luna, Rosie.

List all voices:
```bash
sag voices
```

Set a new default voice:
```bash
sag voices --select
```

## Models

Three model sizes available:

| Model | Params | Quality |
|-------|--------|---------|
| `kitten-tts-nano-0.8` | 15M | Fastest |
| `kitten-tts-micro-0.8` | 40M | Balanced |
| `kitten-tts-mini-0.8` | 80M | Best quality |

List and select a model:
```bash
sag models
sag models --select
```

## Configuration

Defaults are stored in `~/.config/sag/config.json`. You can set them interactively with `sag voices --select` and `sag models --select`, or override per-invocation with `-v` and `--model`.

## Options

| Flag | Description |
|------|-------------|
| `-v, --voice` | Voice name (default from config or Bella) |
| `--speed` | Speed multiplier, 0.5-2.0 (default: 1.0) |
| `-r, --rate` | Words per minute (converted to speed) |
| `-o, --output` | Save to file instead of playing |
| `--format` | Output format: wav or mp3 (auto-detected from extension) |
| `--model` | KittenTTS model ID (default from config) |
| `--version` | Show version |

## Development

```bash
pip install -e .
```

## License

MIT
