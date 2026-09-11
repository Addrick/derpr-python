#!/usr/bin/env python3
"""Read a gguf's *measured* cache shape out of its header (DP-265).

Deployed to the Proxmox node beside ``derpr-model-install``, which calls it after
a download verifies and folds the output into the job status.

⚠️ **This module reports what the file says; it does not size anything.** It was
built to feed

    KV_bytes_per_token = 2 · n_layer · n_kv_head · head_dim · bytes_per_elem

and **DP-360 deleted that evaluation**: a total built from it matched a real
measurement only because two errors cancelled (DP-344). (``bytes_per_elem`` was
also unsourceable then, while CT101's policy wrapper rewrote ``--quantkv`` at
exec; DP-364 removed the wrapper.) The three numbers below still ship, because they are
*read off the file* rather than derived and the cached-layer count is available
nowhere else; what is gone is the multiplication. The caller's answer to "how big
a context fits" is now a measurement: ``gpu_status`` either side of first
enabling the unit.

⚠️ **``n_layer`` is the count of layers that actually cache K/V, which is NOT
``block_count`` on every architecture** (DP-344). Getting that wrong is worse
than having no number: it is reported to a human as a fact about the file, and a
wrong fact about the file survives the deletion of the arithmetic that once
consumed it. Two ways the header lies to a naive reader, both measured on models
this node serves:

- **Hybrid (Gated DeltaNet) archs** — ``qwen35``, ``qwen35moe`` — interleave
  attention blocks with SSM blocks that hold a *fixed* recurrent state and cache
  nothing per token. Qwen3.8-27B is 65 blocks of which **17** attend; using 65
  overstates the cache 3.8× and cost a live answer of "32k is the maximum
  context" for a model that fits 262144.
- **Per-layer attention shapes** — ``gemma4`` publishes
  ``attention.head_count_kv`` as a **list** (16 on sliding-window layers, 4 on
  full-attention ones) and a 1024-token ``attention.sliding_window``. There is no
  single ``n_kv_head``, and 50 of its 60 layers stop growing at the window, so a
  linear formula does not describe this model at any head count. Such a model is
  **refused** with a reason rather than estimated.
- **MTP draft blocks** carry a real ``attn_k`` and are still not cached, because
  koboldcpp only runs them under ``--usemtp`` (ROCm-only, and no unit here passes
  it). Qwen3.8-27B has 17 blocks with a K projection and kcpp allocates KV for
  **16**; block 64 is its ``nextn`` block.

So the layer count comes from the **tensor index** — the blocks carrying a K
projection, less the draft blocks — and not from a metadata integer that means
something else. Validated to the byte against koboldcpp's own
``llama_kv_cache: KV buffer size`` on two models: Qwen3.8-27B (16 layers,
34816 B/token at 262400 ctx) and Deckard-40B (24 layers, 52224 B/token at
16640 ctx).

Stdlib only, and it reads the header and the tensor index, never the tensor
*data* — a 30 GB file costs a few hundred KB of I/O here.

Output is a **JSON fragment**, not a document, and its well-formedness is this
module's responsibility rather than the caller's — ``fragment`` parses what it
built before returning it, so the bash caller needs no grammar of its own::

    ,"n_layer":48,"n_kv_head":8,"head_dim":128,"ssm_layers":0

or, when the model's cache cannot be described by the formula::

    ,"kv_shape_note":"per-layer attention.head_count_kv ...","ssm_layers":0

``ssm_layers`` is the count of blocks holding a recurrent state instead of a KV
cache, and it rides on both shapes because it answers a different question
(DP-360). Non-zero means hybrid, which is what decides whether
``--smartcachegrid`` can do anything for a unit; the same walk yields it, so it
costs nothing to report.

That shape is deliberate: the caller is a bash script on a node with no ``jq``,
and it appends this straight into the status object it is already printf-ing.
A file it cannot parse produces **no output and exit 0** — a header quirk must
never fail an install whose bytes verified.

⚠️ The exit status is the caller's whole gate (DP-360). ``0`` means "stdout is a
complete fragment, possibly empty"; anything else means this process died before
it could say that, and the caller must discard whatever it captured. The caller
used to pattern-match the output instead, which re-derived the grammar above in
shell and got it wrong twice — first accepting only ``,"n_layer"`` and silently
discarding every refusal note, then accepting any leading key and with it a
truncated write. Keep the contract here, where the grammar is.
"""

