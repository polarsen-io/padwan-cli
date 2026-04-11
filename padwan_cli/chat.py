import contextlib
from typing import Any

from piou import Option, CommandGroup
from piou.tui import PromptStyle, TuiContext, TuiOption
from textual.css.query import NoMatches

from padwan_llm import (
    AgentSession,
    ConversationSnapshot,
    LLMClient,
    McpStreamable,
    McpTool,
    McpTransport,
)
from padwan_llm.gemini import GeminiClient
from padwan_llm.gemini.models import ThinkingConfig
from .utils import ALL_MODELS, console
from .widgets import StreamingMessage, ThoughtMessage, ToolCallMessage, UserMessage

chat_group = CommandGroup(name="chat", help="Chat with an LLM")

# Public, no-auth streamable-HTTP MCP server for data.gouv.fr
DATAGOUV_MCP_URL = "https://mcp.data.gouv.fr/mcp"


class _InMemoryStore:
    """ConversationStore keeping snapshots in memory across /chat:send calls.

    Implements the `padwan_llm.ConversationStore` protocol so that
    `AgentSession.load` / `AgentSession.save` transparently preserve chat
    history across successive command invocations within the same TUI run.
    """

    def __init__(self) -> None:
        self._data: dict[str, ConversationSnapshot] = {}

    def save(self, session_id: str, snapshot: ConversationSnapshot) -> None:
        self._data[session_id] = snapshot

    def load(self, session_id: str) -> ConversationSnapshot:
        return self._data[session_id]

    def forget(self, session_id: str | None) -> bool:
        """Drop one or all snapshots; return True if anything was removed."""
        if session_id is None:
            existed = bool(self._data)
            self._data.clear()
            return existed
        return self._data.pop(session_id, None) is not None


_store = _InMemoryStore()

CHAT_PROMPT = PromptStyle(text="You: ", css_class="chat-mode")


def _format_tokens(session: AgentSession, ctx: TuiContext | None = None) -> str:
    """Format token usage and connected MCP count for display."""
    if not session.last_usage:
        return ""
    last = session.last_usage
    total = session.total_usage
    parts = [f"in: {last['input']}", f"out: {last['output']}"]
    if "cached" in last:
        parts.append(f"cached: {last['cached']}")
    parts.append(f"| session: {total['total']}")
    # Count MCP transports (each represents a connected server); standalone
    # McpTool entries in mcp_tools are individual tool definitions, not servers.
    mcp_count = sum(1 for t in session.mcp_tools if not isinstance(t, McpTool))
    if mcp_count:
        parts.append(f"| mcp: {mcp_count}")
    if ctx and ctx.pending_count > 0:
        parts.append(f"| {ctx.pending_count} queued")
    return " ".join(parts)


