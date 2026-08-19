from pathlib import Path
from typing import cast

import pytest

from padwan_llm import AgentSession, LLMClientBase
from padwan_llm.models import UsageToken

from padwan_cli.chat import _build_user_content, _format_tokens
from padwan_cli.widgets import Attachment


def _attachment(path: Path, *, is_image: bool, supported: bool) -> Attachment:
    return Attachment(
        path=str(path),
        name=path.name,
        size=path.stat().st_size,
        is_image=is_image,
        supported=supported,
    )


class FakeClient:
    """Minimal stand-in for LLMClientBase to build an AgentSession."""

    pass


class TestFormatTokens:
    @pytest.mark.parametrize(
        "last_usage, total_usage, expected_parts",
        [
            pytest.param(
                None,
                UsageToken(total=0, input=0, output=0),
                [],
                id="no-usage",
            ),
            pytest.param(
                UsageToken(total=30, input=10, output=20),
                UsageToken(total=100, input=40, output=60),
                ["in: 10", "out: 20", "session: 100"],
                id="basic-usage",
            ),
            pytest.param(
                UsageToken(total=30, input=10, output=20, cached=5),
                UsageToken(total=100, input=40, output=60),
                ["in: 10", "out: 20", "cached: 5", "session: 100"],
                id="with-cached",
            ),
        ],
    )
    def test_format_tokens(self, last_usage, total_usage, expected_parts):
        session = AgentSession(client=cast(LLMClientBase, FakeClient()), system=None)
        session._state.last_usage = last_usage
        session._state.total_usage = total_usage

        result = _format_tokens(session)

        if not expected_parts:
            assert result == ""
        else:
            for part in expected_parts:
                assert part in result


class TestBuildUserContent:
    def test_no_attachments_returns_plain_text(self):
        assert _build_user_content("hi", []) == "hi"

    def test_text_and_supported_image(self, tmp_path):
        img = tmp_path / "shot.png"
        img.write_bytes(b"\x89PNG\r\n")
        content = _build_user_content(
            "look", [_attachment(img, is_image=True, supported=True)]
        )

        assert isinstance(content, list)
        assert content[0] == {"type": "text", "text": "look"}
        assert content[1]["type"] == "image_url"
        assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")

    def test_unsupported_image_dropped_from_payload(self, tmp_path):
        img = tmp_path / "shot.png"
        img.write_bytes(b"\x89PNG\r\n")
        content = _build_user_content(
            "look", [_attachment(img, is_image=True, supported=False)]
        )

        assert content == [{"type": "text", "text": "look"}]

    def test_text_file_inlined_with_header(self, tmp_path):
        f = tmp_path / "notes.md"
        f.write_text("# Hi")
        content = _build_user_content(
            "read", [_attachment(f, is_image=False, supported=True)]
        )

        assert content[1] == {"type": "text", "text": "--- notes.md ---\n# Hi"}

    def test_undecodable_file_skipped(self, tmp_path):
        f = tmp_path / "blob.bin"
        f.write_bytes(b"\xff\xfe\x00\x01")
        content = _build_user_content(
            "read", [_attachment(f, is_image=False, supported=True)]
        )

        assert content == [{"type": "text", "text": "read"}]
