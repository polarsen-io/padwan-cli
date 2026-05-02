# Getting Started

## Installation

```bash
pip install padwan-cli
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install padwan-cli
```

## Requirements

- Python >= 3.14
- API keys for the providers you want to use (set as environment variables, e.g. `OPENAI_API_KEY`, `GEMINI_API_KEY`, etc.)

## Local development

```bash
git clone https://github.com/Polarsen/padwan-llm.git
git clone https://github.com/Polarsen/padwan-cli.git
cd padwan-cli
uv sync --group dev
uv run padwan-cli
```

## Basic usage

### One-shot query

Send a single prompt and print the response:

```bash
padwan-cli "What is the capital of France?" -m gpt-4o-mini
```

Use `--stream` (`-s`) to see tokens as they arrive:

```bash
padwan-cli "Tell me a story" -m gpt-4o-mini --stream
```

The default model is `gpt-4o-mini`. Use `-m` to pick any supported model.

Point to a custom OpenAI-compatible endpoint with `--base-url`, and pass extra request parameters with `--extra-params`:

```bash
padwan-cli "Hello" --base-url http://localhost:8000/v1 --extra-params '{"temperature": 0}'
```

Use `--stream-thinking` (with `--stream`) to stream model reasoning tokens to stderr.

### List models

See all models available across providers:

```bash
padwan-cli models
```

Filter by provider:

```bash
padwan-cli models -p openai
padwan-cli models -p gemini
```

### Library info

Show model counts per provider:

```bash
padwan-cli info
```

## CLI vs TUI mode

Padwan CLI ships with two entry points backed by the same commands:

- **TUI mode** (default via `padwan-cli`) — interactive terminal UI with styled output, streaming widgets, and an input prompt. Best for chat sessions and batch monitoring.
- **CLI mode** (`python -m padwan_cli`) — traditional stdout output. Best for scripting, piping, and CI.

Every command works in both modes. Examples in CLI mode:

```bash
# One-shot query (default subcommand)
python -m padwan_cli "Explain monads in one sentence" -m gpt-4o-mini

# Stream and pipe to another tool
python -m padwan_cli "Write a haiku about Rust" -m gpt-4o-mini --stream | tee out.txt

# Single-turn chat (no interactive loop in CLI mode — sends one message and exits)
python -m padwan_cli chat send "Hello" -m gpt-4o-mini

# Batch operations
python -m padwan_cli batch create -p "Explain gravity" -m gemini-2.5-flash
python -m padwan_cli batch poll -j <job-name> -i 10
```

Behaviour differences:

- **`chat send`**: TUI mode enters an interactive loop until Ctrl+C; CLI mode sends one message, prints the response (and a `[dim]` token-usage line), then exits.
- **`batch poll`**: TUI mode shows a live progress widget; CLI mode prints one `[STATE] Ns elapsed` line per poll.
- **`batch status -r` / `batch poll -r`**: TUI renders a result widget; CLI prints each result inline with a 300-char preview.
- **Tool calls and thoughts**: TUI mounts dedicated widgets; CLI prints `→ tool call: name(args)` and `💭 ...` to the console as `[dim]` text.

In CLI mode, output is plain (Rich-styled) text suitable for piping to other tools.
