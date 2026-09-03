# CLAUDE.md

Async, provider-agnostic LLM orchestration engine (Discord / Gmail / Zammad interfaces).

**This file is deliberately short.** It holds only what must be true before the first
tool call. Everything else is one pointer away — follow the pointer rather than
re-deriving, and put new detail *behind* a pointer rather than here.

**Two agents work this repo** — Claude Code and Antigravity (Gemini). CLAUDE.md is the
single source of truth; `.agents/AGENTS.md` is an auto-generated mirror synced by
`.githooks/pre-commit`. Never hand-edit the mirror, and never fork tool-specific
instructions.

## Commands

```bash
pytest -m "not llm_live" -n auto                    # default test run
flake8 src/ services/                               # lint (services/ is deployed code; CI gates it)
mypy src/ services/ --config-file mypy.ini          # type check
python -m src.main                                  # run
```

Those three are the CI gates (`.github/workflows/deploy.yml`). Test tiers, markers, and
the **mandatory test requirements** for schema/config/contract/startup changes:
**`docs/testing.md`** — read it before changing any of those four things.

## Non-negotiables

**1. Every task is a DP-ID.** Branch `feature/DP-XXX-slug` or `bugfix/DP-XXX-slug`;
commit `DP-XXX: description` (a Conventional-Commits prefix is fine, no decorative
emoji); a ticket file at `memory/project/tasks/DP-XXX.md`. **No `Co-Authored-By: Claude`
trailer and no "Generated with Claude Code" line.**

**2. Fetch before you read, not just before you push.** `git fetch origin` and check
`git log --oneline HEAD..origin/master` *before* reading, planning or editing — work on a
stale tree is wasted twice, because the bug may already be fixed and the file you
reasoned about is not the file that ships. Same for the notes repo (`git -C memory
fetch`). The SessionStart git-sync line and the status-line mark are hints, not proof.

**3. All DP work happens in a worktree, cut from `origin/master`.** Including solo
sessions — the main tree is a shared mutable surface that may already hold another
task's edits.

```bash
git fetch origin && git worktree add worktrees/DP-XXX -b bugfix/DP-XXX-slug origin/master
```

Never branch from local `master` (it drifts, and that produced duplicate DP-IDs and
rework against an old base). Edit, test and commit **inside** the worktree; run `pytest`
there too, using its own `.venv`. Never `git checkout`/`git pull` in the main tree while
another agent is working. Venv provisioning, hook behaviour and teardown:
`memory/infrastructure/worktree_env_and_hooks.md`.

**4. Never stage or commit from the main repo directory.** Before any `git add`, confirm
you are inside `worktrees/DP-XXX/` and that `git status` shows only files *you* changed.
If it lists another DP's uncommitted work, **stop** — a path-broad add sweeps it in.

**5. `git status` in the main tree cannot see a worktree.** Check `git status` inside
every worktree before removing it and before calling its ticket done. A merged PR, a
green deploy and an updated capability map all pass while unstaged work sits in a sibling
directory — that is how a security pass went unnoticed for two days.

**6. Human approval gates merges to `master`, not PRs.** Open the PR automatically once
work is done and gates are green.

**7. Docs-only changes are not PR-worthy — land them straight on `master`.** No branch, no
worktree, no PR, no ticket. "Docs-only" means the diff touches **nothing but** `docs/`,
`readme.md`, `CLAUDE.md` and `.agents/AGENTS.md`; one line under `src/`, `services/`,
`config/`, `tests/`, `scripts/` or `.github/` and rules 1–6 apply to the whole change.
Fixing a stale doc you noticed is the common case and it should cost one commit.

⚠️ Rule 4 still holds in spirit: **stage explicit paths, never `git add -A`**, and confirm
`git status` lists only files you touched — the main tree is still shared, and a path-broad
add still sweeps another task's WIP. That is the hazard rule 4 exists for; the branch was
never the protection.

⚠️ A doc that ships *with* code is not this rule — CLAUDE.md's §Docs table still requires
`user_guide.md`, `architecture.md` and `capability_map.md` to move **in the same commit as
the code**. This rule is for standalone doc work: a staleness fix, a correction, a rewrite.

## Memory — Viking L0/L1/L2, not the default auto-memory

⚠️ **`memory/` is a separate git repo** (`derpr-private-notes`), gitignored here. "Commit
the plan / memory / task" means `git -C memory ...`. Independent history and branches.

`memory/MEMORY.md` (L0) is auto-loaded and is **strictly an index**. Read the relevant
`<dir>/_overview.md` (L1) before any individual file (L2). Write bottom-up — L2 first,
then regenerate L1 from it, then touch L0 only if a directory summary changed — and
**commit and push immediately**, no batching.

Trust the code over the memory, and the L2 over the index that points at it.

Full protocol — tiers, mutability, when to write, Hindsight's supplementary role:
**`memory/protocol.md`**.

## Docs — and the duplication problem they exist to solve

| File | Answers |
|---|---|
| `docs/user_guide.md` | what users can do. **Also the spec** — describe new behavior here in plain language *before* implementing |
| `docs/architecture/architecture.md` | how it works internally. **Canonical** (`memory/codebase/architecture.md` is a pointer stub) |
| `docs/capability_map.md` | capability → implementations. The inverse index the other two structurally cannot be |
| `docs/mechanism_ledger.md` | the same question keyed on **mechanism** — trigger · durable store · idempotency · resumer · gate. Regenerated from source, not maintained |

Update `user_guide.md`, `architecture.md` and `capability_map.md` **in the same commit as
the code**. A second implementation of an existing capability is recorded as `by design`
with a decision record, or it is not written. Fix any doc you notice is stale.

**Search by mechanism, never by name.** Before adding a capability ask "does anything
already do this job?", not "is there a function called `approve_x`?". Code here is
*regenerated*, not copy-pasted, so a re-derived implementation shares neither the name nor
the vocabulary of the original and no clone detector will find it. The capability map
catches this only when the author recognizes the sibling; the mechanism ledger is what
catches it when they do not — **two rows with the same shape and different module names
are a duplicate.** `python scripts/arch_audit.py similar concepts` covers the
function-level case.

> This is not hypothetical: `docs/mechanism_ledger.md` exists because a fourth copy of the
> deferred-result pipeline shipped 26 days after the capability map was created — *while
> its author was filling in a row of that map*.
