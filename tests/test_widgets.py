from collections.abc import Callable

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from rich.console import Console

from padwan_cli.widgets import (
    USER_COLOR,
    Attachment,
    AttachmentBadge,
    BatchProgressWidget,
    BatchResultWidget,
    UserMessage,
    human_size,
    render_attachments,
    render_chips,
)


def _render_text(renderable, width: int = 200) -> str:
    """Render a Rich renderable to plain text for assertions."""
    console = Console(width=width)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


def _attachment(
    name: str = "f.txt", size: int = 1024, is_image: bool = False, supported: bool = True
) -> Attachment:
    return Attachment(
        path=f"/tmp/{name}", name=name, size=size, is_image=is_image, supported=supported
    )


class WidgetApp(App):
    """Minimal app that defers widget creation via a factory.

    Widgets that call self.update() in __init__ need an active app context,
    so we build them inside compose() rather than before mounting.
    """

    def __init__(self, factory: Callable[[], Static]) -> None:
        super().__init__()
        self._factory = factory

    def compose(self) -> ComposeResult:
        yield self._factory()


# UserMessage


class TestUserMessage:
    async def test_renders_content(self):
        app = WidgetApp(lambda: UserMessage("Hello, world!"))
        async with app.run_test():
            widget = app.query_one(UserMessage)
            rendered = widget.render()
            assert str(rendered) == "Hello, world!"

    async def test_applies_user_color(self):
        app = WidgetApp(lambda: UserMessage("test"))
        async with app.run_test():
            widget = app.query_one(UserMessage)
            rendered = widget.render()
            span = rendered._spans[0]
            assert span.style == USER_COLOR


# BatchProgressWidget


class TestBatchProgressWidget:
    async def test_displays_state(self, make_job):
        job = make_job(state="JOB_STATE_RUNNING")
        app = WidgetApp(lambda: BatchProgressWidget(job))
        async with app.run_test():
            widget = app.query_one(BatchProgressWidget)
            rendered = str(widget.render())
            assert "JOB_STATE_RUNNING" in rendered
            assert "123" in rendered

    async def test_displays_display_name(self, make_job):
        job = make_job(display_name="my-batch")
        app = WidgetApp(lambda: BatchProgressWidget(job))
        async with app.run_test():
            widget = app.query_one(BatchProgressWidget)
            rendered = str(widget.render())
            assert "my-batch" in rendered

    async def test_progress_bar_with_stats(self, make_job):
        job = make_job(
            state="JOB_STATE_RUNNING",
            stats={"successfulRequestCount": 5, "requestCount": 10},
        )
        app = WidgetApp(lambda: BatchProgressWidget(job))
        async with app.run_test():
            widget = app.query_one(BatchProgressWidget)
            rendered = str(widget.render())
            assert "5/10" in rendered

    async def test_update_job_tracks_state_history(self, make_job):
        job = make_job(state="JOB_STATE_PENDING")
        app = WidgetApp(lambda: BatchProgressWidget(job))
        async with app.run_test():
            widget = app.query_one(BatchProgressWidget)
            widget.update_job(make_job(state="JOB_STATE_RUNNING"))
            widget.update_job(make_job(state="JOB_STATE_SUCCEEDED"))
            rendered = str(widget.render())
            assert "History:" in rendered
            assert "PENDING" in rendered
            assert "RUNNING" in rendered
            assert "SUCCEEDED" in rendered


# BatchResultWidget


class TestBatchResultWidget:
    async def test_renders_result(self, make_result):
        results = [make_result(key="q1", content="Answer one")]
        app = WidgetApp(lambda: BatchResultWidget(results))
        async with app.run_test():
            widget = app.query_one(BatchResultWidget)
            rendered = str(widget.render())
            assert "q1" in rendered
            assert "Answer one" in rendered
            assert "10 in" in rendered
            assert "20 out" in rendered

    async def test_truncates_long_content(self, make_result):
        long_content = "x" * 500
        results = [make_result(content=long_content)]
        app = WidgetApp(lambda: BatchResultWidget(results))
        async with app.run_test():
            widget = app.query_one(BatchResultWidget)
            rendered = str(widget.render())
            assert "..." in rendered

    async def test_empty_results(self):
        app = WidgetApp(lambda: BatchResultWidget([]))
        async with app.run_test():
            widget = app.query_one(BatchResultWidget)
            rendered = str(widget.render())
            assert rendered.strip() == ""


# Attachments


class TestHumanSize:
    @pytest.mark.parametrize(
        "n, expected",
        [
            pytest.param(0, "0 B", id="zero"),
            pytest.param(512, "512 B", id="bytes"),
            pytest.param(1024, "1.0 KB", id="one-kb"),
            pytest.param(1536, "1.5 KB", id="kb-frac"),
            pytest.param(5 * 1024 * 1024, "5.0 MB", id="mb"),
        ],
    )
    def test_human_size(self, n, expected):
        assert human_size(n) == expected


class TestRenderChips:
    def test_includes_name_and_size(self):
        text = _render_text(render_chips([_attachment(name="a.png", size=4400)]))
        assert "a.png" in text
        assert "4.3 KB" in text

    def test_literal_name_with_brackets(self):
        text = _render_text(render_chips([_attachment(name="[bold].txt")]))
        assert "[bold].txt" in text


class TestRenderAttachments:
    def test_warning_line_above_chips(self):
        text = _render_text(
            render_attachments(
                [_attachment(name="x.png", is_image=True, supported=False)],
                warning="gpt-x can't read images — 1 will be skipped",
            )
        )
        assert "⚠ gpt-x can't read images" in text
        assert "x.png" in text

    def test_no_warning_when_none(self):
        text = _render_text(render_attachments([_attachment(name="ok.txt")]))
        assert "⚠" not in text
        assert "ok.txt" in text


class TestAttachmentBadge:
    async def test_renders_name_and_size(self):
        app = WidgetApp(lambda: AttachmentBadge([_attachment(name="a.txt", size=2048)]))
        async with app.run_test():
            rendered = _render_text(app.query_one(AttachmentBadge).content)
            assert "a.txt" in rendered
            assert "2.0 KB" in rendered

    async def test_shows_vision_warning(self):
        app = WidgetApp(
            lambda: AttachmentBadge(
                [_attachment(name="img.png", is_image=True, supported=False)],
                warning="gpt-x can't read images — 1 skipped",
            )
        )
        async with app.run_test():
            rendered = _render_text(app.query_one(AttachmentBadge).content)
            assert "can't read images" in rendered
