# Padwan CLI

Interactive CLI/TUI for `padwan-llm`.

<img alt="Chat demo" src="https://github.com/Polarsen/padwan-cli/raw/master/docs/static/chat.gif" width="800"/>

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
