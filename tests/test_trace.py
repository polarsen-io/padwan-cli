import pytest

import padwan_cli.trace as trace


class TestEnableTracing:
    @pytest.mark.parametrize(
        "backend",
        [
            pytest.param("langfuse", id="langfuse"),
            pytest.param("otlp", id="otlp"),
        ],
    )
    def test_backend_dispatch(self, monkeypatch, backend: trace.TraceBackend):
        calls: list[str] = []
        monkeypatch.setattr(trace, "_enable_langfuse", lambda: calls.append("langfuse"))
        monkeypatch.setattr(trace, "_enable_otlp", lambda: calls.append("otlp"))

        trace.enable_tracing(backend)

        assert calls == [backend]

    @pytest.mark.parametrize(
        "backend, extra",
        [
            pytest.param("langfuse", "langfuse", id="langfuse"),
            pytest.param("otlp", "otel", id="otlp"),
        ],
    )
    def test_missing_extra_exits_with_hint(
        self, monkeypatch, capsys, backend: trace.TraceBackend, extra: str
    ):
        def _raise() -> None:
            raise ImportError("missing dependency")

        monkeypatch.setattr(trace, "_enable_langfuse", _raise)
        monkeypatch.setattr(trace, "_enable_otlp", _raise)

        with pytest.raises(SystemExit):
            trace.enable_tracing(backend)

        assert f"--extra {extra}" in capsys.readouterr().out
