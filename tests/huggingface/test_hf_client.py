"""Unit tests for the HuggingFace Hub client (DP-265).

No network: the HTTP layer is the thin part, so these pin the parts that decide
what gets installed — which strings are accepted as a repo/file, which tree rows
become an installable file, and which byte count is believed.
"""

from __future__ import annotations

import aiohttp
import pytest
from yarl import URL

from src.huggingface.client import (
    HFClient,
    HFError,
    HFFile,
    _MAX_SEARCH_TAGS,
    _MAX_TREE_PAGES,
    _next_cursor,
    _select_tags,
    validate_file_path,
    validate_repo_id,
)


# -- input validation --------------------------------------------------------

@pytest.mark.parametrize("repo", [
    "TheBloke/Model-GGUF",
    "unsloth/gemma-4-31b-it-GGUF",
    "a/b",
    "owner.name/model_v2-Q6",
])
def test_valid_repo_ids_pass(repo):
    assert validate_repo_id(repo) == repo


@pytest.mark.parametrize("repo", [
    "",
    "no-slash",
    "owner/name/extra",
    "../../etc/passwd",
    "owner/../secret",
    "/leading/slash",
    "owner/name?x=1",
    "owner name/model",
])
def test_traversal_and_malformed_repo_ids_are_refused(repo):
    """The repo id is the one place a model steers a URL, so it is validated
    rather than merely percent-encoded — an encoded traversal comes back 404,
    and a 404 reads to the model as 'try another spelling'."""
    with pytest.raises(HFError):
        validate_repo_id(repo)


@pytest.mark.parametrize("path", [
    "model-Q6_K.gguf",
    "quants/model-Q4_K_M.gguf",
])
def test_valid_file_paths_pass(path):
    assert validate_file_path(path) == path


@pytest.mark.parametrize("path", ["../x.gguf", "a/../../b.gguf", "/abs.gguf", ""])
def test_traversal_file_paths_are_refused(path):
    with pytest.raises(HFError):
        validate_file_path(path)


# -- tree row parsing --------------------------------------------------------

def test_lfs_size_wins_over_the_pointer_size():
    """An LFS row carries the pointer's ~135 bytes at top level on some repos.
    Believing that number would size the node's free-space precheck three orders
    of magnitude too small — the one direction that fills a thin pool."""
    row = {
        "type": "file",
        "path": "model-Q6_K.gguf",
        "size": 135,
        "lfs": {"oid": "a" * 64, "size": 24_000_000_000, "pointerSize": 135},
    }
    entry = HFClient._as_gguf_file(row)
    assert entry is not None
    assert entry.size_bytes == 24_000_000_000
    assert entry.sha256 == "a" * 64


def test_non_lfs_file_has_no_sha256():
    row = {"type": "file", "path": "small.gguf", "size": 4096}
    entry = HFClient._as_gguf_file(row)
    assert entry is not None
    assert entry.sha256 is None


def test_non_gguf_and_directories_are_skipped():
    assert HFClient._as_gguf_file({"type": "file", "path": "README.md", "size": 1}) is None
    assert HFClient._as_gguf_file({"type": "directory", "path": "quants"}) is None
    assert HFClient._as_gguf_file("not a dict") is None


def test_a_non_sha256_oid_is_dropped_rather_than_passed_through():
    """A git blob sha1 in `lfs.oid` must not be mistaken for a digest — the node
    would then verify a 40-hex value that can never match sha256sum output."""
    row = {"type": "file", "path": "m.gguf", "size": 10, "lfs": {"oid": "b" * 40, "size": 10}}
    entry = HFClient._as_gguf_file(row)
    assert entry is not None and entry.sha256 is None


def test_unparseable_size_drops_the_row():
    row = {"type": "file", "path": "m.gguf", "size": "big"}
    assert HFClient._as_gguf_file(row) is None


# -- pagination --------------------------------------------------------------

def test_next_cursor_read_from_link_header():
    header = '<https://huggingface.co/api/models/a/b/tree/main?cursor=ZXlKbQ%3D%3D>; rel="next"'
    assert _next_cursor(header) == "ZXlKbQ%3D%3D"


def test_no_next_link_ends_the_walk():
    assert _next_cursor(None) is None
    assert _next_cursor('<https://x/prev>; rel="prev"') is None


class _FakeResponse:
    """One canned tree page: a status, a JSON body and an optional Link header."""

    def __init__(self, payload, link=None, status=200, text=""):
        self.status = status
        self.headers = {} if link is None else {"Link": link}
        self._payload = payload
        self._text = text

    async def json(self, content_type=None):
        return self._payload

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _fake_aiohttp(monkeypatch, pages):
    """Replace aiohttp.ClientSession with one that serves ``pages`` in order.

    Patched at the aiohttp layer rather than at ``_request`` so the walk runs
    through the real transport call — the defect being pinned is what aiohttp
    does to a ``params`` value, and a fake that intercepts above it cannot see
    that.

    Returns the list every ``(url, params)`` is appended to.
    """
    calls: list = []

    class _Session:
        def __init__(self, *a, **kw):
            pass

        def get(self, url, params=None, headers=None):
            calls.append((url, dict(params or {})))
            return pages[len(calls) - 1]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(aiohttp, "ClientSession", _Session)
    return calls


def _row(path):
    return {"type": "file", "path": path, "size": 10, "lfs": {"oid": "a" * 64, "size": 10}}


def _link(cursor):
    return f'<https://huggingface.co/api/models/a/b/tree/main?cursor={cursor}>; rel="next"'


@pytest.mark.asyncio
async def test_tree_cursor_is_decoded_once_before_it_is_handed_back(monkeypatch):
    """The cursor comes out of the Link header percent-ENCODED, and aiohttp
    encodes ``params`` values again on the way out.

    A base64 cursor's `=` padding therefore went out as `%253D`, and the Hub
    rejected or misread every page after the first: a repo with more than one
    tree page was silently HALF-listed, and a file that exists read as a typo.
    Nothing errored, which is why this needed a test rather than a bug report.
    """
    pages = [
        _FakeResponse([_row("page1-Q6.gguf")], link=_link("ZXlKbQ%3D%3D")),
        _FakeResponse([_row("page2-Q4.gguf")]),
    ]
    calls = _fake_aiohttp(monkeypatch, pages)

    files, truncated = await HFClient(base_url="https://hub").list_gguf_files("a/b")

    assert [f.path for f in files] == ["page1-Q6.gguf", "page2-Q4.gguf"]
    assert truncated is False
    # The second request carries the DECODED cursor...
    assert calls[1][1] == {"recursive": "1", "cursor": "ZXlKbQ=="}
    # ...which is what makes the value on the wire the one the Hub issued.
    # `with_query` is exactly what aiohttp does with `params`, so this is the
    # assertion that would have failed before the fix.
    assert URL(calls[1][0]).with_query(calls[1][1]).query_string.endswith("ZXlKbQ%3D%3D")
    assert "%253D" not in URL(calls[1][0]).with_query(calls[1][1]).query_string


@pytest.mark.asyncio
async def test_a_tree_longer_than_the_page_cap_says_so(monkeypatch):
    """`_MAX_TREE_PAGES` bounds how long a repo can make a tool call run, so it
    has to exist — but a bare list is indistinguishable from a complete one, and
    a caller that cannot tell reports a partial listing as the whole truth."""
    pages = [
        _FakeResponse([_row(f"shard-{i}.gguf")], link=_link(f"cur{i}"))
        for i in range(_MAX_TREE_PAGES + 3)
    ]
    calls = _fake_aiohttp(monkeypatch, pages)

    files, truncated = await HFClient(base_url="https://hub").list_gguf_files("a/b")

    assert truncated is True
    assert len(calls) == _MAX_TREE_PAGES  # the cap is still a cap
    assert len(files) == _MAX_TREE_PAGES


@pytest.mark.asyncio
async def test_a_repeated_cursor_ends_the_walk_without_claiming_truncation(monkeypatch):
    """A Hub that hands back the cursor it was given is a loop, not a longer
    tree; ending on it is complete, and saying "truncated" there would put a
    false warning on a listing that has everything."""
    pages = [
        _FakeResponse([_row("a.gguf")], link=_link("same")),
        _FakeResponse([_row("b.gguf")], link=_link("same")),
    ]
    calls = _fake_aiohttp(monkeypatch, pages)

    files, truncated = await HFClient(base_url="https://hub").list_gguf_files("a/b")

    assert truncated is False
    assert len(calls) == 2
    assert [f.path for f in files] == ["a.gguf", "b.gguf"]


@pytest.mark.asyncio
async def test_a_404_on_the_tree_is_a_repo_error_not_a_transport_error(monkeypatch):
    """The 404 message survived folding the per-endpoint failure ladder into one
    `_request`. It was duplicated before, which is how two paths came to handle
    the same aiohttp exception differently."""
    _fake_aiohttp(monkeypatch, [_FakeResponse(None, status=404, text="not found")])

    with pytest.raises(HFError, match="no such HuggingFace repo"):
        await HFClient(base_url="https://hub").list_gguf_files("a/b")


