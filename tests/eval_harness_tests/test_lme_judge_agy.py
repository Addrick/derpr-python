"""Unit tests for the agy-based LongMemEval (LME) judge harness (DP-363)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from eval_harnesses.suites.memory_recall.lme_judge import (
    DEFAULT_MODEL,
    _agy_bin,
    _agy_call,
    _looks_like_agent_leak,
    _parse_verdict,
    _score_at_k,
    resolve_lme_model,
    strip_system_messages,
)


def test_resolve_lme_model_aliases() -> None:
    assert resolve_lme_model("lme-t0") == "gemini-3.8-flash-low"
    assert resolve_lme_model("gemini-2.5-flash") == "gemini-3.8-flash-low"
    assert resolve_lme_model("lme-g3-t0") == "gemini-3.8-flash-low"
    assert resolve_lme_model("gemini-3-flash-preview") == "gemini-3.8-flash-low"
    assert resolve_lme_model("lme-25pro-t0") == "gemini-3.1-pro-low"
    assert resolve_lme_model("gemini-2.5-pro") == "gemini-3.1-pro-low"
    # Unaliased model names pass through untouched
    assert resolve_lme_model("gemini-3.8-flash-medium") == "gemini-3.8-flash-medium"
    assert resolve_lme_model("claude-sonnet-4-6") == "claude-sonnet-4-6"


def test_strip_system_messages() -> None:
    raw = (
        "<SYSTEM_MESSAGE>Task id finished with result</SYSTEM_MESSAGE>\n"
        "The total cost is $140.\n"
        "<SYSTEM_MESSAGE>Background cleanup done</SYSTEM_MESSAGE>"
    )
    cleaned = strip_system_messages(raw).strip()
    assert cleaned == "The total cost is $140."


def test_looks_like_agent_leak() -> None:
    assert _looks_like_agent_leak("I am ready to assist with your workspace.")
    assert _looks_like_agent_leak("Session_context loaded successfully.")
    assert _looks_like_agent_leak("The workspace is empty. Please provide instructions.")
    assert not _looks_like_agent_leak("The user purchased two items for $140.")


def test_agy_bin_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTIGRAVITY_HARNESS_PATH", "/custom/bin/agy")
    with patch("eval_harnesses.suites.memory_recall.lme_judge._AGY_BIN", None):
        assert _agy_bin() == "/custom/bin/agy"


def test_agy_bin_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTIGRAVITY_HARNESS_PATH", raising=False)
    with patch("shutil.which", return_value=None), patch("eval_harnesses.suites.memory_recall.lme_judge._AGY_BIN", None):
        with pytest.raises(RuntimeError, match="`agy` CLI not on PATH"):
            _agy_bin()


def test_agy_call_success() -> None:
    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = "<SYSTEM_MESSAGE>notice</SYSTEM_MESSAGE>42"
    fake_proc.stderr = ""

    with patch("eval_harnesses.suites.memory_recall.lme_judge._agy_bin", return_value="agy"), \
         patch("subprocess.run", return_value=fake_proc) as mock_run:
        result = _agy_call("what is the answer?", model="lme-t0")
        assert result == "42"

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "agy"
        assert "--sandbox" in cmd
        assert "--disable-slash-commands" in cmd
        assert "--model" in cmd
        model_idx = cmd.index("--model")
        assert cmd[model_idx + 1] == "gemini-3.8-flash-low"
        assert "-p" in cmd
        prompt_idx = cmd.index("-p")
        assert cmd[prompt_idx + 1] == "what is the answer?"


def test_agy_call_retry_on_agent_leak() -> None:
    leak_proc = MagicMock(returncode=0, stdout="I am ready to assist.", stderr="")
    clean_proc = MagicMock(returncode=0, stdout="42", stderr="")

    with patch("eval_harnesses.suites.memory_recall.lme_judge._agy_bin", return_value="agy"), \
         patch("subprocess.run", side_effect=[leak_proc, clean_proc]), \
         patch("time.sleep"):
        result = _agy_call("prompt", model="gemini-3.8-flash-low")
        assert result == "42"


def test_agy_call_retry_on_process_error() -> None:
    fail_proc = MagicMock(returncode=1, stdout="", stderr="network error")
    good_proc = MagicMock(returncode=0, stdout="success answer", stderr="")

    with patch("eval_harnesses.suites.memory_recall.lme_judge._agy_bin", return_value="agy"), \
         patch("subprocess.run", side_effect=[fail_proc, good_proc]), \
         patch("time.sleep"):
        result = _agy_call("prompt", model="gemini-3.8-flash-low")
        assert result == "success answer"


def test_parse_verdict() -> None:
    assert _parse_verdict("yes") is True
    assert _parse_verdict("Yes, that is correct.") is True
    assert _parse_verdict("no") is False
    assert _parse_verdict("No, the count is wrong.") is False
    assert _parse_verdict("maybe") is None
    assert _parse_verdict("") is None


def test_score_at_k() -> None:
    q = {
        "question_id": "test_q1",
        "question_type": "multi-session",
        "question": "What was the price?",
        "answer": "$140",
    }
    hits = [
        {"text": "Item 1 cost $120", "source": {"document_id": "sess_1"}},
        {"text": "Item 2 cost $20", "source": {"document_id": "sess_2"}},
    ]
    gold_sessions = {"sess_1", "sess_2"}

    # Mock answer and judge calls
    with patch("eval_harnesses.suites.memory_recall.lme_judge._agy_call", side_effect=["$140 total", "yes"]):
        res = _score_at_k(q, hits, gold_sessions, k=2, model_answer=DEFAULT_MODEL, model_judge=DEFAULT_MODEL)
        assert res["k"] == 2
        assert res["n_facts_in_context"] == 2
        assert res["session_hit_any"] is True
        assert res["session_hit_rate"] == 1.0
        assert res["predicted_answer"] == "$140 total"
        assert res["judge_verdict"] == "yes"
        assert res["judge_label"] is True
