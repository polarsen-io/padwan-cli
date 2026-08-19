import pytest


async def test_talk_command_refuses_tui(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import padwan_cli.talk as talk

    monkeypatch.setattr(talk, "get_tui_context", lambda: SimpleNamespace(is_tui=True))

    def _boom():
        raise AssertionError("audio must not be touched inside the TUI")

    monkeypatch.setattr(talk, "_import_sounddevice", _boom)
    # The guard must return early, before importing sounddevice or opening a session.
    result = await talk.talk_command(
        voice="marin",
        model="gpt-realtime",
        instructions=None,
        check=False,
    )
    assert result is None
