"""The node's completion ping, turned back into the turn that asked (DP-343/345).

An install and a promotion both run detached on the pve node — `systemd-run`
owns them so a multi-GB download survives the SSH disconnect — which means that
when one *finishes*, nothing inside derpr is awake to notice. Before this, a
finished install sat on the node until a human thought to ask `install_status`
again, and a cold-tier promotion (which `set_active_model` starts and does not
wait for) stopped one step short of serving for the same reason.

Both node scripts POST the job id to derpr when a job reaches `done` or
`failed`. This module answers that POST:

    ping (job id only) → job_status over SSH → resolve the deferral → announce

**This used to be a self-contained wake path and is now a thin caller.** The job
id IS the park token: `install_model` and the cold-tier promotion declare a
`node_job` deferral when they hand the node a job, so a durable row already
holds the persona, channel, user and the tool entry to patch. Everything this
module used to own — an in-process seen-set for idempotency, three env vars
naming where to reply, a synthetic user message, a `generate_response` entry
into the turn — belongs to the DP-345 mechanism now, and each of those was a
defect in the version that owned it:

- the seen-set was lost on restart, so a ping arriving after one resolved
  nothing at all;
- the env vars named a conversation the park row already knew;
- `generate_response` persisted the whole synthetic wake message as a durable
  **user row**, under the operator's real Discord id.

Two properties are load-bearing and unchanged:

1. **The ping carries no facts.** The body is a job id; everything reported
   comes from `HuggingFaceToolHandler.job_status`, i.e. the same SSH read the
   `install_status` tool uses. A forged or replayed ping cannot assert that an
   install succeeded — at worst it costs one status read. It also cannot resolve
   anything else: `stream_resolve_deferral` refuses a token whose park is an
   approval, so a leaked token cannot be spent as a human's verdict.
2. **Nothing here raises.** A failure must not become a 500 on the node side,
   where the only consumer is a `curl` in a bash script that has already
   finished the job it was reporting on.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from config import global_config
from src.deferral_kinds import DEFERRAL_KIND_NODE_JOB
from src.generation_events import DoneEvent
from src.huggingface.handler import HuggingFaceToolHandler

if TYPE_CHECKING:
    from src.chat_system import ChatSystem
    from src.clients.notification import NotificationRouter

logger = logging.getLogger(__name__)


class JobCompletionBridge:
    """Resolves one node-job deferral when the node says its job is over.

    Everything it needs is injected: the handler (the SSH read), the ChatSystem
    (the resume) and the NotificationRouter (the announcement). Tests drive the
    whole path with fakes for all three and no node, no LLM and no Discord.
    """

    def __init__(
        self,
        handler: HuggingFaceToolHandler,
        chat_system: "ChatSystem",
        notification_router: Optional["NotificationRouter"] = None,
    ) -> None:
        self._handler = handler
        self._chat_system = chat_system
        self._notifier = notification_router

    async def handle(self, job_id: str) -> Dict[str, Any]:
        """Answer one completion ping. Returns a small dict for the HTTP route.

        The return value describes what derpr did with the ping — it is a log
        line for the node's journal, not something the node acts on.
        """
        value = str(job_id or "").strip().lower()
        if not value:
            return {"status": "error", "message": "job_id is required"}

        status = await self._handler.job_status(value)
        if status.get("status") != "ok":
            # An unreadable job is a real answer: the node says it finished, the
            # node's own status verb cannot produce the record. Say so and stop —
            # resolving a deferral with "something finished, I cannot tell you
            # what" is worse than the silence this feature replaced.
            logger.warning(
                "job completion ping for %s could not be verified: %s",
                value, status.get("message"),
            )
            return {"status": "error", "message": "job status unreadable",
                    "job_id": value}

        job = status.get("job") or {}
        state = str(job.get("state") or "")
        if state not in ("done", "failed"):
            # The node only pings on a terminal state, so this means the ping
            # overtook the job file or something else sent it. Either way there
            # is nothing to report yet.
            logger.info(
                "job completion ping for %s ignored: state=%r", value, state,
            )
            return {"status": "ignored", "reason": "job not terminal",
                    "job_id": value, "state": state}

        # The claim, the idempotency and the conversation all come off the row.
        # A retried ping (the node sends a second ~6s later) finds the park
        # already taken and yields nothing, which is why there is no seen-set.
        reply = ""
        try:
            async for event in self._chat_system.stream_resolve_deferral(
                value,
                kind=DEFERRAL_KIND_NODE_JOB,
                status=state,
                result={**job, "instruction": _instruction(job, state)},
                note=status.get("note"),
            ):
                if isinstance(event, DoneEvent):
                    reply = event.text or ""
        except Exception:  # noqa: BLE001 — a failed turn must not 500 the node
            logger.exception("resume turn failed for job %s", value)
            return {"status": "error", "message": "resume turn failed",
                    "job_id": value}

        if not reply:
            # Nothing pending under this id: already settled, expired, or a job
            # started before the deferral existed. Not an error — the node did
            # its part, and the status read above still happened.
            logger.info(
                "job %s finished (%s) but no deferral was waiting on it",
                value, state,
            )
            return {"status": "ok", "resumed": False, "job_id": value,
                    "state": state}

        announced = await self._announce(reply)
        return {"status": "ok", "resumed": True, "announced": announced,
                "job_id": value, "state": state}

    async def _announce(self, reply: str) -> bool:
        """Post the resumed turn's reply to Discord.

        Needed because this resume has no listener. An operator clicking approve
        is holding a stream open and reads the reply on the way back; a node
        POSTing a job id is not, so the events would otherwise drain into
        nothing. Posted verbatim rather than left to a tool the persona may or
        may not call — an announcement that depends on the model choosing to
        announce goes missing exactly when the install failed and the model
        judged the failure self-explanatory.
        """
        recipient = global_config.MODEL_JOB_ALERT_CHANNEL_ID
        text = (reply or "").strip()
        if not recipient or not text or self._notifier is None:
            return False
        try:
            return bool(await self._notifier.send(
                channel="discord_channel",
                recipient=recipient,
                subject="",
                body=text,
            ))
        except Exception:  # noqa: BLE001 — best effort, same as the resume
            logger.exception("job completion announcement failed")
            return False


def _instruction(job: Dict[str, Any], state: str) -> str:
    """What the resumed persona is asked to do about this outcome.

    Rides in the patched tool entry rather than in the continuation nudge, for
    the reason `DENIAL_INSTRUCTION` does: the nudge is ephemeral, so guidance
    framed only there decays one turn later, while the outcome it refers to
    lives in history for good. Same fact, same lifetime, same place.

    Split by outcome and by kind because the three cases have genuinely
    different next steps, and a single "decide and act" line left the model to
    re-derive which of them it was in.
    """
    if state == "failed":
        return _INSTRUCTION_FAILED
    kind = "promotion" if job.get("kind") == "promote" else "install"
    return _INSTRUCTION_OK[kind]


_INSTRUCTION_OK = {
    "install": (
        "This finished on the model host after your turn ended; nobody has just "
        "asked you about it. Say what landed, in one short paragraph. The unit "
        "is DISABLED and nothing is serving it. If this conversation already "
        "told you to make it active when it arrived, do that now: call "
        "set_active_model, which will park for approval, and say that you did. "
        "If it did not, do NOT swap :5001 on your own — report it and offer "
        "the swap."
    ),
    "promotion": (
        "This finished on the model host after your turn ended; nobody has just "
        "asked you about it. The weights are on the SSD, and this did NOT change "
        "what :5001 is serving. If this conversation was working towards making "
        "that model active, call set_active_model again now to finish the swap "
        "(it parks for approval) and say so. Otherwise report that the copy "
        "finished and stop."
    ),
}

_INSTRUCTION_FAILED = (
    "This failed on the model host after your turn ended; nobody has just asked "
    "you about it. Report the failure plainly, including the step and reason in "
    "the result above, and say what you would do about it. Do not retry it on "
    "your own: a repeat of the same call against the same cause spends an "
    "approval on a known failure."
)
