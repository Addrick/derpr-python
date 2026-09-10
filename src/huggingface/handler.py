"""Tool handlers for HuggingFace model provisioning (DP-265).

Four tools behind the ``huggingface`` service binding:

- ``hf_search``      (read, HF):    gguf repos matching a query.
- ``hf_files``       (read, HF):    one repo's gguf files with byte size + sha256.
- ``install_model``  (WRITE → parked): download a gguf onto the pve node and
  template a **disabled** ``koboldcpp-<name>.service`` for it.
- ``install_status`` (read, node):  poll one install job.

Every handler returns a JSON-able dict; transport, validation and Hub failures
come back as ``{"status": "error", ...}`` rather than raised, so the model gets a
message instead of a tool crash.

**The security boundary is the node-side script, not this module.** Everything
here runs one command — ``/usr/local/sbin/derpr-model-install`` — over the same
forced-command-wrapped SSH key the proxmox tools use. The alternative, letting
the model drive ``curl`` / ``systemctl`` / file writes as separate verbs, would
widen that key to arbitrary node write for the sake of a slightly simpler
handler. One verb keeps it lean *and* narrow; see ``services/pve/README.md``.

**The download does not happen inside the tool loop.** A multi-GB fetch exceeds
any sane tool timeout, so the node runs it detached under ``systemd-run`` and
derpr polls ``install_status``. Deliberately *not* a background task inside
derpr: that re-opens the DP-304 interval-loop shutdown-contract problem for a
job the node is already supervising.

Two things the model never gets to decide:

1. **What bytes land.** ``install_model`` reads the file's size and sha256 from
   the Hub itself and passes them to the node, which refuses on any mismatch.
   The same two values are what the enricher puts on the approval card, so the
   human approves a *digest*, not a repo name.
2. **Where they land.** The node script owns the models directory and the unit
   template; nothing in the arguments is a path.

One thing the model *proposes* and a human approves: the unit's **tuning**
(DP-364), a closed ``<kv>-<cache>`` token the node expands into ``--quantkv``
and the smartcache flags. It is on the approval card and written into the unit
verbatim, so the unit file states every flag the process runs with.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Dict, Optional, TYPE_CHECKING

from config import global_config
from src.huggingface.client import HFClient, HFError, validate_file_path, validate_repo_id
from src.proxmox.ssh import SSHRunner, run_node_command

if TYPE_CHECKING:
    from src.tools.tool_manager import ToolManager

from src.deferral_kinds import DEFERRAL_KIND_NODE_JOB, declare_deferral
logger = logging.getLogger(__name__)

#: The one node-side verb this whole feature is allowed to run. Absolute because
#: sshd's forced command inherits a minimal PATH.
_INSTALL_SCRIPT = "/usr/local/sbin/derpr-model-install"

#: A friendly model name → the unit stem ``koboldcpp-<name>.service``.
#: Narrower than the unit charset ``ProxmoxToolHandler._UNIT_RE`` accepts on
#: *discovery*, because this one is **minted** from a model-supplied string: a
#: name we create has to be one that discovery can later read back, and dots or
#: ``@`` in a unit stem mean something to systemd that we do not want chosen for
#: us. Matches the node script's own gate.
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,48}$")

#: A minted job id. Same charset as ``_NAME_RE`` so the node can gate both with
#: one pattern, and so the id is legal in the ``modelinstall-<id>`` unit name.
_JOB_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

#: Context the templated unit is written with when the caller names none.
#: Deliberately small. The unit lands **disabled** and a human tunes the number
#: against ``gpu_status`` before enabling it — DP-265 chose the conservative
#: fixed default over computing a budget here, on the grounds that today the
#: number is picked by hand with no check at all, so even the weak version is a
#: strict improvement.
_DEFAULT_CONTEXTSIZE = 8192
_MIN_CONTEXTSIZE = 512
_MAX_CONTEXTSIZE = 1048576

#: DP-364. ``<kv>-<cache>``: KV precision (``f16``/``q8``/``q4``) and cache
#: mode (``off``/``swap``/``grid``). A closed vocabulary rather than raw flag
#: values, so the node and the sshd wrapper gate one token with one regex and
#: the approval card shows a choice a human can read. Matches both of theirs.
#: There is no default: which cache mode a unit wants depends on how it will be
#: used, which the persona knows and the template never did.
_TUNING_RE = re.compile(r"^(f16|q8|q4)-(off|swap|grid)$")

#: Keys derpr will surface out of the node's job JSON, and how to coerce them.
#: A whitelist rather than a passthrough: it is what keeps ``install_status``'s
#: ``produces_untrusted: False`` claim *enforced* instead of merely asserted, so
#: a future node-side change that starts echoing an HTTP error body cannot
#: quietly turn a trusted read into an injection surface.
_STATUS_FIELDS: Dict[str, type] = {
    "job_id": str,
    "state": str,
    # DP-343: `derpr-model-tier` stamps "promote" here and the installer stamps
    # nothing, which is how one job document says which of the two node scripts
    # wrote it. Whitelisted rather than inferred from the other fields, because
    # "repo is empty" happening to mean "this was a promotion" is the kind of
    # inference that survives right up until the installer learns a case where
    # repo is empty too.
    "kind": str,
    "step": str,
    "reason": str,
    "repo": str,
    "file": str,
    "name": str,
    "unit": str,
    "sha256": str,
    "started": str,
    "finished": str,
    "size_bytes": int,
    "downloaded_bytes": int,
    "contextsize": int,
    # DP-364: the approved `<kv>-<cache>` token the unit was written with.
    "tuning": str,
    # DP-360: blocks holding a recurrent state instead of a KV cache. Non-zero
    # means hybrid, which is what decides whether --smartcachegrid can do
    # anything for the unit. Reported rather than inferred from an
    # architecture name, because the name of the next hybrid arch is not known.
    "ssm_layers": int,
    "n_layer": int,
    "n_kv_head": int,
    "head_dim": int,
    # DP-344. Present *instead of* the three numbers, when the node determined
    # this model's cache is not a linear function of context (per-layer KV head
    # counts, sliding-window attention). A node older than DP-344 never sends
    # it; since DP-360 that degrades to the plain measurement note, which is
    # already the right advice — the shape note only ever *added* the reason
    # the cache is non-linear. Node artifacts and the container image are two
    # independent deploys, so both ages are live at once.
    "kv_shape_note": str,
}

#: How much of any single node-supplied string is kept. A fixed-vocabulary
#: `reason` is short; a long one means the node script grew a passthrough and
#: the truncation is the backstop for that.
_MAX_STATUS_STR = 200

_GIB = 1024 ** 3


def _err(message: str) -> Dict[str, Any]:
    return {"status": "error", "message": message}


def _validate_name(name: str) -> str:
    value = str(name or "").strip().lower()
    if not _NAME_RE.match(value):
        raise HFError(
            f"invalid model name {name!r}; use lowercase letters, digits and "
            "dashes (it becomes the systemd unit stem koboldcpp-<name>.service)"
        )
    return value


def _validate_contextsize(contextsize: Any) -> int:
    if contextsize is None or contextsize == "":
        return _DEFAULT_CONTEXTSIZE
    try:
        value = int(contextsize)
    except (TypeError, ValueError):
        raise HFError(f"contextsize must be an integer, got {contextsize!r}")
    if not _MIN_CONTEXTSIZE <= value <= _MAX_CONTEXTSIZE:
        raise HFError(
            f"contextsize must be between {_MIN_CONTEXTSIZE} and "
            f"{_MAX_CONTEXTSIZE}, got {value}"
        )
    return value


def _validate_tuning(tuning: Any) -> str:
    value = str(tuning or "").strip().lower()
    if not _TUNING_RE.match(value):
        raise HFError(
            f"invalid tuning {tuning!r}; use <kv>-<cache> with kv one of "
            "f16, q8, q4 and cache one of off, swap, grid (e.g. q8-swap)"
        )
    return value


class HuggingFaceToolHandler:
    """Owns the Hub client and shares the proxmox SSH transport.

    Both are injectable so tests drive the whole feature with no network and no
    node: a fake client returns canned Hub metadata, a fake runner records the
    single argv that crosses the SSH boundary.
    """

    def __init__(
        self,
        client: Optional[HFClient] = None,
        runner: Optional[SSHRunner] = None,
    ) -> None:
        self._hf = client or HFClient()
        self._ssh = runner or SSHRunner()

    def register(self, manager: "ToolManager") -> None:
        manager.register("hf_search", self._hf_search)
        manager.register("hf_files", self._hf_files)
        # The enricher is what puts repo / file / byte size / sha256 on the
        # approval card. Without it the card would show only what the model
        # typed, and the human would be approving a name rather than bytes.
        manager.register(
            "install_model", self._install_model, self._enrich_install_model
        )
        manager.register("install_status", self.job_status)

    # -- guards --------------------------------------------------------------

    @staticmethod
    def _enabled() -> bool:
        return bool(global_config.HF_TOOLS_ENABLED)

    @staticmethod
    def _disabled_error() -> Dict[str, Any]:
        return _err(
            "HuggingFace model tools are disabled (set HF_TOOLS_ENABLED=true and "
            "deploy services/pve/derpr-model-install on the node to enable)."
        )

    async def _run(self, argv: list[str]) -> Dict[str, Any]:
        """Run the one node-side verb through the shared node gate (DP-348).

        This used to be a second, independent implementation of
        ``ProxmoxToolHandler._run``, and the two had drifted in the two ways that
        mattered: it checked no ``PVE_TOOLS_ENABLED``, so ``install_model``
        shelled out to the box while every proxmox tool correctly reported itself
        disabled; and it held no in-flight cap, so HF connections were invisible
        to the limit that exists to keep the node under sshd's MaxStartups.
        Both are properties of the key and the box, not of a handler, so both now
        live behind ``ssh.run_node_command``.

        ``HF_TOOLS_ENABLED`` stays where it is — it is the *feature* switch for
        these four tools, checked per tool before any argv is built. The gate is
        the *transport* switch.
        """
        return await run_node_command(self._ssh, argv, exit_label="node script")

    # -- read tools ----------------------------------------------------------

    async def _hf_search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        logger.info("Tool hf_search: %r limit=%s", query, limit)
        if not self._enabled():
            return self._disabled_error()
        try:
            capped = max(1, min(int(limit), global_config.HF_SEARCH_LIMIT_MAX))
        except (TypeError, ValueError):
            # The fallback goes through the ceiling too. A model that emits
            # limit="ten" must not end up with a bigger page than the operator's
            # configured maximum allows — that is the one case where a garbage
            # argument would buy more untrusted text than a valid one.
            capped = max(1, min(10, global_config.HF_SEARCH_LIMIT_MAX))
        try:
            models = await self._hf.search_models(query, capped)
        except HFError as e:
            return _err(str(e))
        return {
            "status": "ok",
            "query": query,
            "models": models,
            # DP-335: the filter is the whole answer to "why isn't the model I
            # asked for here", and until this note existed the payload said it
            # nowhere. `hf_files` had carried a note since DP-265 precisely so
            # an empty list would not be misread; `hf_search` — the tool whose
            # empty result is *structurally* unfixable by re-querying — had
            # none, so a zero-hit search read as "wrong spelling, try again"
            # and a live turn spent its whole budget re-spelling one name
            # against a filter that could never yield it.
            "note": (
                "Results are restricted to repos tagged `gguf`, the only "
                "format install_model can install. A publisher that ships "
                "only safetensors — which is most official/upstream model "
                "repos — will NEVER appear here, however the query is "
                "spelled. The community quant repos ARE the installable form "
                "of those weights: match one to an upstream model by its "
                "`base_model:<owner>/<name>` tag. Zero hits means broaden the "
                "query (drop the version suffix, the parameter count, the "
                "org) or accept that only a converted repo can satisfy it; "
                "re-spelling the same name does not change the filter."
            ),
        }

    async def _hf_files(self, repo: str) -> Dict[str, Any]:
        logger.info("Tool hf_files: %s", repo)
        if not self._enabled():
            return self._disabled_error()
        try:
            files, truncated = await self._hf.list_gguf_files(validate_repo_id(repo))
        except HFError as e:
            return _err(str(e))
        # Capped for the same reason hf_search is, and over the same kind of
        # text: every row is a path and a digest chosen by whoever uploaded the
        # repo, and a repo publishing every quant of a sharded model is several
        # thousand tokens of third-party text in one tool result.
        cap = max(1, global_config.HF_FILES_LIMIT_MAX)
        elided = max(0, len(files) - cap)
        # Said out loud rather than left to inference, in both directions: a
        # repo with no gguf is a normal answer and must not read as "the read
        # failed", and an incomplete listing must never read as a complete one.
        notes = [
            "Sizes are bytes as HuggingFace reports them. A file with "
            "sha256: null cannot be installed — install_model refuses "
            "anything it cannot pin to a digest."
        ]
        if elided:
            notes.append(
                f"{elided} further gguf file(s) were elided at the "
                f"HF_FILES_LIMIT_MAX cap of {cap}, so this list is INCOMPLETE."
            )
        if truncated:
            notes.append(
                "The repo's file tree is larger than this listing walked, so "
                "this list is INCOMPLETE — a file missing from it may still "
                "exist. Do not report a file as absent on the strength of it."
            )
        return {
            "status": "ok",
            "repo": repo,
            "files": [f.to_dict() for f in files[:cap]],
            "truncated": bool(truncated or elided),
            "note": " ".join(notes),
        }

    async def job_status(self, job_id: str) -> Dict[str, Any]:
        """One job's verified state — the `install_status` tool, and the read
        the DP-343 completion callback answers a node ping with.

        Public because it has a second caller that is not the tool loop:
        `completion.JobCompletionBridge` re-reads the job here rather than
        trusting the POST body, so a ping is a doorbell and the facts still come
        from the SSH transport derpr already trusts. Promote jobs
        (`derpr-model-tier`) write into the same JOBS_DIR under the same schema,
        so this reads both kinds.
        """
        logger.info("Tool install_status: %s", job_id)
        if not self._enabled():
            return self._disabled_error()
        value = str(job_id or "").strip().lower()
        if not _JOB_ID_RE.match(value):
            return _err(f"invalid job_id {job_id!r}")
        res = await self._run([_INSTALL_SCRIPT, "status", value])
        if res.get("status") != "ok":
            return res
        try:
            payload = json.loads(res.get("stdout") or "")
        except json.JSONDecodeError:
            return _err(
                f"job {value} returned no readable status; the job file may not "
                "exist yet (a just-started job writes it within a second or two)"
            )
        if not isinstance(payload, dict):
            return _err(f"job {value} returned a non-object status")
        job = _clean_status(payload)
        result: Dict[str, Any] = {"status": "ok", "job": job}
        note = _kv_measurement_note(job)
        if note:
            result["note"] = note
        return result

    # -- write tool (parked for confirmation) --------------------------------

    async def _enrich_install_model(self, **kwargs: Any) -> Optional[str]:
        """The one line a human reads before approving an install.

        Returns HF's *own* size and digest for the file, not the model's account
        of them. Failures are returned as loud text rather than raised: the
        ToolManager turns an enricher exception into ``None``, which would
        render a card that looks ordinary while having verified nothing.
        """
        repo = str(kwargs.get("repo") or "")
        file_path = str(kwargs.get("file") or "")
        # DP-364: the tuning is the one model-proposed setting the unit gets,
        # so the card shows it -- and says so when it is not one the node will
        # accept, rather than letting an approval fail after the fact.
        try:
            tuning = f"tuning {_validate_tuning(kwargs.get('tuning'))}"
        except HFError:
            tuning = f"⚠️ INVALID tuning {kwargs.get('tuning')!r} — will be refused"
        try:
            entry = await self._hf.find_gguf_file(
                validate_repo_id(repo), validate_file_path(file_path)
            )
        except HFError as e:
            return f"⚠️ UNVERIFIED — HuggingFace lookup failed: {e} · {tuning}"
        gib = entry.size_bytes / _GIB
        return (
            f"{repo}/{entry.path} · {entry.size_bytes} bytes ({gib:.2f} GiB) · "
            f"sha256 {entry.sha256} · {tuning}"
        )

    async def _install_model(
        self,
        repo: str,
        file: str,
        name: str,
        contextsize: Optional[int] = None,
        tuning: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Provision a gguf so it *becomes* a valid ``set_active_model`` target.

        Runs after a human approved the park. The Hub is re-read here rather
        than trusting the enricher's values, because the enricher's result is
        display text, not state — but that also means the digest enforced can
        differ from the digest approved if the repo changed in between. The
        returned ``sha256`` is the one actually enforced, so a swap between park
        and execution is visible in the tool result rather than silent.
        """
        logger.info(
            "Tool install_model: repo=%s file=%s name=%s ctx=%s tuning=%s",
            repo, file, name, contextsize, tuning,
        )
        if not self._enabled():
            return self._disabled_error()
        try:
            repo_id = validate_repo_id(repo)
            file_path = validate_file_path(file)
            unit_name = _validate_name(name)
            ctx = _validate_contextsize(contextsize)
            unit_tuning = _validate_tuning(tuning)
            entry = await self._hf.find_gguf_file(repo_id, file_path)
        except HFError as e:
            return _err(str(e))

        job_id = f"{unit_name}-{uuid.uuid4().hex[:12]}"
        res = await self._run([
            _INSTALL_SCRIPT, "install",
            repo_id, entry.path, unit_name, str(ctx),
            str(entry.size_bytes), str(entry.sha256), job_id, unit_tuning,
        ])
        if res.get("status") != "ok":
            return res
        # DP-345: the node owns this job now and it outlives the call. Declaring
        # the deferral re-parks this executed write under `job_id`, so the
        # node's completion ping resolves it in the conversation that asked —
        # no configuration names a persona, channel or user anywhere.
        return declare_deferral({
            "status": "ok",
            "job_id": job_id,
            "repo": repo_id,
            "file": entry.path,
            "name": unit_name,
            "unit": f"koboldcpp-{unit_name}.service",
            "contextsize": ctx,
            "tuning": unit_tuning,
            "size_bytes": entry.size_bytes,
            "sha256": entry.sha256,
            "state": "running",
            # Both halves matter to the model: the download is not finished when
            # this returns, and the unit will not be serving anything even when
            # it is. Saying so here is what stops "installed" being reported as
            # "active".
            "note": (
                "Download started on the node and continues after this call "
                f"returns — poll install_status(job_id='{job_id}'). The unit is "
                "written DISABLED: it will not start and will not take :5001. "
                "Putting it on :5001 is a separate, separately-approved "
                "set_active_model call, and the contextsize should be checked "
                "against gpu_status first."
            ),
        }, DEFERRAL_KIND_NODE_JOB, job_id)