from __future__ import annotations

import json
import struct
import sys
from typing import Any, BinaryIO, Dict, List, NamedTuple, Optional, Set

_MAGIC = b"GGUF"

# GGUF metadata value type ids → struct format for the scalar ones.
_SCALAR = {
    0: "<B",   # uint8
    1: "<b",   # int8
    2: "<H",   # uint16
    3: "<h",   # int16
    4: "<I",   # uint32
    5: "<i",   # int32
    6: "<f",   # float32
    7: "<?",   # bool
    10: "<Q",  # uint64
    11: "<q",  # int64
    12: "<d",  # float64
}
_STRING = 8
_ARRAY = 9

#: Refuse absurd lengths rather than trying to allocate them. A corrupt or
#: hostile header is the case this guards; the largest legitimate gguf string
#: (a chat template) is comfortably under this.
_MAX_LEN = 64 * 1024 * 1024
_MAX_KV = 100_000
#: Same guard for the tensor index. The largest model here has 866 tensors.
_MAX_TENSORS = 1_000_000

#: Cap on an array's ELEMENT COUNT, which is a different quantity from
#: ``_MAX_LEN``'s bytes and needs its own, much smaller, bound (DP-349).
#: Bounding a count with the byte cap let a header declaring 60 million elements
#: enter a 60-million-pass read loop, and because a real gguf has tens of GB of
#: tensor data behind the header those reads keep succeeding on garbage instead
#: of hitting the truncated-file exit — so the install hung for minutes with its
#: status frozen rather than failing. The largest legitimate array is a tokenizer
#: vocabulary (~250k on today's big models), so 4M is generous by more than an
#: order of magnitude.
_MAX_ARRAY = 4_000_000

#: The tensor that proves a block caches K. A block without one contributes
#: nothing per token, whatever `block_count` says it is.
_K_TENSOR = "attn_k.weight"
#: Fused-QKV architectures publish no separate `attn_k`; K lives inside this.
#: Checked only when no block has a separate K projection — on the hybrid archs
#: `attn_qkv.weight` is what the *SSM* blocks carry, so preferring it there
#: would reintroduce exactly the overcount this module exists to avoid.
_QKV_TENSOR = "attn_qkv.weight"
#: The tensor that proves a block holds a *recurrent* state instead of a KV
#: cache. Counting it is what makes hybrid-ness an observation rather than an
#: architecture-name lookup: `qwen35` and `qwen35moe` are hybrid today, the
#: next one will not be called either, and a name table is a thing that goes
#: stale silently (DP-360).
#:
#: Counted here rather than read from the `<arch>.ssm.*` metadata keys, which
#: would also answer yes/no more cheaply. Those keys give the SSM's *shape* and
#: not how many blocks carry it, and the count is the part that matters: it is
#: what says 49 of Qwen3.8-27B's 65 blocks cache nothing per token, which is
#: the same fact `attn_layers` exists to establish, arrived at independently.
#: All three kinds come off one pass, which makes
#: `attn + ssm + nextn == block_count` a free check on the walk — a walk that
#: does not add up is one to distrust. It is not enforced here, because the
#: recognised-nothing fallback legitimately fails it (0 + 0 + 0 against a real
#: block_count) and refusing that model would trade a safe overstatement for
#: silence. `Header.nextn_layers` exists so the check can be made by whoever
#: has the metadata; `tests/services/test_gguf_header.py` makes it on every
#: fixture whose naming this module claims to recognise.
_SSM_TENSOR = "ssm_conv1d.weight"
#: Prefix of the multi-token-prediction draft block's tensors. Such a block has
#: a real K projection and is still **not cached**: koboldcpp only runs MTP with
#: ``--usemtp``, which needs ROCm, and no unit ``install_model`` writes passes
#: it. Measured — Qwen3.8-27B has 17 blocks with `attn_k` and kcpp allocates KV
#: for 16 of them; block 64 is the nextn block.
#: ⚠️ If a unit here ever enables MTP, the draft block caches too and this
#: exclusion under-counts. Under-counting is the direction that overcommits
#: VRAM, so revisit this the moment `--usemtp` becomes reachable.
_NEXTN_PREFIX = "nextn."


