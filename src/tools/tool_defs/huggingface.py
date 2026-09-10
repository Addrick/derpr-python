"""HuggingFace model-provisioning tools (service_binding: huggingface, DP-265).

Two Hub reads, one parked write that provisions a gguf onto the pve node, and
one poll for the resulting job.

**Read this before changing a capability flag here.** The four tools sit beside
the proxmox toolset on one persona (``hypr``), and that composition is the whole
reason the flags are what they are:

- ``hf_search`` / ``hf_files`` are ``produces_untrusted: True``. Repo ids,
  filenames and card text are written by whoever uploaded the repo.
- Their egress domain is ``huggingface``, straight from ``service_binding``.
- ``install_model`` writes to the same domain it reads from: derpr's own hop is
  SSH to the node, but the payload it carries — the repo id — is what the node
  then fetches *from HuggingFace*. Tagging it ``huggingface`` is therefore
  accurate, not a dodge, and it makes the persona a **same-origin closed loop**
  under ``ToolPolicy`` Rule 2 rather than an exfiltration path.
- ``install_status`` declares ``domain: "proxmox"`` explicitly (the
  ``capabilities["domain"]`` seam), because its egress genuinely is the node and
  not the Hub. It is ``exfil_capable: False``: the only argument is a job id
  matched against ``_JOB_ID_RE`` **before** it crosses SSH, bound for a host we
  own.

The counterpart edit lives in ``proxmox.py``: the guest/node write tools became
``exfil_capable: False`` in the same change. Without that, ``network_write_domains``
would still hold ``proxmox`` while the untrusted reads are ``huggingface``, Rule
2 would fire on a foreign-domain write, and ``hypr`` would be quarantined. The
honest fix is the flag on those tools (their arguments are vmids and names
*discovered from the node*, so no model-authored payload rides out) — **not** an
``explicit_overrides`` entry, which would disarm Rule 2 for hypr's whole toolset
permanently, including for tools added later.
"""

from typing import Any, Dict, List


