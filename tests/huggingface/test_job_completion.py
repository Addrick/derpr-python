"""DP-343/345 — the node's completion ping, turned back into the turn that asked.

Two properties under test throughout:

- **The ping is a doorbell.** It carries a job id and nothing else; everything
  reported comes from the SSH status read. The node half (the `curl` in
  `derpr-model-install` / `derpr-model-tier`) is covered in
  tests/services/test_job_completion_ping.py; this file starts at the job id.
- **The job id is the park token.** The bridge resolves a `node_job` deferral by
  that id and does not choose a conversation, because the row already did. This
  is what deleted `MODEL_JOB_WAKE_PERSONA` / `_CHANNEL` / `_USER` — pinned by
  `test_nothing_here_names_a_persona_channel_or_user` below.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config import global_config
from src.deferral_kinds import DEFERRAL_KIND_NODE_JOB
from src.generation_events import DoneEvent, ResponseType
from src.huggingface.completion import JobCompletionBridge


ALERT_CHANNEL = "999888777"


@pytest.fixture(autouse=True)
def alert_configured(monkeypatch):
    monkeypatch.setattr(global_config, "MODEL_JOB_ALERT_CHANNEL_ID",
                        ALERT_CHANNEL, raising=False)


def _job(**over):
    job = {
        "job_id": "newmodel-abc123",
        "state": "done",
        "step": "installed",
        "reason": "",
        "repo": "bartowski/Qwen3-32B-GGUF",
        "file": "Qwen3-32B-Q4_K_M.gguf",
        "name": "newmodel",
        "unit": "koboldcpp-newmodel.service",
        "size_bytes": 20_000_000_000,
        "contextsize": 8192,
    }
    job.update(over)
    return job


class _FakeChat:
    """Records each `stream_resolve_deferral` call and replays scripted events.

    `replies` is one list per call, so a retried ping can be given an empty
    list — which is exactly what the real store does once the park is claimed.
    """

    def __init__(self, replies=(("all done",),), raises=None):
        self.calls = []
        self._replies = list(replies)
        self._raises = raises

    def stream_resolve_deferral(self, token, *, kind, status, result, note=None):
        self.calls.append({"token": token, "kind": kind, "status": status,
                           "result": result, "note": note})
        raises, texts = self._raises, (
            self._replies.pop(0) if self._replies else ()
        )

        async def _gen():
            if raises:
                raise raises
            for text in texts:
                yield DoneEvent(text=text,
                                response_type=ResponseType.DEV_COMMAND)
        return _gen()


def _bridge(status=None, replies=(("all done",),), raises=None):
    """A bridge with all three collaborators faked."""
    handler = SimpleNamespace(job_status=AsyncMock(
        return_value=status if status is not None else {
            "status": "ok", "job": _job(),
            "note": "KV cache for this model: 1024 bytes per token",
        }
    ))
    chat = _FakeChat(replies=replies, raises=raises)
    notifier = SimpleNamespace(send=AsyncMock(return_value=True))
    return JobCompletionBridge(handler, chat, notifier), handler, chat, notifier


# ---------------------------------------------------------------------------
# the happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_finished_install_resumes_the_turn_and_announces():
    bridge, handler, chat, notifier = _bridge()

    res = await bridge.handle("newmodel-abc123")

    assert res == {"status": "ok", "resumed": True, "announced": True,
                   "job_id": "newmodel-abc123", "state": "done"}
    handler.job_status.assert_awaited_once_with("newmodel-abc123")
    assert len(chat.calls) == 1
    call = chat.calls[0]
    assert call["token"] == "newmodel-abc123"
    assert call["kind"] == DEFERRAL_KIND_NODE_JOB
    assert call["status"] == "done"
    assert notifier.send.await_args.kwargs["recipient"] == ALERT_CHANNEL
    assert notifier.send.await_args.kwargs["body"] == "all done"


@pytest.mark.asyncio
async def test_nothing_here_names_a_persona_channel_or_user():
    """THE reason three settings were deleted, pinned as a property.

    The bridge addresses the deferral by token; the persona, channel and user
    come off the park row, which took them from the turn that started the job.
    If any of them were ever re-introduced here they would be a second source
    of truth for a fact the row already holds, and could only disagree with it.
    """
    bridge, _, chat, _ = _bridge()

    await bridge.handle("newmodel-abc123")

    assert set(chat.calls[0]) == {"token", "kind", "status", "result", "note"}
    for gone in ("MODEL_JOB_WAKE_PERSONA", "MODEL_JOB_WAKE_CHANNEL",
                 "MODEL_JOB_WAKE_USER"):
        assert not hasattr(global_config, gone), (
            f"{gone} is back; the park row already carries that coordinate"
        )


@pytest.mark.asyncio
async def test_the_outcome_comes_from_the_status_read_not_the_ping():
    """The ping carries a job id. Everything else is re-read over SSH."""
    bridge, _, chat, _ = _bridge()

    await bridge.handle("newmodel-abc123")

    result = chat.calls[0]["result"]
    assert result["repo"] == "bartowski/Qwen3-32B-GGUF"
    assert result["unit"] == "koboldcpp-newmodel.service"
    assert result["state"] == "done"
    assert chat.calls[0]["note"].startswith("KV cache")


@pytest.mark.asyncio
async def test_promotion_gets_the_promotion_instruction():
    bridge, _, chat, _ = _bridge(status={
        "status": "ok",
        "job": _job(kind="promote", step="copied", name="oldmodel"),
    })

    await bridge.handle("oldmodel-abc123")

    instruction = chat.calls[0]["result"]["instruction"]
    assert "did NOT change what :5001 is serving" in instruction
    assert "set_active_model" in instruction


@pytest.mark.asyncio
async def test_failed_job_gets_the_failure_instruction():
    bridge, _, chat, _ = _bridge(status={
        "status": "ok",
        "job": _job(state="failed", step="verify", reason="sha256 mismatch"),
    })

    res = await bridge.handle("newmodel-abc123")

    assert res["state"] == "failed"
    assert chat.calls[0]["status"] == "failed"
    result = chat.calls[0]["result"]
    # The facts ride in the result; the instruction says what to do about them.
    assert result["step"] == "verify"
    assert result["reason"] == "sha256 mismatch"
    assert "Do not retry it on your own" in result["instruction"]


# ---------------------------------------------------------------------------
# nothing to resolve
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unreadable_job_resolves_nothing():
    """The node says it finished; its own status verb cannot say what happened.

    Resolving a deferral with "something finished, I cannot tell you what" is
    worse than the silence this feature replaced.
    """
    bridge, _, chat, notifier = _bridge(
        status={"status": "error", "message": "no such job"})

    res = await bridge.handle("newmodel-abc123")

    assert res["status"] == "error"
    assert chat.calls == []
    notifier.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_terminal_job_is_ignored():
    bridge, _, chat, _ = _bridge(
        status={"status": "ok", "job": _job(state="running")})

    res = await bridge.handle("newmodel-abc123")

    assert res["status"] == "ignored"
    assert chat.calls == []


@pytest.mark.asyncio
async def test_a_retried_ping_resolves_once():
    """The node sends a second ping ~6s later.

    Idempotency is the durable row claim inside `take`, not a set in this
    process — which is the difference that makes it survive a restart. Here the
    second call yields no events because the park is already gone.
    """
    bridge, _, chat, notifier = _bridge(replies=(("all done",), ()))

    first = await bridge.handle("newmodel-abc123")
    second = await bridge.handle("newmodel-abc123")

    assert first["resumed"] is True
    assert second["resumed"] is False
    assert len(chat.calls) == 2, "the second ping still re-reads and re-claims"
    assert notifier.send.await_count == 1, "a retry must not announce twice"


@pytest.mark.asyncio
async def test_empty_job_id_rejected_without_a_status_read():
    bridge, handler, chat, _ = _bridge()

    res = await bridge.handle("   ")

    assert res["status"] == "error"
    handler.job_status.assert_not_awaited()
    assert chat.calls == []


# ---------------------------------------------------------------------------
# the announcement is best-effort; the resume is not
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_alert_channel_still_resolves_the_deferral(monkeypatch):
    """The turn is the feature; the Discord post is how it gets seen."""
    monkeypatch.setattr(global_config, "MODEL_JOB_ALERT_CHANNEL_ID", "",
                        raising=False)
    bridge, _, chat, notifier = _bridge()

    res = await bridge.handle("newmodel-abc123")

    assert res == {"status": "ok", "resumed": True, "announced": False,
                   "job_id": "newmodel-abc123", "state": "done"}
    assert len(chat.calls) == 1
    notifier.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_notification_router_does_not_crash():
    handler = SimpleNamespace(job_status=AsyncMock(
        return_value={"status": "ok", "job": _job()}))
    bridge = JobCompletionBridge(handler, _FakeChat(), None)

    res = await bridge.handle("newmodel-abc123")

    assert res["resumed"] is True
    assert res["announced"] is False


@pytest.mark.asyncio
async def test_a_failed_resume_is_reported_not_raised():
    """The only consumer is a curl in a bash script that already finished."""
    bridge, _, _, _ = _bridge(raises=RuntimeError("engine down"))

    res = await bridge.handle("newmodel-abc123")

    assert res == {"status": "error", "message": "resume turn failed",
                   "job_id": "newmodel-abc123"}


@pytest.mark.asyncio
async def test_a_failed_announcement_does_not_fail_the_resume():
    """The deferral is already settled by then — the post is the only casualty."""
    bridge, _, chat, notifier = _bridge()
    notifier.send = AsyncMock(side_effect=RuntimeError("discord down"))

    res = await bridge.handle("newmodel-abc123")

    assert res["resumed"] is True
    assert res["announced"] is False
    assert len(chat.calls) == 1