class _Bad(Exception):
    """The file is not a gguf we can read. Always handled, never propagated."""


class ArrayValue(NamedTuple):
    """Marker for a metadata key whose value is an array.

    The elements are consumed and thrown away — materialising a 150k-entry
    tokenizer vocabulary is the one way a header read could become expensive —
    but the *key* must still be recorded. An array that read back as ``None``
    was indistinguishable from an absent key, and that is precisely what let
    ``head_count_kv or head_count`` silently substitute gemma4's **query** head
    count (32) for its per-layer KV head counts (16/4).
    """

    # NOT `count`: NamedTuple fields shadow tuple methods, and `tuple.count`
    # is one. mypy rejects it outright, which is the good outcome — a silent
    # shadow would break `.count()` for any caller that expected a tuple.
    length: int
    elem_type: int


class Header(NamedTuple):
    """What one pass over a gguf's header yields."""

    #: Every metadata key. Array values are ``ArrayValue`` markers.
    meta: Dict[str, Any]
    #: Blocks carrying a K projection, or None if the tensor index was
    #: unreadable. ``0`` means the index read fine and named no such tensor.
    attn_layers: Optional[int]
    #: Blocks carrying an SSM convolution. ``0`` on a pure attention model,
    #: non-zero is what "hybrid" means concretely, and None means the walk
    #: could not establish either — an unreadable index, or one that named no
    #: block tensor at all.
    ssm_layers: Optional[int]
    #: Blocks excluded as MTP draft layers. Not published to the model; it is
    #: here so ``attn + ssm + nextn == block_count`` — the partition this walk
    #: claims to compute — can actually be checked against the metadata.
    nextn_layers: int = 0


def _read(fh: BinaryIO, size: int) -> bytes:
    if size < 0 or size > _MAX_LEN:
        raise _Bad(f"implausible length {size}")
    data = fh.read(size)
    if len(data) != size:
        raise _Bad("truncated header")
    return data


def _scalar(fh: BinaryIO, type_id: int) -> Any:
    fmt = _SCALAR.get(type_id)
    if fmt is None:
        raise _Bad(f"unknown value type {type_id}")
    return struct.unpack(fmt, _read(fh, struct.calcsize(fmt)))[0]


def _string(fh: BinaryIO) -> str:
    (length,) = struct.unpack("<Q", _read(fh, 8))
    return _read(fh, length).decode("utf-8", "replace")


def _value(fh: BinaryIO, type_id: int) -> Any:
    """One metadata value. Arrays are consumed and reduced to a marker."""
    if type_id == _STRING:
        return _string(fh)
    if type_id == _ARRAY:
        (elem_type,) = struct.unpack("<I", _read(fh, 4))
        (count,) = struct.unpack("<Q", _read(fh, 8))
        # _MAX_ARRAY, not _MAX_LEN: this is a count of elements, not a count of
        # bytes, and the two differ by whatever an element costs.
        if count > _MAX_ARRAY:
            raise _Bad(f"implausible array count {count}")
        for _ in range(count):
            _value(fh, elem_type)
        return ArrayValue(length=count, elem_type=elem_type)
    return _scalar(fh, type_id)


def _index_entry(fh: BinaryIO) -> Optional["tuple[str, str]"]:
    """Consume one tensor-index entry; return ``(block index, suffix)`` or None.

    The consuming is the point and happens on every path, including the two
    that return None: the index is a packed stream with no entry lengths, so a
    caller that skipped the fixed-size tail of an uninteresting tensor would
    resume mid-entry and read subsequent names out of dimension bytes.
    """
    name = _string(fh)
    (n_dims,) = struct.unpack("<I", _read(fh, 4))
    if n_dims > 8:
        raise _Bad(f"implausible tensor rank {n_dims}")
    _read(fh, 8 * n_dims)          # dims
    _read(fh, 4)                   # ggml type
    _read(fh, 8)                   # offset
    if not name.startswith("blk."):
        return None
    parts = name.split(".", 2)
    if len(parts) != 3:
        return None
    return parts[1], parts[2]