HUGGINGFACE_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "is_write": False,
        "service_binding": "huggingface",
        "capabilities": {
            # Repo names, descriptions and tags are third-party text.
            "produces_untrusted": True,
            "irreversible": False,
            "locality": "network",
            "sensitivity": "public",
        },
        "function": {
            "name": "hf_search",
            "description": (
                "Search HuggingFace for repositories that publish gguf model "
                "files, most-downloaded first. Returns repo id, downloads, "
                "likes, gated flag and tags. A hit means the repo is tagged as "
                "containing gguf — not that any particular file exists or will "
                "fit. Follow up with hf_files to see the actual files and their "
                "sizes before proposing an install. "
                "ONLY gguf-tagged repos are searchable: an upstream publisher "
                "shipping safetensors (most official model repos) can never be "
                "returned, so asking for 'the official <model>' means finding "
                "the community quant of it — match one by its "
                "`base_model:<owner>/<name>` tag. If a search returns nothing, "
                "broaden it rather than re-spelling the same name; the filter "
                "will not change."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search text, e.g. a model family or quant name.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Maximum repos to return (default 10, capped by "
                            "HF_SEARCH_LIMIT_MAX)."
                        ),
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "is_write": False,
        "service_binding": "huggingface",
        "capabilities": {
            "produces_untrusted": True,
            "irreversible": False,
            "locality": "network",
            "sensitivity": "public",
        },
        "function": {
            "name": "hf_files",
            "description": (
                "List one HuggingFace repo's gguf files with the exact byte "
                "size and sha256 the Hub publishes for each. Use it to pick a "
                "quant that fits the VRAM budget (check gpu_status) and to get "
                "the exact filename install_model needs. A file whose sha256 is "
                "null cannot be installed — there would be nothing to verify "
                "the download against. If the result carries truncated: true "
                "the listing is INCOMPLETE: a file you do not see may still "
                "exist, so name the exact file you want rather than concluding "
                "the repo does not have it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repo id as 'owner/name', exactly as hf_search reports it.",
                    },
                },
                "required": ["repo"],
            },
        },
    },
    {
        "type": "function",
        "is_write": True,
        "service_binding": "huggingface",
        "capabilities": {
            "produces_untrusted": False,
            # Reversible in the sense that matters: it adds a file and a
            # DISABLED unit, takes nothing down, and touches nothing that is
            # serving. Deleting both undoes it. The cost that is *not* trivially
            # undone is the disk it fills, which is why the node refuses on a
            # failed free-space precheck rather than downloading and truncating.
            "irreversible": False,
            "locality": "network",
            "sensitivity": "internal",
            # See the module docstring: the payload's real destination is the
            # Hub, so this write shares a domain with the untrusted reads above
            # and the composition stays a closed loop.
            "domain": "huggingface",
        },
        "function": {
            "name": "install_model",
            "description": (
                "Download a gguf from HuggingFace onto the model host and write "
                "a koboldcpp systemd unit for it, so it becomes a choice "
                "list_models offers and set_active_model can switch to. "
                "Requires human approval, and the approval card shows the repo, "
                "file, byte size and sha256 read from HuggingFace itself, plus "
                "the tuning you chose. Every flag the unit runs with is written "
                "into it, so list_models reports what it actually runs. "
                "The download continues on the node after this returns — poll "
                "install_status with the job_id. The unit is written DISABLED "
                "and does NOT start: putting it on :5001 is a separate "
                "set_active_model call. Check gpu_status and size the "
                "contextsize before proposing this; the node refuses if there "
                "is not enough free disk, and refuses on any sha256 mismatch."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repo id as 'owner/name', from hf_search or hf_files.",
                    },
                    "file": {
                        "type": "string",
                        "description": (
                            "The gguf filename inside the repo, exactly as "
                            "hf_files reports its path."
                        ),
                    },
                    "name": {
                        "type": "string",
                        "description": (
                            "Short friendly name for the model: lowercase "
                            "letters, digits and dashes. It becomes the systemd "
                            "unit stem (koboldcpp-<name>.service) and the name "
                            "list_models will report. Must not already exist."
                        ),
                    },
                    "contextsize": {
                        "type": "integer",
                        "description": (
                            "koboldcpp --contextsize for the new unit. Defaults "
                            "to a deliberately small 8192, because the unit "
                            "lands disabled and a human tunes this against "
                            "gpu_status before enabling it. With the tuning's "
                            "precision it is one of the two VRAM knobs here. "
                            "Pick it by comparison and by measurement, not by "
                            "arithmetic: anchor on a unit list_models already "
                            "reports running on this card at a known "
                            "contextsize and the same quantkv, and confirm by "
                            "reading gpu_status before the unit is first "
                            "enabled and again after. Do NOT derive a VRAM "
                            "total — a figure assembled from header terms has "
                            "matched a real measurement on this box only by "
                            "two errors cancelling, so any product you form is "
                            "a confident wrong number. Overshooting into GTT "
                            "is recoverable; a wrong total quoted as "
                            "arithmetic is not."
                        ),
                    },
                    "tuning": {
                        "type": "string",
                        "enum": [
                            f"{kv}-{cache}"
                            for kv in ("f16", "q8", "q4")
                            for cache in ("off", "swap", "grid")
                        ],
                        "description": (
                            "How the unit holds its KV cache, as "
                            "<precision>-<cache mode>. Precision: q8 is the "
                            "usual choice; f16 is full precision and roughly "
                            "doubles the cache; q4 halves it again and costs "
                            "output quality, so propose it only when the "
                            "context cannot fit otherwise. Cache mode: swap "
                            "keeps several conversations' contexts so switching "
                            "between them does not reprocess the prompt — the "
                            "right choice for a model that will serve more "
                            "than one conversation. grid instead checkpoints "
                            "ONE deep conversation so edits and retries deep "
                            "in it do not reprocess; it gives up swapping "
                            "entirely and only works on a hybrid model "
                            "(install_status reports ssm_layers > 0), so the "
                            "node refuses it for anything else. off is plain "
                            "prefix reuse. Say which you chose and why."
                        ),
                    },
                },
                "required": ["repo", "file", "name", "tuning"],
            },
        },
    },
    {
        "type": "function",
        "is_write": False,
        "service_binding": "huggingface",
        "capabilities": {
            # The node emits a fixed vocabulary plus the request's own echoed
            # fields, and `handler._clean_status` whitelists and truncates what
            # is surfaced — so no third-party text reaches the model through
            # this tool. The whitelist is what keeps this flag true; do not
            # replace it with a passthrough.
            "produces_untrusted": False,
            "irreversible": False,
            "locality": "network",
            "sensitivity": "internal",
            # Its egress is the pve node, not the Hub — unlike the other three.
            "domain": "proxmox",
            # The only argument is a minted job id, pattern-checked before it
            # crosses SSH, bound for our own node: no model-controlled payload
            # rides out, so it must not arm the exfil composition rules.
            "exfil_capable": False,
        },
        "function": {
            "name": "install_status",
            "description": (
                "Poll one install_model job by its job_id. Reports state "
                "(running / done / failed), the current step, bytes downloaded "
                "so far, and on failure a short reason such as a sha256 "
                "mismatch or insufficient disk. A multi-GB download takes "
                "minutes to hours — report progress when asked rather than "
                "polling in a tight loop. A finished install also carries what "
                "the node read out of the gguf itself: n_layer / n_kv_head / "
                "head_dim (the cache SHAPE, and n_layer is the count of layers "
                "that actually cache, which is not the block count on a hybrid "
                "model), and ssm_layers — how many blocks hold a recurrent "
                "state instead of a KV cache, so a non-zero value means the "
                "model is a hybrid and a grid tuning can do something for "
                "it. These are measurements read off the file, not estimates. "
                "A job that failed with reason grid_needs_hybrid downloaded "
                "and verified the file and then refused to write a grid unit "
                "for a model that is not a hybrid: the bytes are kept, so "
                "installing it again under a non-grid tuning does not "
                "download again. "
                "It reports no cache size and no VRAM total: multiplying that "
                "shape out needs a bytes-per-element term nothing here can "
                "source, so the job's note points at the gpu_status "
                "measurement instead. Where the node determines the cache is "
                "not linear in contextsize at all it says so in words rather "
                "than sending the shape."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The job_id install_model returned.",
                    },
                },
                "required": ["job_id"],
            },
        },
    },
]
