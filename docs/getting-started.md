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
- **CLI mode** (`python -m padwan_cli`) — traditional stdout output. Best for scripting and piping.

In TUI mode, chat responses render with colored messages and a live progress bar for batch jobs. In CLI mode, output is plain text suitable for piping to other tools.