def _block_kinds(
    fh: BinaryIO, tensor_count: int
) -> "tuple[int, Optional[int], int]":
    """``(attention, SSM, draft)`` block counts, all off one index walk.

    Counting distinct block indices rather than tensors is deliberate: a block
    is either cached or it is not, and a future arch that splits K across two
    tensors must not count twice.

    The SSM and draft counts ride along on the pass that was already happening.
    Reading the index twice for them would double the I/O to learn something
    this walk passes over anyway — and having all three off one walk is what
    makes ``attn + ssm + nextn == block_count`` checkable by the caller.

    The SSM count is ``None`` when the walk named no block tensor at all, which
    is a different claim from zero; see the guard below.
    """
    if tensor_count > _MAX_TENSORS:
        raise _Bad(f"implausible tensor count {tensor_count}")
    # One set per thing a block index can prove about itself. Kept as sets of
    # the index string so a block that carries two interesting tensors lands in
    # both without either being counted twice.
    seen: Dict[str, Set[str]] = {
        _K_TENSOR: set(), _QKV_TENSOR: set(), _SSM_TENSOR: set(),
        _NEXTN_PREFIX: set(),
    }
    for _ in range(tensor_count):
        entry = _index_entry(fh)
        if entry is None:
            continue
        index, suffix = entry
        if suffix.startswith(_NEXTN_PREFIX):
            seen[_NEXTN_PREFIX].add(index)
        elif suffix in seen:
            seen[suffix].add(index)
    if not any(seen.values()):
        # The walk completed and named no block tensor of any kind. That is
        # "unknown", not "zero of each" — an unfamiliar naming convention, an
        # index of nothing but output tensors. Reporting 0 SSM blocks off an
        # index that named none at all is the confident-answer-with-nothing-
        # behind-it failure this module exists to avoid, so the count is
        # withheld the same way an unwalkable index withholds it. The
        # attention count still degrades to 0, which makes `kv_shape` fall
        # back to `block_count` — overstating the cache, the safe direction.
        return 0, None, 0
    nextn_blocks = seen[_NEXTN_PREFIX]
    # Every candidate set is narrowed BEFORE any of them is tested, so the set
    # that decides the branch is the set that gets counted. Testing the raw
    # `attn_k` set and counting the narrowed one disagreed for a model whose
    # only K projection lives on the draft block: the branch was taken and
    # returned 0.
    #
    # An SSM block is never also a draft block, but subtract anyway: the
    # exclusion is about what koboldcpp runs, and the two sets are maintained
    # by different upstreams.
    ssm_blocks = seen[_SSM_TENSOR] - nextn_blocks
    k_blocks = seen[_K_TENSOR] - nextn_blocks
    # ⚠️ The fused set loses the SSM blocks too, and that subtraction is the
    # whole reason this is a fallback rather than a preference. On the hybrid
    # archs `attn_qkv.weight` is what the *recurrent* blocks carry, so a hybrid
    # whose attention blocks are ALSO fused — no separate `attn_k` anywhere —
    # reaches this line with every block in `qkv_blocks`. Counting them all is
    # the DP-344 overcount arriving by a second route, and the corrective set
    # is already in hand.
    qkv_blocks = seen[_QKV_TENSOR] - nextn_blocks - ssm_blocks
    ssm = len(ssm_blocks)
    nextn = len(nextn_blocks)
    if k_blocks:
        return len(k_blocks), ssm, nextn
    return len(qkv_blocks), ssm, nextn


