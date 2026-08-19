from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from rich import box
from rich.columns import Columns
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text
from textual.widgets import Static

from piou.tui import StreamingMessage as _StreamingMessage

if TYPE_CHECKING:
    from padwan_llm.gemini import BatchJob, BatchResult

# Colors for chat messages
USER_COLOR = "#87ceeb"
ASSISTANT_COLOR = "#98fb98"
TOOL_CALL_COLOR = "#ffa500"
THOUGHT_COLOR = "#9370db"
ERROR_COLOR = "#ff6b6b"
ATTACHMENT_COLOR = USER_COLOR
WARN_COLOR = "#fbbf24"
CHIP_BG = "#1f2230"
CHIP_BORDER = "#3a3f55"


@dataclass
class Attachment:
    """A file dropped into the chat, queued to send with the next message."""

    path: Path
    name: str
    size: int
    is_image: bool
    supported: bool  # whether the active model can use it (images need vision)


def human_size(num_bytes: int) -> str:
    """Format a byte count as a short human-readable string."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _chip_panel(a: Attachment) -> Panel:
    """Build one bordered pill chip for an attachment.

    Unsupported files get an amber border (the "which"); the reason — a
    model-level fact — is carried once by the warning bar and hint.
    """
    label = Text()
    label.append(f"📎 {a.name}", style=ATTACHMENT_COLOR)
    label.append(f"  {human_size(a.size)}", style="dim")
    return Panel(
        label,
        box=box.ROUNDED,
        border_style=WARN_COLOR if not a.supported else CHIP_BORDER,
        style=f"on {CHIP_BG}",
        padding=(0, 1),
        expand=False,
    )


def render_chips(attachments: list[Attachment]) -> Columns:
    """Render queued attachments as a row of bordered pill chips."""
    return Columns([_chip_panel(a) for a in attachments], padding=(0, 1), expand=False)


def render_attachments(
    attachments: list[Attachment], *, warning: str | None = None
) -> RenderableType:
    """Render the attachment block: an optional amber warning line, then chips."""
    chips = render_chips(attachments)
    if warning:
        return Group(Text(f"⚠ {warning}", style=WARN_COLOR), chips)
    return chips


class AttachmentBadge(Static):
    """Bordered pill chips shown under a sent user message."""

    def __init__(
        self, attachments: list[Attachment], *, warning: str | None = None, **kwargs
    ) -> None:
        super().__init__(render_attachments(attachments, warning=warning), **kwargs)


# Colors for batch job states
STATE_COLORS = {
    "JOB_STATE_PENDING": "#ffa500",
    "JOB_STATE_QUEUED": "#ffff00",
    "JOB_STATE_RUNNING": "#00bfff",
    "JOB_STATE_SUCCEEDED": "#98fb98",
    "JOB_STATE_FAILED": "#ff6b6b",
    "JOB_STATE_CANCELLED": "#808080",
    "JOB_STATE_EXPIRED": "#808080",
}


class UserMessage(Static):
    """A styled widget for displaying user messages."""

    def __init__(self, content: str, **kwargs) -> None:
        text = Text(content, style=USER_COLOR)
        super().__init__(text, **kwargs)


class ToolCallMessage(Static):
    """A styled widget for displaying an MCP tool call inline in the chat.

    Shows the tool name and a truncated one-line preview of its arguments,
    so the user can actually see when the agent reaches out to an MCP server
    mid-response (toast notifications are easy to miss).
    """

    _MAX_ARGS_CHARS = 120

    def __init__(self, name: str, args: dict[str, Any], **kwargs) -> None:
        self._tool_name = name
        args_str = json.dumps(args, ensure_ascii=False, sort_keys=True)
        if len(args_str) > self._MAX_ARGS_CHARS:
            args_str = args_str[: self._MAX_ARGS_CHARS - 1] + "…"
        self._args_str = args_str
        text = Text(f"\u26a1 {name}({args_str})", style=TOOL_CALL_COLOR)
        super().__init__(text, **kwargs)

    def set_elapsed(self, seconds: float) -> None:
        """Append elapsed time in dim style."""
        text = Text()
        text.append(
            f"\u26a1 {self._tool_name}({self._args_str})", style=TOOL_CALL_COLOR
        )
        text.append(f"  {seconds:.1f}s", style="dim")
        self.update(text)


class ErrorMessage(Static):
    """A styled widget for displaying an error inline in the chat."""

    def __init__(self, content: str, **kwargs) -> None:
        text = Text(f"✖ {content}", style=ERROR_COLOR)
        super().__init__(text, **kwargs)


class ThoughtMessage(Static):
    """A styled widget for displaying a model reasoning/thought block.

    Providers stream reasoning/thoughts in small chunks. `append` grows the
    widget in place so a continuous thought renders as one block instead
    of one widget per chunk.
    """

    def __init__(self, content: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._text = content
        self.update(Text(f"\U0001f4ad {self._text}", style=f"italic {THOUGHT_COLOR}"))

    def append(self, text: str) -> None:
        self._text += text
        self.update(Text(f"\U0001f4ad {self._text}", style=f"italic {THOUGHT_COLOR}"))


class StreamingMessage(_StreamingMessage):
    """Streaming message with assistant color styling.

    Extends piou's StreamingMessage (which handles autoscroll) to render
    text in the assistant color.
    """

    def append(self, text: str) -> None:
        self._text += text
        self.update(Text(self._text, style=ASSISTANT_COLOR))
        from piou.tui import TuiApp

        if isinstance(self.app, TuiApp):
            self.call_after_refresh(self.app._scroll_to_bottom)


class BatchProgressWidget(Static):
    """A widget that displays batch job progress with state coloring.

    Shows job name, current state (with color), progress bar showing
    succeeded/total requests, and elapsed time. Call update() to refresh
    with new job data.
    """

    def __init__(self, job: BatchJob, **kwargs) -> None:
        super().__init__(**kwargs)
        self._job = job
        self._state_history: list[str] = [job.state]
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Update the display with current job state."""
        job = self._job
        state_color = STATE_COLORS.get(job.state, "white")

        # Build progress info
        succeeded = 0
        total = 0
        if job.stats:
            succeeded = cast(int, job.stats.get("successfulRequestCount", 0))
            total = cast(int, job.stats.get("requestCount", 0))

        # Create progress bar
        bar_width = 30
        if total > 0:
            filled = int((succeeded / total) * bar_width)
        else:
            filled = 0
        bar = "\u2588" * filled + "\u2591" * (bar_width - filled)

        # Build display text
        lines = [
            f"Job: {job.name.split('/')[-1]}",
            f"State: [{state_color}]{job.state}[/{state_color}]",
            f"Progress: [{bar}] {succeeded}/{total}",
        ]

        if job.display_name:
            lines.insert(1, f"Name: {job.display_name}")

        # Show state history if there were transitions
        if len(self._state_history) > 1:
            history = " -> ".join(
                s.replace("JOB_STATE_", "") for s in self._state_history
            )
            lines.append(f"History: {history}")

        text = Text("\n".join(lines))
        self.update(text)

    def update_job(self, job: BatchJob) -> None:
        """Update with new job data and refresh display."""
        if job.state != self._job.state:
            self._state_history.append(job.state)
        self._job = job
        self._refresh_display()


class BatchResultWidget(Static):
    """A widget that displays batch results in a styled format.

    Shows each result with its key, token counts, and content preview.
    Useful for viewing results in TUI mode.
    """

    def __init__(self, results: list[BatchResult], **kwargs) -> None:
        super().__init__(**kwargs)
        self._results = results
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Update the display with results."""
        lines: list[str] = []

        for result in self._results:
            # Header with key and token info
            lines.append(
                f"[cyan]\\[{result.key}][/cyan] "
                f"[dim]({result.input_tokens} in, {result.output_tokens} out, "
                f"{result.total_tokens} total tokens)[/dim]"
            )

            # Content preview (truncated)
            preview = result.content[:300].replace("\n", " ")
            if len(result.content) > 300:
                preview += "..."
            lines.append(f"  {preview}")
            lines.append("")

        text = Text.from_markup("\n".join(lines))
        self.update(text)
