import csv
import json

import pytest

from padwan_llm.gemini import BatchResult

from padwan_cli.batch.utils import load_prompts_from_file, save_results_to_file


def assert_(cond: bool) -> None:
    assert cond


class TestLoadPromptsFromFile:
    @pytest.mark.parametrize(
        "data, expected_keys, expected_texts",
        [
            pytest.param(
                ["What is AI?", "What is ML?"],
                ["prompt-0", "prompt-1"],
                ["What is AI?", "What is ML?"],
                id="json-string-array",
            ),
            pytest.param(
                [
                    {"prompt": "Hello", "key": "greeting"},
                    {"prompt": "Bye", "key": "farewell"},
                ],
                ["greeting", "farewell"],
                ["Hello", "Bye"],
                id="json-object-array",
            ),
        ],
    )
    def test_json_file(self, tmp_path, data, expected_keys, expected_texts):
        f = tmp_path / "prompts.json"
        f.write_text(json.dumps(data))

        requests = load_prompts_from_file(str(f))

        assert len(requests) == len(expected_keys)
        for req, key, text in zip(requests, expected_keys, expected_texts):
            assert req.key == key
            assert req.contents[0]["parts"][0]["text"] == text

    def test_text_file(self, tmp_path):
        f = tmp_path / "prompts.txt"
        f.write_text("First prompt\nSecond prompt\n\nThird prompt\n")

        requests = load_prompts_from_file(str(f))

        assert len(requests) == 3
        assert requests[0].contents[0]["parts"][0]["text"] == "First prompt"
        assert requests[1].key == "prompt-1"
        assert requests[2].contents[0]["parts"][0]["text"] == "Third prompt"


class TestSaveResultsToFile:
    @pytest.fixture
    def results(self):
        return [
            BatchResult(
                key="q1",
                content="Answer 1",
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
            ),
            BatchResult(
                key="q2",
                content="Answer 2",
                input_tokens=5,
                output_tokens=15,
                total_tokens=20,
            ),
        ]

    @pytest.mark.parametrize(
        "fmt, check",
        [
            pytest.param(
                "json",
                lambda p: (
                    (data := json.loads(p.read_text())),
                    assert_(len(data) == 2),
                    assert_(data[0]["key"] == "q1"),
                    assert_(data[0]["content"] == "Answer 1"),
                    assert_(data[0]["input_tokens"] == 10),
                    assert_(data[1]["key"] == "q2"),
                ),
                id="json",
            ),
            pytest.param(
                "csv",
                lambda p: (
                    (rows := list(csv.DictReader(p.read_text().splitlines()))),
                    assert_(len(rows) == 2),
                    assert_(rows[0]["key"] == "q1"),
                    assert_(rows[0]["content"] == "Answer 1"),
                    assert_(rows[1]["output_tokens"] == "15"),
                ),
                id="csv",
            ),
            pytest.param(
                "txt",
                lambda p: (
                    (text := p.read_text()),
                    assert_("[q1]" in text),
                    assert_("Answer 1" in text),
                    assert_("[q2]" in text),
                    assert_("Answer 2" in text),
                ),
                id="txt",
            ),
        ],
    )
    def test_save_results(self, tmp_path, results, fmt, check):
        out = tmp_path / f"out.{fmt}"
        save_results_to_file(results, str(out), fmt)
        check(out)