def read_header(path: str) -> Header:
    """Metadata plus the block-kind counts. Raises ``_Bad`` on garbage.

    The tensor index is best-effort *within* an otherwise good file: a header
    whose metadata parsed but whose index did not still yields a usable
    ``n_kv_head``/``head_dim``, and ``kv_shape`` falls back to ``block_count``
    for the layer count rather than discarding the two numbers that did read.
    """
    with open(path, "rb") as fh:
        if _read(fh, 4) != _MAGIC:
            raise _Bad("not a gguf file")
        struct.unpack("<I", _read(fh, 4))  # version
        (tensor_count,) = struct.unpack("<Q", _read(fh, 8))
        (kv_count,) = struct.unpack("<Q", _read(fh, 8))
        if kv_count > _MAX_KV:
            raise _Bad(f"implausible metadata count {kv_count}")
        meta: Dict[str, Any] = {}
        for _ in range(kv_count):
            key = _string(fh)
            (type_id,) = struct.unpack("<I", _read(fh, 4))
            value = _value(fh, type_id)
            if value is not None:
                meta[key] = value
        attn_layers: Optional[int]
        ssm_layers: Optional[int]
        nextn_layers = 0
        try:
            attn_layers, ssm_layers, nextn_layers = _block_kinds(
                fh, tensor_count
            )
        except (_Bad, struct.error, UnicodeDecodeError):
            attn_layers = ssm_layers = None
    return Header(
        meta=meta,
        attn_layers=attn_layers,
        ssm_layers=ssm_layers,
        nextn_layers=nextn_layers,
    )


def read_metadata(path: str) -> Dict[str, Any]:
    """Every metadata key in the gguf header. Raises ``_Bad`` on garbage."""
    return read_header(path).meta


def _arch_get(meta: Dict[str, Any], suffix: str) -> Any:
    arch = meta.get("general.architecture")
    if not isinstance(arch, str) or not arch:
        return None
    return meta.get(f"{arch}.{suffix}")


def _num(meta: Dict[str, Any], suffix: str) -> Optional[int]:
    value = _arch_get(meta, suffix)
    # bool is an int subclass and would sail through; no count is ever a bool.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def kv_shape_note(meta: Dict[str, Any]) -> Optional[str]:
    """Why this model's KV cache is not a linear function of context, or None.

    Returned instead of numbers, never beside them. A refusal with a reason is
    strictly better than a confident wrong estimate: the caller's fallback is
    "measure it", which is correct for exactly these models.
    """
    if not isinstance(meta.get("general.architecture"), str):
        return None
    if isinstance(_arch_get(meta, "attention.head_count_kv"), ArrayValue):
        return (
            "this model publishes attention.head_count_kv per layer, so it has "
            "no single KV head count and its cache is not a linear function of "
            "context; size the contextsize by measurement instead"
        )
    if _num(meta, "attention.sliding_window"):
        return (
            "this model uses sliding-window attention, so its cache stops "
            "growing at the window rather than scaling with contextsize; size "
            "the contextsize by measurement instead"
        )
    return None


def kv_shape(
    meta: Dict[str, Any], attn_layers: Optional[int] = None
) -> Optional[Dict[str, int]]:
    """``n_layer`` / ``n_kv_head`` / ``head_dim``, or None if not applicable.

    ``n_layer`` is the number of layers that **cache K/V**. It comes from
    ``attn_layers`` (counted off the tensor index) when that is available and
    non-zero, and falls back to ``block_count`` only when the index named no
    attention tensor at all — an unfamiliar naming convention, where
    overstating the cache is the safe direction because it under-sizes the
    context rather than overcommitting VRAM.

    All metadata keys are namespaced by the architecture (``qwen3.block_count``),
    so the arch is read first. ``head_dim`` is taken from
    ``attention.key_length`` when the model publishes it — several architectures
    use a head dim that is *not* ``embedding_length / head_count``, and deriving
    it there would understate the KV cache on exactly those models.
    """
    arch = meta.get("general.architecture")
    if not isinstance(arch, str) or not arch:
        return None
    if kv_shape_note(meta) is not None:
        return None

    if attn_layers:
        n_layer: Optional[int] = attn_layers
    else:
        n_layer = _num(meta, "block_count")
    # Only fall back to the query head count when head_count_kv is genuinely
    # ABSENT (an MHA model, where they are equal). A present-but-non-scalar one
    # was refused above and must never reach this `or`.
    n_kv_head = (
        _num(meta, "attention.head_count_kv")
        or _num(meta, "attention.head_count")
    )
    head_dim = _num(meta, "attention.key_length")
    if head_dim is None:
        embedding = _num(meta, "embedding_length")
        heads = _num(meta, "attention.head_count")
        if embedding and heads:
            head_dim = embedding // heads
    if not (n_layer and n_kv_head and head_dim):
        return None
    return {"n_layer": n_layer, "n_kv_head": n_kv_head, "head_dim": head_dim}


