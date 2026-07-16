from pathlib import Path

from rich.console import Console
from textual.events import Paste
from textual.widgets import Static

from piou.tui.app import PromptInput

from padwan_cli.run import cli, CUSTOM_CSS
from padwan_cli.widgets import Attachment, render_attachments


def _app():
    return cli.tui_app(css=CUSTOM_CSS)


def _render_text(renderable, width: int = 200) -> str:
    console = Console(width=width)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


class TestChatTuiAttachments:
    async def test_app_composes_with_attachment_tray(self):
        app = _app()
        async with app.run_test():
            tray = app.query_one("#attachment-tray", Static)
            assert app.query_one(PromptInput) is not None
            assert tray.display is False

    async def test_dropped_file_shows_chip_and_keeps_input_clean(self, tmp_path):
        f = tmp_path / "report.md"
        f.write_text("hello")
        pending: list[Attachment] = []

        app = _app()
        async with app.run_test() as pilot:
            # Mirror the chat command's drop handler over the real framework path.
            def on_drop(paths: list[str]) -> None:
                for p in paths:
                    pending.append(
                        Attachment(
                            path=p,
                            name=Path(p).name,
                            size=Path(p).stat().st_size,
                            is_image=False,
                            supported=True,
                        )
                    )
                app.set_attachments(render_attachments(pending))

            app.register_paste_handler(on_drop)
            inp = app.query_one(PromptInput)
            inp.post_message(Paste(f"file://{f}"))
            await pilot.pause()

            tray = app.query_one("#attachment-tray", Static)
            assert tray.display is True
            assert "report.md" in _render_text(tray.content)
            assert inp.value == ""
