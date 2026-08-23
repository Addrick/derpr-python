# src/deferral_kinds.py
"""The vocabulary of *deferred tool results* (DP-345).

A **deferral** is one tool call whose real result arrives after the turn that
made it has ended. Nothing hangs: the turn completes with a placeholder tool
result, a durable row binds the pending call to that turn's own coordinates, and
whatever external event finally answers it patches the placeholder and runs one
continuation turn.

`kind` is the axis that names *which* external event does the answering. Its
whole reason to exist is discoverability, so it lives in its own leaf module
rather than beside either consumer:

- `src.tools.tool_loop` writes the placeholder and may not import
  `src.memory.memory_manager` (module-boundary contract);
- `src.memory.memory_manager` stores the row and may not import `src.tools`;
- so a constant both of them need has nowhere else to live that does not
  duplicate it — and a *duplicated* constant whose two copies must stay byte
  equal (the `Parked_Writes.kind` DDL default has to match what the store
  writes) is exactly the failure this ticket was filed about.

The rule a new kind must keep, stated once, here, because it is the rule two
subsystems already broke:

    **The coordinates of a resume come from the turn, never from config.**

`ParkedWrite` carries `user_identifier`, `persona_name`, `channel` and
`server_id`, taken from the turn that raised the deferral. A kind that has to be
*told* which persona or channel to answer in has discarded state it was already
handed — that is what `MODEL_JOB_WAKE_PERSONA`, `MODEL_JOB_WAKE_CHANNEL`,
`MODEL_JOB_WAKE_USER`, `CC_FIXR_PERSONA` and `CC_FIXR_CHANNEL` were, and why
DP-345 deletes rather than generalizes them.
"""

# A human clicking approve/deny. The original kind. Every kind is addressed by
# TOKEN, including the ones answered by an outside authority: derpr mints the
# park token and hands that same string outward as the job id, so there is no
# second namespace to map back from. Same rule as the coordinates above — a
# kind that has to be handed an identifier the parking call already had is
# discarding state it was given.
#
# Also the value of the `Parked_Writes.kind` DDL default, which is what makes
# the migration a no-op for rows written before the column existed: every one
# of them was an approval.
DEFERRAL_KIND_APPROVAL = "approval"

__all__ = ["DEFERRAL_KIND_APPROVAL"]