def _kv_measurement_note(job: Dict[str, Any]) -> Optional[str]:
    """Point a finished install at the measurement instead of at an estimate.

    DP-360 deleted the arithmetic this used to do, and the deletion is the fix
    rather than a retreat from one.

    The formula was never wrong. ``2 x n_layer x n_kv_head x head_dim`` is
    right, and the node reads all three terms off the tensor index precisely
    because a hybrid architecture's block count is not its cached-layer count.
    What could not be sourced at the time was the fourth term: bytes per
    element is set by ``--quantkv``, and CT101's policy wrapper substituted that
    per model at exec. DP-364 removed the wrapper -- the approved tuning is now
    written into the unit, so the unit file does settle it -- and the deletion
    still stands, on the ground below alone.

    DP-344 is why this is a deletion and not a repair. The estimate returned
    the right total for Qwen3.8 only because a layer count one too high and a
    bytes-per-element one too low cancelled exactly. One matching measurement
    cannot pin a product of two unknowns, and a wrong total is worse here than
    no total, because it reaches a human already in the shape of arithmetic.

    The header shape still ships in the job status. It is read off the file,
    not derived, and it is useful. What is gone is the multiplication.

    Installs only. ``job_status`` reads promote jobs (``derpr-model-tier``) out
    of the same JOBS_DIR under the same schema, and a promotion creates no
    unit, sets no contextsize and reads no header -- it copies weights to the
    SSD. Telling its operator to "read gpu_status before the unit is first
    enabled" describes a decision that was made when the unit was installed,
    about a unit that is usually already serving, and `completion.py` posts
    this straight to Discord. Same branch `_instruction` takes.
    """
    if job.get("state") != "done" or job.get("kind") == "promote":
        return None
    note = (
        "Size this unit's contextsize by measurement, not by arithmetic: read "
        "gpu_status before the unit is first enabled and again after, and "
        "trust that difference. Do not multiply the header shape in this "
        "status into a VRAM figure -- a total assembled from header terms has "
        "matched a real measurement on this box only by two errors "
        "cancelling, and the compute buffers beside the cache do not follow "
        "the header at all. Overshooting into GTT is recoverable and "
        "sometimes fine; a confident wrong total is neither."
    )
    # The node's own refusal is strictly better information than the generic
    # advice above, because it names the property that breaks the linearity.
    shape_note = job.get("kv_shape_note")
    if isinstance(shape_note, str) and shape_note.strip():
        note += (
            " The node adds that this model's cache is not a linear function "
            f"of contextsize at all: {shape_note.strip()}."
        )
    return note


def _clean_status(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Whitelist + coerce the node's job JSON into the shape derpr publishes."""
    out: Dict[str, Any] = {}
    for key, kind in _STATUS_FIELDS.items():
        if key not in payload:
            continue
        raw = payload[key]
        if kind is int:
            try:
                out[key] = int(raw)
            except (TypeError, ValueError):
                continue
        else:
            out[key] = str(raw)[:_MAX_STATUS_STR]
    return out
