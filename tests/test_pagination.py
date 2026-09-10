"""Pagination tests for PRD-17977 (chargebee_list_* offset/next_offset).

No real network calls: each test registers the tool(s) under test on a fresh
FastMCP instance with a fake ChargebeeClient (a plain object exposing an
async .get(path, params=None)), and drives the tool through
FastMCP.call_tool so the MCP layer's own argument pre-parsing (the thing that
turns a JSON-array-looking string into a real list before Pydantic sees it —
see _common.py's cursor codec docstring) is exercised for real, not bypassed.

Mapping to docs/tickets/PRD-17977.ac.json: TC-CBM-001/002/003/004/005/006/
008/009/010/013/014/015 (the 12 `type: auto` cases). TC-CBM-007/011/012 are
`type: manual` and need a real Chargebee test-site — not covered here, see
the "自测" section of PRD-17977.md.
"""

import json

import pytest
from mcp.server.fastmcp import FastMCP

from chargebee_mcp.tools import customers, reports, subscriptions


class FakeClient:
    """Stands in for ChargebeeClient: .get() returns queued canned
    responses in order and records every call for assertions."""

    def __init__(self, pages):
        self._pages = list(pages)
        self.calls = []

    async def get(self, path, params=None):
        self.calls.append((path, dict(params or {})))
        return self._pages.pop(0)


def _mcp_with(fake_client, tool="subscriptions"):
    mcp = FastMCP(name="test")
    if tool == "subscriptions":
        subscriptions.register(mcp, lambda: fake_client)
    elif tool == "invoices" or tool == "transactions":
        reports.register(mcp, lambda: fake_client)
    elif tool == "customers":
        customers.register(mcp, lambda: fake_client)
    return mcp


async def _call(mcp, name, **args):
    _content, structured = await mcp.call_tool(name, args)
    return json.loads(structured["result"])


# ── AC1/TC-CBM-001: page_cursor round-trips and unblocks page 2 ────────────
@pytest.mark.asyncio
async def test_page_cursor_round_trip_gets_page_two():
    fake = FakeClient(
        [
            {
                "list": [{"subscription": {"id": "s1"}}],
                "next_offset": ["1666285190000", "41937694"],
            },
            {"list": [{"subscription": {"id": "s2"}}]},
        ]
    )
    mcp = _mcp_with(fake)

    page1 = await _call(mcp, "chargebee_list_subscriptions", limit=10)
    assert "error" not in page1
    cursor = page1["page_cursor"]
    assert cursor.startswith("cb1.")

    page2 = await _call(mcp, "chargebee_list_subscriptions", limit=10, offset=cursor)
    assert "error" not in page2
    assert page2["list"][0]["subscription"]["id"] == "s2"
    # the second call actually forwarded a Chargebee-shaped offset, not our
    # opaque wrapper
    _, second_params = fake.calls[1]
    expected_offset = json.dumps(["1666285190000", "41937694"], separators=(",", ":"))
    assert second_params["offset"] == expected_offset


# ── AC1/TC-CBM-002: raw next_offset passed back also works (back-compat) ──
@pytest.mark.asyncio
async def test_raw_next_offset_passed_back_also_works():
    fake = FakeClient(
        [
            {
                "list": [{"subscription": {"id": "s1"}}],
                "next_offset": ["1666285190000", "41937694"],
            },
            {"list": [{"subscription": {"id": "s2"}}]},
        ]
    )
    mcp = _mcp_with(fake)

    page1 = await _call(mcp, "chargebee_list_subscriptions", limit=10)
    raw_next_offset = page1["next_offset"]

    page2 = await _call(mcp, "chargebee_list_subscriptions", limit=10, offset=raw_next_offset)
    assert "error" not in page2
    assert page2["list"][0]["subscription"]["id"] == "s2"


# ── AC2/TC-CBM-003: consecutive pages accumulate to the full set ──────────
@pytest.mark.asyncio
async def test_consecutive_pages_cover_full_set_no_gaps_no_dupes():
    fake = FakeClient(
        [
            {"list": [{"id": "a"}, {"id": "b"}], "next_offset": ["1000", "x1"]},
            {"list": [{"id": "c"}, {"id": "d"}], "next_offset": ["2000", "x2"]},
            {"list": [{"id": "e"}]},
        ]
    )
    mcp = _mcp_with(fake)

    seen = []
    offset = None
    for _ in range(10):  # bounded loop, not a while-True
        resp = await _call(mcp, "chargebee_list_subscriptions", limit=2, offset=offset)
        seen.extend(item["id"] for item in resp["list"])
        offset = resp.get("page_cursor")
        if offset is None:
            break

    assert seen == ["a", "b", "c", "d", "e"]


# ── AC3/TC-CBM-004: single page, no cursor fields at all ──────────────────
@pytest.mark.asyncio
async def test_single_page_has_no_cursor_fields():
    fake = FakeClient([{"list": [{"id": "only"}]}])
    mcp = _mcp_with(fake)

    resp = await _call(mcp, "chargebee_list_subscriptions", limit=10)
    assert "next_offset" not in resp
    assert "page_cursor" not in resp


