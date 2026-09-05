# src/utils/atomic_json.py
"""Crash-safe and permission-safe JSON writes for the JSON stores under DATA_DIR.

DP-361. Two stores here persist structured state as a JSON file — `personas.json`
(`src/personas/store.py`) and `mcp_servers.json` (`src/tools/mcp_client.py`) — and
both had independently arrived at the same mechanism, one of them only after the
in-place version cost two weeks of prod. This module is that mechanism, once.

The two properties it buys:

- **Crash safety.** `open(path, 'w')` truncates before the first byte is written,
  so a serialization failure mid-dump destroys the previous contents outright.
- **Permission safety.** Truncating in place needs write permission on the *file*.
  Creating a sibling and renaming over the target needs only permission on the
  *directory* — which is what actually broke prod: a root-run maintenance pass left
  `/app/data/personas.json` `root:root` while `/app/data` stayed writable by the
  container user, and every persona-mutating command raised PermissionError for two
  weeks. Rename also **self-heals** the ownership on the first successful save.
"""

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Union


def write_json_atomic(path: Union[str, Path], data: Any, indent: int = 4) -> None:
    """Serialize ``data`` to ``path`` via a sibling temp file and ``os.replace``.

    The temp file is created in the destination's own directory (``os.replace`` is
    only atomic within a filesystem) and removed if anything raises, so a failure
    leaves neither debris nor a truncated target.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=indent)
            file.flush()
            os.fsync(file.fileno())
        # mkstemp creates 0600; match the 0644 an in-place write would have
        # preserved, so sidecar readers (backup scripts, `docker exec` inspection)
        # keep working.
        os.chmod(tmp_name, 0o644)
        try:
            os.replace(tmp_name, path)
        except PermissionError:
            # POSIX rename needs only directory permission, so this is Windows:
            # os.replace refuses a destination carrying FILE_ATTRIBUTE_READONLY.
            # Clear it and retry — we are overwriting the file either way, and
            # letting local dev on Windows diverge from the Linux container is how
            # the next persistence bug hides until it reaches prod.
            os.chmod(path, 0o644)
            os.replace(tmp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise
