import contextlib
import json
import mimetypes
import os
import time
from contextlib import contextmanager
from typing import Any

from piou import Option, CommandGroup
from piou.tui import PromptStyle, TuiContext, TuiOption
from textual.css.query import NoMatches

from padwan_llm import (
    AgentSession,
    ContentPart,
    ConversationSnapshot,
    LLMClient,
    McpStreamable,
    McpTool,
    McpTransport,
    ToolCallContext,
    image_part,
    supports_vision,
    text_file_part,
    text_part,
)
from padwan_llm.gemini import GeminiClient
from padwan_llm.gemini.models import ThinkingConfig
from .utils import ALL_MODELS, console
from .widgets import (
    Attachment,
    AttachmentBadge,
    ErrorMessage,
    StreamingMessage,
    ThoughtMessage,
    ToolCallMessage,
    UserMessage,
    render_attachments,
)

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


def _build_user_content(
    text: str, attachments: list[Attachment]
) -> str | list[ContentPart]:
    """Assemble the user turn from typed text and queued attachments.

    Returns the plain string when nothing is attached. Otherwise builds content
    parts: the text, each text file inlined, and each supported image as a data
    URL. Unsupported images (text-only model) and unreadable files are dropped
    from the payload — they still appear in the sent badge.
    """
    if not attachments:
        return text
    parts: list[ContentPart] = []
    if text:
        parts.append(text_part(text))
    for a in attachments:
        if a.is_image:
            if a.supported:
                parts.append(image_part(a.path))
        else:
            try:
                parts.append(text_file_part(a.path))
            except OSError, UnicodeDecodeError:
                continue
    return parts


def _parse_extra_params(raw: str | None) -> tuple[dict[str, Any] | None, bool]:
    """Parse --extra-params JSON; print the error and return ok=False on failure."""
    if raw is None:
        return None, True
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        console.print(f"[red]--extra-params is not valid JSON: {e}[/red]")
        return None, False
    if not isinstance(parsed, dict):
        console.print("[red]--extra-params must be a JSON object[/red]")
        return None, False
    return parsed, True


@chat_group.command("send", help="Send a message to the LLM")
async def chat_send_fn(
    message: str = Option(..., help="Message to send"),
    model: str = Option("gpt-4o-mini", "-m", "--model", help="Model to use"),
    session_id: str | None = Option(None, "--resume", help="Resume session"),
    max_tool_rounds: int = Option(
        20, "--max-tools-round", help="Maximum number of tool calls per round"
    ),
    base_url: str | None = Option(
        None, "--base-url", help="Custom OpenAI-compatible endpoint"
    ),
    extra_params: str | None = Option(
        None,
        "--extra-params",
        help="Extra JSON object merged into every request body (e.g. '{\"temperature\": 0}')",
    ),
    mcp_urls: list[str] | None = Option(
        None,
        "--mcp",
        help=f"Streamable-HTTP MCP server URL(s) to expose as tools (e.g. {DATAGOUV_MCP_URL})",
    ),
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
    # Consecutive thought chunks stream into the same widget; any non-thought
    # event (tool call or text chunk) closes the current thought block so
    # the next thought starts a fresh widget.
    current_thought: ThoughtMessage | None = None

    @contextmanager
    def _on_tool(tc: ToolCallContext):
        nonlocal needs_new_text_widget, current_thought
        current_thought = None
        if ctx.is_tui:
            widget = ToolCallMessage(tc.name, tc.args)
            ctx.mount_widget(widget)
            needs_new_text_widget = True
            t0 = time.perf_counter()
            yield
            widget.set_elapsed(time.perf_counter() - t0)
        else:
            console.print(f"[dim]→ tool call: {tc.name}({tc.args})[/dim]")
            t0 = time.perf_counter()
            yield
            console.print(f"[dim]  ↳ {time.perf_counter() - t0:.1f}s[/dim]")

    def _on_thought(text: str) -> None:
        nonlocal needs_new_text_widget, current_thought
        if ctx.is_tui:
            if current_thought is None:
                current_thought = ThoughtMessage(text)
                ctx.mount_widget(current_thought)
            else:
                current_thought.append(text)
            needs_new_text_widget = True
        else:
            console.print(f"[dim italic]💭 {text}[/dim italic]", end="")

    def _on_mcp_connect(transport: McpTransport) -> None:
        if ctx.is_tui:
            ctx.notify(transport.label, title="MCP connected")
        else:
            console.print(f"[green]MCP connected[/green] [dim]{transport.label}[/dim]")

    parsed_extra, ok = _parse_extra_params(extra_params)
    if not ok:
        return

    try:
        client = LLMClient(model=model, on_thought=_on_thought, base_url=base_url)
        if isinstance(client, GeminiClient):
            client.thinking_config = ThinkingConfig(includeThoughts=True)

        # `--resume` lets the user pick an explicit session id; otherwise we
        # key history by model so a second `/chat:send` continues the same
        # conversation (and `chat_clear_fn` can target it by model name).
        # `AgentSession.load` treats a missing snapshot as get-or-create, so
        # the first turn under a new id lands in the store via `session.save()`.
        session = AgentSession.load(
            client=client,
            mcp_tools=[McpStreamable(url=url) for url in mcp_urls or ()],
            on_tool=_on_tool,
            on_mcp_connect=_on_mcp_connect,
            store=_store,
            session_id=session_id or model,
            max_tool_rounds=max_tool_rounds,
            extra_params=parsed_extra,
        )
        async with session:
            user_input: str | None = message
            original_style = ctx.set_prompt_style(CHAT_PROMPT)
            ctx.set_hint("Chat mode - press Ctrl+C to exit")
            ctx.set_rule_above(add_class="chat-mode")
            ctx.set_rule_below(add_class="chat-mode")

            # Files dropped onto the terminal arrive as a paste of their path(s);
            # queue them here and send with the next typed message.
            pending: list[Attachment] = []

            def _set_attach_warning(on: bool) -> None:
                """Turn the input bars amber (or back to chat-mode cyan)."""
                add, remove = (
                    ("attach-warning", "chat-mode")
                    if on
                    else ("chat-mode", "attach-warning")
                )
                ctx.set_rule_above(add_class=add, remove_class=remove)
                ctx.set_rule_below(add_class=add, remove_class=remove)

            def _on_drop(paths: list[str]) -> None:
                for p in paths:
                    try:
                        size = os.path.getsize(p)
                    except OSError:
                        continue
                    is_image = (mimetypes.guess_type(p)[0] or "").startswith("image/")
                    pending.append(
                        Attachment(
                            path=p,
                            name=os.path.basename(p),
                            size=size,
                            is_image=is_image,
                            supported=(not is_image) or supports_vision(model),
                        )
                    )
                blind = [a for a in pending if a.is_image and not a.supported]
                warning = (
                    f"{model} can't read images — {len(blind)} will be skipped"
                    if blind
                    else None
                )
                ctx.set_attachments(render_attachments(pending, warning=warning))
                _set_attach_warning(bool(blind))
                ctx.set_hint(
                    f"{len(pending)} attached — type a message · Ctrl+U clears"
                )

            def _on_clear() -> None:
                pending.clear()
                ctx.set_attachments(None)
                _set_attach_warning(False)
                ctx.set_hint("Chat mode - press Ctrl+C to exit")

            ctx.register_paste_handler(_on_drop)
            ctx.register_attachment_clear(_on_clear)

            try:
                while user_input:
                    if ctx.is_tui:
                        sent = list(pending)
                        ctx.mount_widget(UserMessage(user_input))
                        if sent:
                            skipped = [
                                a for a in sent if a.is_image and not a.supported
                            ]
                            badge_warning = (
                                f"{model} can't read images — {len(skipped)} skipped"
                                if skipped
                                else None
                            )
                            ctx.mount_widget(
                                AttachmentBadge(sent, warning=badge_warning)
                            )
                        content = _build_user_content(user_input, sent)
                        pending.clear()
                        ctx.set_attachments(None)
                        _set_attach_warning(False)
                        ctx.set_hint("Responding...")
                        ctx.set_silent_queue(True)
                        needs_new_text_widget = True
                        widget: StreamingMessage | None = None
                        try:
                            async for chunk in session.stream(content):
                                if needs_new_text_widget or widget is None:
                                    widget = StreamingMessage()
                                    ctx.mount_widget(widget)
                                    needs_new_text_widget = False
                                    current_thought = None
                                widget.append(chunk)
                                if (n := ctx.pending_count) > 0:
                                    ctx.set_hint(f"Responding... ({n} queued)")
                        except Exception as e:
                            # Surface the error inline: the outer handler is
                            # only reached after session teardown, which can
                            # hang on the MCP listener (see padwan-llm mcp.py).
                            ctx.mount_widget(ErrorMessage(str(e)))
                            needs_new_text_widget = True
                        ctx.set_silent_queue(False)
                        ctx.set_hint("Chat mode - press Ctrl+C to exit")
                        ctx.set_status_above(_format_tokens(session, ctx) or None)
                        user_input = await ctx.prompt()
                    else:
                        try:
                            async for chunk in session.stream(user_input):
                                console.print(chunk, end="")
                        except Exception as e:
                            console.print(f"\n[red]✖ {e}[/red]")
                            break
                        console.print()
                        if tokens := _format_tokens(session):
                            console.print(f"[dim]{tokens}[/dim]")
                        break
            finally:
                session.save()
                ctx.register_paste_handler(None)
                ctx.register_attachment_clear(None)
                # Cleanup is best-effort — on a double-Ctrl+C the TUI screen
                # is already tearing down, so query_one("#status-above") and
                # friends raise NoMatches. Don't surface that as a misleading
                # "chat session failed" on what was actually a clean exit.
                with contextlib.suppress(NoMatches):
                    ctx.set_silent_queue(False)
                    ctx.clear_queue()  # Discard any messages typed during streaming
                    ctx.set_status_above(None)
                    ctx.set_attachments(None)
                    ctx.set_hint(None)
                    ctx.set_rule_above(remove_class="chat-mode")
                    ctx.set_rule_below(remove_class="chat-mode")
                    ctx.set_rule_above(remove_class="attach-warning")
                    ctx.set_rule_below(remove_class="attach-warning")
                    if original_style:
                        ctx.set_prompt_style(original_style)
    except Exception as e:
        console.print_exception(show_locals=False)
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