def _json_str(text: str) -> str:
    """Minimal JSON string escaping — these notes are ours, not user input."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def fragment(path: str) -> str:
    """The JSON fragment for ``path``, or an empty string if unreadable.

    ``ssm_layers`` is appended rather than prepended, and that placement is
    load-bearing for one deploy shape only: an installer OLDER than DP-360 still
    gates on the leading key, and a node whose artifacts are older than the
    container is a shape this project keeps meeting. The current installer gates
    on this process's exit status instead and does not care about key order.

    It is emitted beside a ``kv_shape_note`` as well as beside a shape. Whether
    the KV formula applies and whether the model is hybrid are separate
    questions -- gemma4 is refused for windowed attention and is still
    definitively not hybrid, and that is worth saying.

    The result is parsed before it is returned. The caller splices this into an
    object it is printf-ing with no encoder anywhere in the path, so a fragment
    that does not compose is a job document nothing can read -- and the grammar
    is this module's to keep, not the bash script's to re-derive.
    """
    try:
        header = read_header(path)
    except (_Bad, OSError, struct.error, UnicodeDecodeError):
        return ""
    parts: List[str] = []
    shape = kv_shape(header.meta, header.attn_layers)
    if shape is not None:
        parts.extend(f',"{k}":{v}' for k, v in shape.items())
    else:
        note = kv_shape_note(header.meta)
        if note is not None:
            parts.append(f',"kv_shape_note":"{_json_str(note)}"')
    # None means the index could not be walked, or walked and named no block
    # tensor at all. Neither is the same claim as zero, and neither may be
    # reported as "not hybrid".
    if header.ssm_layers is not None:
        parts.append(f',"ssm_layers":{header.ssm_layers}')
    out = "".join(parts)
    if not out:
        return ""
    try:
        json.loads("{" + out[1:] + "}")
    except ValueError:
        # Unreachable barring a bug above, which is exactly when it matters:
        # silence costs the caller a shape it can measure instead, while a
        # malformed splice costs it the whole job record.
        return ""
    return out


def ssm_layers(path: str) -> str:
    """``ssm_layers`` for ``path`` as a bare integer, or ``""`` if unknown.

    DP-364: the installer picks the unit's cache mode from this (grid for a
    hybrid, swap for a dense model), and asks it rather than picking the number
    out of ``fragment()``
    with a shell pattern -- DP-360 is what a pattern over this module's output
    costs. Unknown stays empty rather than ``0``, so the caller can tell "not a
    hybrid" from "could not tell", and refuses on both.
    """
    try:
        header = read_header(path)
    except (_Bad, OSError, struct.error, UnicodeDecodeError):
        return ""
    return "" if header.ssm_layers is None else str(header.ssm_layers)


def main() -> int:
    """Write the answer and exit 0; the exit status IS the caller's gate.

    ``gguf_header.py <file>`` writes the JSON fragment; ``gguf_header.py
    --ssm-layers <file>`` writes the SSM block count alone (DP-364).

    Exit 0 promises "stdout is a complete answer", empty included -- a header
    this cannot read is a normal outcome and must never fail an install whose
    bytes verified. Every other status means this process did not get to make
    that promise (an unhandled error, an OOM kill, a failed flush), and the
    caller discards whatever it captured rather than splicing a partial write
    into a JSON document. `flush` is explicit so a write that fails does so
    here, where the interpreter turns it into a non-zero exit, rather than
    silently at shutdown.
    """
    if len(sys.argv) == 3 and sys.argv[1] == "--ssm-layers":
        text = ssm_layers(sys.argv[2])
    elif len(sys.argv) == 2:
        text = fragment(sys.argv[1])
    else:
        return 0
    if text:
        sys.stdout.write(text)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