# ── AC4/TC-CBM-005: truncation re-fetches at the size that actually fits ──
@pytest.mark.asyncio
async def test_oversized_page_triggers_refetch_with_matching_cursor():
    big_row = {"id": "x", "blob": "y" * 800}
    first_page = {"list": [big_row] * 40, "next_offset": ["1000", "big"]}
    # A second, smaller request Chargebee would actually answer with a
    # cursor that lines up with the rows it returns this time.
    refetched_page = {"list": [big_row] * 20, "next_offset": ["1000", "smaller"]}
    fake = FakeClient([first_page, refetched_page])
    mcp = _mcp_with(fake)

    resp = await _call(mcp, "chargebee_list_subscriptions", limit=40)

    assert len(fake.calls) == 2, "must have re-fetched once at a smaller limit"
    first_limit = fake.calls[0][1]["limit"]
    second_limit = fake.calls[1][1]["limit"]
    assert second_limit < first_limit
    # the cursor we hand back must decode to the *refetched* next_offset,
    # not the first (oversized) response's — this is the AC4 guarantee.
    assert len(resp["list"]) == 20
    assert resp["next_offset"] == ["1000", "smaller"]


# ── AC5/TC-CBM-006: garbage cursor -> invalid_argument, not a crash ───────
@pytest.mark.asyncio
async def test_garbage_offset_is_invalid_argument_not_a_crash():
    fake = FakeClient([])
    mcp = _mcp_with(fake)

    resp = await _call(mcp, "chargebee_list_subscriptions", limit=10, offset="not-a-real-cursor")
    assert resp["error"]["code"] == "invalid_argument"
    assert resp["error"]["retryable"] is False
    assert fake.calls == [], "must reject before ever calling Chargebee"


# ── AC7/TC-CBM-008: original next_offset is never deleted or renamed ──────
@pytest.mark.asyncio
async def test_original_next_offset_field_preserved():
    fake = FakeClient([{"list": [{"id": "a"}], "next_offset": ["1000", "id1"]}])
    mcp = _mcp_with(fake)

    resp = await _call(mcp, "chargebee_list_subscriptions", limit=10)
    assert resp["next_offset"] == ["1000", "id1"]
    assert resp["page_cursor"].startswith("cb1.")


# ── AC8/TC-CBM-009 + TC-CBM-010: "" and omitted offset both mean page 1 ───
@pytest.mark.asyncio
async def test_empty_string_offset_is_first_page():
    fake = FakeClient([{"list": [{"id": "a"}]}])
    mcp = _mcp_with(fake)

    resp = await _call(mcp, "chargebee_list_subscriptions", limit=10, offset="")
    assert "error" not in resp
    _, params = fake.calls[0]
    assert params["offset"] is None


@pytest.mark.asyncio
async def test_omitted_offset_is_first_page():
    fake = FakeClient([{"list": [{"id": "a"}]}])
    mcp = _mcp_with(fake)

    resp = await _call(mcp, "chargebee_list_subscriptions", limit=10)
    assert "error" not in resp
    _, params = fake.calls[0]
    assert params["offset"] is None


# ── AC5/TC-CBM-013: a well-formed but invented JSON-array offset is rejected
@pytest.mark.asyncio
async def test_invented_json_array_offset_is_rejected():
    fake = FakeClient([])
    mcp = _mcp_with(fake)

    # This string is valid JSON and *will* get pre-parsed into a real list by
    # the MCP layer before our function sees it (same mechanism as the real
    # cursor round-trip) — but nobody issued these values.
    resp = await _call(
        mcp, "chargebee_list_subscriptions", limit=10, offset=json.dumps(["fake_a", "fake_b"])
    )
    assert resp["error"]["code"] == "invalid_argument"
    assert fake.calls == []


# ── AC2/TC-CBM-014: a cursor from a different tool/resource is rejected ───
@pytest.mark.asyncio
async def test_cursor_from_a_different_tool_is_rejected():
    fake = FakeClient([{"list": [{"id": "inv1"}], "next_offset": ["1000", "invid"]}])
    mcp = _mcp_with(fake, tool="invoices")

    invoices_page = await _call(mcp, "chargebee_list_invoices", limit=10)
    invoices_cursor = invoices_page["page_cursor"]

    fake2 = FakeClient([])
    mcp2 = _mcp_with(fake2, tool="subscriptions")
    resp = await _call(mcp2, "chargebee_list_subscriptions", limit=10, offset=invoices_cursor)

    assert resp["error"]["code"] == "invalid_argument"
    assert fake2.calls == []


# ── AC6/TC-CBM-015: replaying a cursor under a different tenant's client ──
# never leaks the issuing tenant's data — each request is scoped to
# whichever ChargebeeClient client_factory() hands back *for that call*,
# and the cursor payload carries no tenant identity at all.
@pytest.mark.asyncio
async def test_cursor_replayed_under_another_tenant_stays_scoped_to_that_tenant():
    tenant_a = FakeClient(
        [{"list": [{"id": "a-row"}], "next_offset": ["1000", "cursorA"]}]
    )
    mcp_a = _mcp_with(tenant_a)
    page = await _call(mcp_a, "chargebee_list_subscriptions", limit=10)
    cursor = page["page_cursor"]

    # Same opaque cursor string, but this time client_factory resolves to
    # tenant B's own client (simulating the same cursor value reaching the
    # gateway under a different X-Chargebee-Site/-Api-Key pair).
    tenant_b = FakeClient([{"list": [{"id": "b-row-page-2"}]}])
    mcp_b = _mcp_with(tenant_b)
    replayed = await _call(mcp_b, "chargebee_list_subscriptions", limit=10, offset=cursor)

    assert "error" not in replayed
    assert replayed["list"] == [{"id": "b-row-page-2"}]
    assert tenant_a.calls != tenant_b.calls or len(tenant_b.calls) == 1
    # tenant A's client was never touched by tenant B's request
    assert len(tenant_a.calls) == 1
    assert len(tenant_b.calls) == 1
