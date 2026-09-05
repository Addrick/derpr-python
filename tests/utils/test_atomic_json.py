# tests/utils/test_atomic_json.py
"""DP-361: the shared crash/permission-safe JSON writer.

`tests/personas/test_store.py` covers the store-level behaviour these properties
buy; this file pins the mechanism itself, since `mcp_client._save_config` now
depends on the same helper.
"""

import json
import os
from pathlib import Path

import pytest

from src.utils.atomic_json import write_json_atomic


def test_writes_and_reads_back(tmp_path: Path):
    target = tmp_path / "state.json"
    write_json_atomic(target, {"a": [1, 2], "b": None})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": [1, 2], "b": None}


def test_creates_missing_parent_directories(tmp_path: Path):
    target = tmp_path / "nested" / "deeper" / "state.json"
    write_json_atomic(target, {"ok": True})
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}


def test_replaces_a_destination_the_process_cannot_open_for_writing(tmp_path: Path):
    """The prod failure: rename needs directory permission, not file permission.

    chmod 0444 stands in for the root:root ownership that made
    `open(path, 'w')` raise PermissionError inside the container.
    """
    target = tmp_path / "state.json"
    target.write_text('{"old": true}', encoding="utf-8")
    os.chmod(target, 0o444)

    write_json_atomic(target, {"new": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {"new": True}


def test_leaves_no_temp_file_behind_on_success(tmp_path: Path):
    target = tmp_path / "state.json"
    write_json_atomic(target, {"a": 1})
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


def test_failure_preserves_the_previous_content_and_removes_the_temp(tmp_path: Path):
    """Truncate-in-place destroyed the file before serialization could fail."""
    target = tmp_path / "state.json"
    target.write_text('{"keep": "me"}', encoding="utf-8")

    class Unserializable:
        pass

    with pytest.raises(TypeError):
        write_json_atomic(target, {"bad": Unserializable()})

    assert json.loads(target.read_text(encoding="utf-8")) == {"keep": "me"}
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


def test_indent_is_configurable(tmp_path: Path):
    """mcp_servers.json is indent=2; personas.json is indent=4."""
    target = tmp_path / "state.json"
    write_json_atomic(target, {"a": 1}, indent=2)
    assert target.read_text(encoding="utf-8") == '{\n  "a": 1\n}'
