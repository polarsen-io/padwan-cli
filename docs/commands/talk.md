# Talk

The `talk` command opens a real-time speech-to-speech session with a voice assistant: your microphone streams to the model and its audio reply plays through your speakers, with both transcripts printed as the conversation goes.

```bash
padwan-talk
# or
python -m padwan_cli talk
```

!!! note "Headless only"
    A live mic/speaker session needs the whole terminal, so `talk` can't run inside the TUI — use the `padwan-talk` entry point (or `python -m padwan_cli talk`).

## Requirements

- The `voice` extra: `pip install "padwan-cli[voice]"` (or `uv sync --extra voice` for local development)
- The PortAudio system library, e.g. `apt install libportaudio2`
- `OPENAI_API_KEY` set in the environment

## Options

| Option | Default | Description |
|---|---|---|
| `--voice` | `marin` | Realtime voice (`marin`, `cedar`, …) |
| `-m`, `--model` | `gpt-realtime` | Realtime model |
| `--instructions` | *built-in* | System prompt for the voice assistant |
| `--hands-free` | *off* | Auto voice detection instead of push-to-talk |
| `--check` | *off* | List audio devices and key status, then exit |
| `--trace` | *off* | Export LLM telemetry to `langfuse` or `otlp` (needs the matching extra) |

## Push-to-talk vs hands-free

By default the session is **push-to-talk**: hold **Space** while speaking and release it to send your turn. This disables server-side voice detection, so nothing is sent until you let go. Very short taps are discarded as accidental.

With `--hands-free`, the server's voice activity detection picks up turns automatically — just speak. Speaking while the assistant is answering interrupts it (barge-in): queued audio is dropped and the model listens to you instead.

Press **Ctrl+C** to quit either mode.

## Transcripts

Both sides of the conversation are transcribed and printed as you go:

```
you: what's the tallest mountain in Europe?
assistant: That's Mount Elbrus in Russia, at about 5,642 meters.
```

## Checking your setup

`--check` lists the available audio devices, the default input/output pair, and whether `OPENAI_API_KEY` is set — without opening a session:

```bash
padwan-talk --check
```
