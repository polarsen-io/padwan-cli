from typing import cast

import pytest

from padwan_llm import AgentSession, LLMClientBase
from padwan_llm.models import UsageToken

from padwan_cli.chat import _format_tokens


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
