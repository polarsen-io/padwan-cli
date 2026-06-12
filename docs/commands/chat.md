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
| `--base-url` | *none* | Custom OpenAI-compatible endpoint |
| `--extra-params` | *none* | Extra JSON object merged into every request body |
| `--mcp` | *none* | Streamable-HTTP MCP server URL(s) to expose as tools (space-separated) |
| `--resume` | *none* | Resume a previous session by ID |
| `--max-tools-round` | `20` | Maximum number of tool calls per round |

In TUI mode, the command enters an interactive loop — type follow-up messages and press Enter to continue the conversation. Press **Ctrl+C** to exit chat mode. Messages you type while the model is responding are queued and processed in order.

In CLI mode, the command sends a single message, prints the response, and exits.

After each response, token usage is displayed:

```
in: 42 out: 128 cached: 0 | session: 170 | mcp: 1 | 2 queued
```

- **in** — input tokens for the last request
- **out** — output tokens for the last request
- **cached** — cached tokens (if supported by the provider)
- **session** — cumulative tokens across the conversation
- **mcp** — number of connected MCP servers (only shown when > 0)
- **queued** — messages typed while the model was responding, awaiting their turn (only shown when > 0)

### Tools and MCP

Chat sessions run without tools by default. Pass `--mcp` with one or more streamable-HTTP MCP server URLs to expose their tools to the model:

```bash
# Single server (public, no-auth example)
padwan-cli chat send "Which datasets cover cycling?" --mcp https://mcp.data.gouv.fr/mcp

# Multiple servers (space-separated)
padwan-cli chat send "Hello" --mcp https://mcp.example.com/mcp https://mcp.data.gouv.fr/mcp
```

When a connection comes up you'll see an `MCP connected` notification, and any tool calls render as their own widgets (with elapsed time) inline with the response.

### Errors

Failures during a response (bad endpoint, invalid API key, provider errors…) are shown inline as a `✖` message and the chat stays usable — fix the issue or just send the next message.

### Thinking tokens

For Gemini models, the chat session enables `includeThoughts` so reasoning tokens stream into a separate "thought" widget above the answer. Other providers that emit reasoning chunks (e.g. via `--stream-thinking` on the one-shot path) behave the same way.

### Session persistence

Each model gets its own conversation session. 
Sending messages to `gpt-4o-mini` and then to `gemini-2.5-flash`
creates two independent sessions.
Switching back to a model resumes where you left off.

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
