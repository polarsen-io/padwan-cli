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

## Tracing

Pass `--trace <backend>` (on the one-shot, `chat send`, and `talk` commands) to instrument all LLM calls with [padwan-llm's OTel GenAI telemetry](https://github.com/polarsen-io/padwan-llm/blob/master/docs/observability.md):

```bash
# Langfuse, using the standard LANGFUSE_* env vars
export LANGFUSE_PUBLIC_KEY=... LANGFUSE_SECRET_KEY=... LANGFUSE_BASE_URL=...
uvx --from "padwan-cli[langfuse]" padwan-cli "Hello" --trace langfuse

# any OTLP collector, using the standard OTEL_EXPORTER_OTLP_* env vars
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
  uvx --from "padwan-cli[otel]" padwan-cli "Hello" --trace otlp
```

