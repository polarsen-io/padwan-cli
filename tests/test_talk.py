import pytest

from padwan_cli.talk import load_api_key


def test_load_api_key_prefers_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    assert load_api_key() == "sk-from-env"


def test_load_api_key_reads_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text('OPENAI_API_KEY="sk-from-file"\n')
    # Restrict the search to this .env so a real ~/.../padwan-llm/.env can't leak in.
    monkeypatch.setattr("padwan_cli.talk._ENV_FILES", (env_file,))
    assert load_api_key() == "sk-from-file"


def test_load_api_key_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("padwan_cli.talk._ENV_FILES", ())
    assert load_api_key() is None


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
