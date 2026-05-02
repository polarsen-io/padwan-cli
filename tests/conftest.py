from collections.abc import Callable
from dataclasses import dataclass

import pytest

from padwan_llm.gemini import BatchResult


@dataclass
class FakeBatchJob:
    name: str = "projects/test/locations/us/batchPredictionJobs/123"
    state: str = "JOB_STATE_PENDING"
    display_name: str | None = None
    model: str | None = None
    create_time: str | None = None
    error: dict | None = None
    stats: dict | None = None

    @property
    def is_terminal(self) -> bool:
        return self.state in {
            "JOB_STATE_SUCCEEDED",
            "JOB_STATE_FAILED",
            "JOB_STATE_CANCELLED",
            "JOB_STATE_EXPIRED",
        }

    @property
    def succeeded(self) -> bool:
        return self.state == "JOB_STATE_SUCCEEDED"


@pytest.fixture
def make_job() -> Callable[..., FakeBatchJob]:
    def _make(**kwargs) -> FakeBatchJob:
        return FakeBatchJob(**kwargs)

    return _make


@pytest.fixture
def make_result() -> Callable[..., BatchResult]:
    def _make(
        key: str = "prompt-0",
        content: str = "Hello world",
        input_tokens: int = 10,
        output_tokens: int = 20,
        total_tokens: int = 30,
    ) -> BatchResult:
        return BatchResult(
            key=key,
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    return _make
