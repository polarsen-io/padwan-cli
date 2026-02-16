# Chat

The `chat` command group provides interactive, multi-turn conversations with LLMs. Sessions are persisted in memory per model for the lifetime of the process.

<img alt="Chat demo" src="../static/chat.gif" width="800"/>

## `chat send`

Start (or continue) a conversation with a model.

```bash
padwan-cli chat send "Hello, how are you?" -m gpt-4o-mini
```

| Option | Default | Description |
|---|---|---|
| `MESSAGE` (positional) | *required* | The message to send |
| `-m`, `--model` | `gpt-4o-mini` | Model to use |

In TUI mode, the command enters an interactive loop — type follow-up messages and press Enter to continue the conversation. Press **Ctrl+C** to exit chat mode. Messages you type while the model is responding are queued and processed in order.

In CLI mode, the command sends a single message, prints the response, and exits.

After each response, token usage is displayed:

```
in: 42 out: 128 cached: 0 | session: 170
```

- **in** — input tokens for the last request
- **out** — output tokens for the last request
- **cached** — cached tokens (if supported by the provider)
- **session** — cumulative tokens across the conversation

### Session persistence

Each model gets its own conversation session. Sending messages to `gpt-4o-mini` and then to `gemini-2.0-flash` creates two independent sessions. Switching back to a model resumes where you left off.

## `chat clear`

Clear conversation history.

```bash
# Clear history for a specific model
padwan-cli chat clear -m gpt-4o-mini

# Clear all sessions
padwan-cli chat clear
```

| Option | Default | Description |
|---|---|---|
| `-m`, `--model` | *all* | Model session to clear. Clears all sessions if omitted. |