@chat_group.command("send", help="Send a message to the LLM")
async def chat_send_fn(
        message: str = Option(..., help="Message to send"),
        model: str = Option(
            "gpt-4o-mini", "-m", "--model", help="Model to use", choices=ALL_MODELS
        ),
        session_id: str | None = Option(None, '--resume', help="Resume session"),
        ctx: TuiContext = TuiOption(),
) -> None:
    """Start a conversation. Use Ctrl+C to exit."""

    # Tracks whether the next text chunk should start a fresh streaming
    # widget. Mounted widgets keep their position in the message scroll, so
    # if we mounted a single StreamingMessage up-front any tool/thought
    # widgets fired mid-stream would land *below* the (still empty) text
    # placeholder — making the final answer appear above the tool calls
    # that produced it. Resetting this flag on every event splits the text
    # into one widget per "section" with tool/thought widgets between them.
    needs_new_text_widget = True

    def _on_tool(name: str, args: dict[str, Any]) -> None:
        nonlocal needs_new_text_widget
        if ctx.is_tui:
            ctx.mount_widget(ToolCallMessage(name, args))
            needs_new_text_widget = True
        else:
            console.print(f"[dim]→ tool call: {name}({args})[/dim]")

    def _on_thought(text: str) -> None:
        nonlocal needs_new_text_widget
        if ctx.is_tui:
            ctx.mount_widget(ThoughtMessage(text))
            needs_new_text_widget = True
        else:
            console.print(f"[dim italic]💭 {text}[/dim italic]")

    def _on_mcp_connect(transport: McpTransport) -> None:
        label = getattr(transport, "url", None) or transport.auto_prefix
        if ctx.is_tui:
            ctx.notify(str(label), title="MCP connected")
        else:
            console.print(f"[green]MCP connected[/green] [dim]{label}[/dim]")

    try:
        client = LLMClient(model=model, on_thought=_on_thought)
        if isinstance(client, GeminiClient):
            client.thinking_config = ThinkingConfig(includeThoughts=True)

        # `--resume` lets the user pick an explicit session id; otherwise we
        # key history by model so a second `/chat:send` continues the same
        # conversation (and `chat_clear_fn` can target it by model name).
        # `AgentSession.load` treats a missing snapshot as get-or-create, so
        # the first turn under a new id lands in the store via `session.save()`.
        session = AgentSession.load(
            client=client,
            mcp_tools=[McpStreamable(url=DATAGOUV_MCP_URL)],
            on_tool=_on_tool,
            on_mcp_connect=_on_mcp_connect,
            store=_store,
            session_id=session_id or model,
            max_tool_rounds=5,
        )
        async with session:
            user_input: str | None = message
            original_style = ctx.set_prompt_style(CHAT_PROMPT)
            ctx.set_hint("Chat mode - press Ctrl+C to exit")
            ctx.set_rule_above(add_class="chat-mode")
            ctx.set_rule_below(add_class="chat-mode")

            try:
                while user_input:
                    if ctx.is_tui:
                        ctx.mount_widget(UserMessage(user_input))
                        ctx.set_hint("Responding...")
                        ctx.set_silent_queue(True)
                        needs_new_text_widget = True
                        widget: StreamingMessage | None = None
                        async for chunk in session.stream(user_input):
                            if needs_new_text_widget:
                                widget = StreamingMessage()
                                ctx.mount_widget(widget)
                                needs_new_text_widget = False
                            assert widget is not None
                            widget.append(chunk)
                            if (n := ctx.pending_count) > 0:
                                ctx.set_hint(f"Responding... ({n} queued)")
                        ctx.set_silent_queue(False)
                        ctx.set_hint("Chat mode - press Ctrl+C to exit")
                        ctx.set_status_above(_format_tokens(session, ctx) or None)
                        user_input = await ctx.prompt()
                    else:
                        async for chunk in session.stream(user_input):
                            console.print(chunk, end="")
                        console.print()
                        if tokens := _format_tokens(session):
                            console.print(f"[dim]{tokens}[/dim]")
                        break
            finally:
                session.save()
                # Cleanup is best-effort — on a double-Ctrl+C the TUI screen
                # is already tearing down, so query_one("#status-above") and
                # friends raise NoMatches. Don't surface that as a misleading
                # "chat session failed" on what was actually a clean exit.
                with contextlib.suppress(NoMatches):
                    ctx.set_silent_queue(False)
                    ctx.clear_queue()  # Discard any messages typed during streaming
                    ctx.set_status_above(None)
                    ctx.set_hint(None)
                    ctx.set_rule_above(remove_class="chat-mode")
                    ctx.set_rule_below(remove_class="chat-mode")
                    if original_style:
                        ctx.set_prompt_style(original_style)
    except Exception as e:
        console.print(f"[red]Chat session failed: {e}[/red]")


@chat_group.command("clear", help="Clear conversation history")
async def chat_clear_fn(
        model: str | None = Option(
            None,
            "-m",
            "--model",
            help="Model session to clear (all if omitted)",
            choices=ALL_MODELS,
        ),
        ctx: TuiContext = TuiOption(),
) -> None:
    """Clear conversation history for a model or all models."""
    if model:
        if _store.forget(model):
            ctx.notify(f"Cleared history for {model}", title="Chat")
            print(f"Cleared conversation history for {model}")
        else:
            print(f"No active session for {model}")
    else:
        if _store.forget(None):
            ctx.notify("Cleared all chat history", title="Chat")
            print("Cleared all conversation history")
        else:
            print("No chat history to clear")