@pytest.mark.asyncio
async def test_a_hub_5xx_on_the_tree_reports_its_status_and_body(monkeypatch):
    _fake_aiohttp(monkeypatch, [_FakeResponse(None, status=503, text="upstream down")])

    with pytest.raises(HFError, match="503"):
        await HFClient(base_url="https://hub").list_gguf_files("a/b")


# -- find_gguf_file ----------------------------------------------------------

@pytest.mark.asyncio
async def test_find_refuses_a_file_with_no_published_digest(monkeypatch):
    """The digest is the only thing tying the bytes that land on the node to the
    bytes a human approved, so 'install it unverified' is not a degraded mode —
    it is the whole control being switched off."""
    client = HFClient()

    async def fake_list(repo, revision="main"):
        return [HFFile(path="m.gguf", size_bytes=10, sha256=None)], False

    monkeypatch.setattr(client, "list_gguf_files", fake_list)
    with pytest.raises(HFError, match="no LFS sha256"):
        await client.find_gguf_file("a/b", "m.gguf")


@pytest.mark.asyncio
async def test_find_lists_what_the_repo_does_offer_on_a_miss(monkeypatch):
    client = HFClient()

    async def fake_list(repo, revision="main"):
        return [HFFile(path="real-Q6.gguf", size_bytes=10, sha256="c" * 64)], False

    monkeypatch.setattr(client, "list_gguf_files", fake_list)
    with pytest.raises(HFError, match="real-Q6.gguf"):
        await client.find_gguf_file("a/b", "typo-Q6.gguf")


@pytest.mark.asyncio
async def test_find_refuses_rather_than_reporting_absence_from_a_partial_listing(monkeypatch):
    """When the walk was cut short, "no such file" is a claim the listing does
    not support — the file may sit on a page never reached. Reporting absence
    (and worse, "it offers: [...]") is a false statement the model then acts on,
    and re-spelling a name that was right the first time is the loop DP-335 was
    filed to break. A refusal is recoverable; a confident wrong answer is not.
    """
    client = HFClient()

    async def fake_list(repo, revision="main"):
        return [HFFile(path="shard-01.gguf", size_bytes=10, sha256="c" * 64)], True

    monkeypatch.setattr(client, "list_gguf_files", fake_list)
    with pytest.raises(HFError, match="could not be confirmed absent"):
        await client.find_gguf_file("a/b", "shard-99.gguf")


@pytest.mark.asyncio
async def test_find_returns_the_matching_entry(monkeypatch):
    client = HFClient()
    wanted = HFFile(path="m-Q6.gguf", size_bytes=99, sha256="d" * 64)

    async def fake_list(repo, revision="main"):
        return [HFFile(path="other.gguf", size_bytes=1, sha256="e" * 64), wanted], False

    monkeypatch.setattr(client, "list_gguf_files", fake_list)
    assert await client.find_gguf_file("a/b", "m-Q6.gguf") is wanted


def test_to_dict_reports_bytes_and_gib():
    entry = HFFile(path="m.gguf", size_bytes=2 * 1024 ** 3, sha256="f" * 64)
    assert entry.to_dict() == {
        "path": "m.gguf",
        "size_bytes": 2147483648,
        "size_gib": 2.0,
        "sha256": "f" * 64,
    }


# -- search payload ----------------------------------------------------------

def test_search_tags_keep_base_model_ahead_of_the_truncation():
    """`base_model:` survives the tag cap (DP-335 review).

    The tool description, the handler note and hypr's prompt all tell the model
    to match a quant repo to its upstream model by this tag. The cap used to be
    a bare slice over the Hub's own unordered list, and `base_model:` sorts
    late — so a model told three times to read the field searched hits that did
    not carry it, concluded no quant corresponded to the model it was asked
    about, and re-queried: the exact budget-burning loop DP-335 exists to
    break.
    """
    raw = (
        ["gguf", "transformers", "text-generation", "conversational"]
        + [f"lang:{c}" for c in "abcdefghij"]
        + ["base_model:Qwen/Qwen3.8-27B", "license:apache-2.0"]
    )

    tags = _select_tags(raw)

    assert len(tags) == _MAX_SEARCH_TAGS
    assert tags[0] == "base_model:Qwen/Qwen3.8-27B"
    # Everything else keeps the Hub's own order, so a truncated list still
    # reads like the source.
    assert tags[1:4] == ["gguf", "transformers", "text-generation"]


def test_search_tags_are_unchanged_when_there_is_no_base_model_tag():
    tags = _select_tags(["gguf", "transformers"])
    assert tags == ["gguf", "transformers"]


def test_search_tags_tolerate_a_missing_or_non_string_tag_list():
    assert _select_tags(None) == []
    assert _select_tags([1, "gguf"]) == ["1", "gguf"]
