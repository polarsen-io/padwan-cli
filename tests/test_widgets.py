from collections.abc import Callable

from textual.app import App, ComposeResult
from textual.widgets import Static

from padwan_cli.widgets import (
    USER_COLOR,
    BatchProgressWidget,
    BatchResultWidget,
    UserMessage,
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
