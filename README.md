# Padwan CLI

Interactive CLI/TUI for [`padwan-llm`](https://github.com/polarsen-io/padwan-llm).

> [!NOTE]
> This is a playground for experimenting with `padwan-llm` features (streaming, agents, MCP, thinking tokens, batch jobs, realtime voice) — not a production-grade tool. Expect rough edges and breaking changes.

<img alt="Chat demo" src="https://github.com/polarsen-io/padwan-cli/raw/master/docs/static/chat.gif" width="800"/>

## Quick start

```bash
export OPENAI_API_KEY=...
uvx padwan-cli
# then /help for commands
```


## Install

```bash
pip install padwan-cli
```

## Local Development

```bash
uv sync --group dev
uv run padwan-cli
```

## One-shot Mode

```bash
uvx padwan-cli "Hello" -m gpt-4o-mini
```

## Voice Mode

Real-time speech-to-speech chat (needs the PortAudio system lib, e.g. `libportaudio2`):

```bash
uvx --from "padwan-cli[voice]" padwan-talk
```

