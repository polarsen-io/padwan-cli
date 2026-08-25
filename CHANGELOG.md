## 0.6.0 (2026-08-25)

### Feat

- one-shot -f/--file attachments routed by content type
- wire --trace into chat, talk, and the one-shot command
- **chat**: audio file attachments gated by supports_audio
- list Anthropic models in models, info, and model choices
- opt-in tracing (Langfuse or OTLP export)

## 0.5.0 (2026-08-19)

### Feat

- **chat**: optional first message for chat:start; quote just chat args
- just chat recipe and env.template
- **chat**: chat:start interactive terminal session
- **talk**: print your transcript before the tutor's reply
- **talk**: hold-to-talk — hold Space while speaking, release to send
- **chat**: file attachments + talk voice tutor

### Fix

- **talk**: batch mic audio per send and flush before commit
- **talk**: clean shutdown — cancel turn tasks, route Ctrl-C through task cancellation, timed mic reads

### Refactor

- **chat**: adopt piou's list[Path] paste contract
- **talk**: let the padwan-llm client validate the API key
- **talk**: drop the hardcoded .env fallback; require OPENAI_API_KEY in the environment
- just chat opens the chat TUI instead of headless send
- **chat**: drop chat:start; just chat wraps chat:send
- **talk**: generic voice assistant instead of the language-tutor persona

### Perf

- **talk**: tracktolib BytesBuffer for speaker playback

## 0.4.0 (2026-06-12)

### Feat

- **chat**: surface streaming errors inline and make MCP opt-in

## 0.3.0 (2026-05-02)

### Feat

- add --base-url, --extra-params, and --stream-thinking CLI options
- tool elapsed time, streaming thoughts, tunable tool rounds
- wire AgentSession + MCP with on_mcp_connect callback
- add test suite using Textual's run_test pattern

### Fix

- show traceback before 'Chat session failed' message
- upgrade qh3 1.5.6 → 1.7.1 to fix intermittent QUIC cert errors

## 0.2.3 (2026-02-17)

### Fix

- correct GitHub org in README links

## 0.2.2 (2026-02-17)

### Fix

- broken gif link in README

## 0.2.1 (2026-02-17)

### Fix

- CI publish

## 0.2.0 (2026-02-17)

### Feat

- first commit

### Fix

- remove .idea
