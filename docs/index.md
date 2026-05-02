# Padwan CLI

Padwan CLI is an interactive CLI and TUI for [padwan-llm](https://github.com/Polarsen/padwan-llm), the unified LLM client library. 
It provides a terminal interface for querying multiple LLM providers — OpenAI, Gemini, Mistral, and Grok — through a single tool.

!!! note "Playground project"
    This is a playground for experimenting with `padwan-llm` features (streaming, agents, MCP, thinking tokens, batch jobs) — not a production-grade tool. Expect rough edges and breaking changes.

## Features

- **One-shot queries** — send a prompt and get a response, with optional streaming
- **Interactive chat** — multi-turn conversations with persistent session history
- **Batch processing** — submit, poll, and export Gemini batch jobs
- **Dual interface** — works as both a traditional CLI and a rich TUI (via [piou](https://github.com/Polarsen/piou))
- **Multi-provider** — switch between providers with a `-m` flag

<img alt="Chat demo" src="static/chat.gif" width="800"/>

## Quick example

```bash
# Try it without installing
uvx padwan-cli "Explain monads in one sentence" -m gpt-4o-mini

# One-shot query
padwan-cli "Explain monads in one sentence" -m gpt-4o-mini

# Stream the response
padwan-cli "Write a haiku about Rust" -m gpt-4o-mini --stream

# Interactive chat
padwan-cli chat send "Hello!" -m gpt-4o-mini

# List available models
padwan-cli models

# CLI mode (no TUI) — same commands, plain stdout
python -m padwan_cli "Explain monads" -m gpt-4o-mini
```

The `padwan-cli` script launches the TUI; `python -m padwan_cli` runs the same commands in plain CLI mode for scripting and piping. See [Getting Started](getting-started.md#cli-vs-tui-mode) for details.

## Commands overview

| Command | Description |
|---|---|
| *(default)* | One-shot LLM query |
| `models` | List available models across providers |
| `info` | Show model count per provider |
| `chat send` | Start an interactive conversation |
| `chat clear` | Clear conversation history |
| `batch create` | Create a Gemini batch job |
| `batch status` | Check batch job status |
| `batch list` | List recent batch jobs |
| `batch poll` | Poll a batch job until completion |
| `batch cancel` | Cancel a batch job |
| `batch retry` | Retry failed requests from a batch |
| `batch export` | Export batch results to a file |
