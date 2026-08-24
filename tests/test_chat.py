from pathlib import Path
from typing import cast

import pytest

from padwan_llm import AgentSession, LLMClientBase
from padwan_llm.models import UsageToken

from padwan_cli.chat import _build_user_content, _format_tokens, _unsupported_warning
from padwan_cli.widgets import Attachment, AttachmentKind


def _attachment(
    path: Path, *, kind: AttachmentKind = "text", supported: bool = True
) -> Attachment:
    return Attachment(
        path=path,
        name=path.name,
        size=path.stat().st_size if path.exists() else 0,
        kind=kind,
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
        content = _build_user_content("look", [_attachment(img, kind="image")])

        assert isinstance(content, list)
        assert content[0] == {"type": "text", "text": "look"}
        assert content[1]["type"] == "image_url"
        assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")

    def test_text_and_supported_audio(self, tmp_path):
        clip = tmp_path / "clip.mp3"
        clip.write_bytes(b"ID3\x04")
        content = _build_user_content("listen", [_attachment(clip, kind="audio")])

        assert isinstance(content, list)
        assert content[1]["type"] == "input_audio"
        assert content[1]["input_audio"]["format"] == "mp3"

    @pytest.mark.parametrize(
        "data, name, kind, supported",
        [
            pytest.param(b"\x89PNG\r\n", "shot.png", "image", False, id="blind-image"),
            pytest.param(b"ID3\x04", "clip.mp3", "audio", False, id="deaf-audio"),
            pytest.param(b"ID3\x04", "clip.weird", "audio", True, id="bad-audio-fmt"),
            pytest.param(b"\xff\xfe\x00\x01", "blob.bin", "text", True, id="binary"),
        ],
    )
    def test_attachment_dropped_from_payload(
        self, tmp_path, data: bytes, name: str, kind: AttachmentKind, supported: bool
    ):
        f = tmp_path / name
        f.write_bytes(data)
        content = _build_user_content(
            "hi", [_attachment(f, kind=kind, supported=supported)]
        )

        assert content == [{"type": "text", "text": "hi"}]

    def test_text_file_inlined_with_header(self, tmp_path):
        f = tmp_path / "notes.md"
        f.write_text("# Hi")
        content = _build_user_content("read", [_attachment(f)])

        assert content[1] == {"type": "text", "text": "--- notes.md ---\n# Hi"}


class TestUnsupportedWarning:
    @pytest.mark.parametrize(
        "attachments, expected",
        [
            pytest.param(
                [("a.txt", "text", True), ("b.png", "image", True)],
                None,
                id="all-supported",
            ),
            pytest.param(
                [("a.png", "image", False)],
                "gpt-x can't read images — 1 will be skipped",
                id="image",
            ),
            pytest.param(
                [("a.mp3", "audio", False)],
                "gpt-x can't read audio — 1 will be skipped",
                id="audio",
            ),
            pytest.param(
                [("a.png", "image", False), ("b.mp3", "audio", False)],
                "gpt-x can't read images/audio — 2 will be skipped",
                id="mixed",
            ),
        ],
    )
    def test_warning(
        self,
        tmp_path,
        attachments: list[tuple[str, AttachmentKind, bool]],
        expected: str | None,
    ):
        atts = [
            _attachment(tmp_path / name, kind=kind, supported=supported)
            for name, kind, supported in attachments
        ]

        warning = _unsupported_warning("gpt-x", atts, suffix="will be skipped")

        assert warning == expected
