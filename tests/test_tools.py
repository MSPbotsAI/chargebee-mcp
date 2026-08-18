"""tools/list snapshot + error-envelope mapping tests.

No network calls: tool enumeration goes through FastMCP's in-process
list_tools(), and the error-code mapping is tested directly against
ChargebeeError, independent of any real HTTP request.
"""

import json

import pytest

from chargebee_mcp.api_client import ChargebeeError
from chargebee_mcp.config import Settings
from chargebee_mcp.server import create_mcp_server

EXPECTED_REQUIRED = {
    "chargebee_list_customers": set(),
    "chargebee_create_customer": set(),
    "chargebee_retrieve_customer": {"customer_id"},
    "chargebee_update_customer": {"customer_id"},
    "chargebee_list_customer_contacts": {"customer_id"},
    "chargebee_list_subscriptions": set(),
    "chargebee_retrieve_subscription": {"subscription_id"},
    "chargebee_cancel_subscription": {"subscription_id"},
    "chargebee_list_invoices": set(),
    "chargebee_list_transactions": set(),
}

READ_ONLY_TOOLS = {
    "chargebee_list_customers",
    "chargebee_retrieve_customer",
    "chargebee_list_customer_contacts",
    "chargebee_list_subscriptions",
    "chargebee_retrieve_subscription",
    "chargebee_list_invoices",
    "chargebee_list_transactions",
}
IDEMPOTENT_TOOLS = {"chargebee_update_customer"}
DESTRUCTIVE_TOOLS = {"chargebee_cancel_subscription"}
# chargebee_create_customer is intentionally left without an annotation:
# it's neither read-only, idempotent, nor destructive.
NO_ANNOTATION_TOOLS = {"chargebee_create_customer"}


@pytest.mark.asyncio
async def test_tools_list_snapshot():
    mcp = create_mcp_server(Settings())
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == set(EXPECTED_REQUIRED), f"unexpected tool set: {names}"

    by_name = {t.name: t for t in tools}
    for name, expected_required in EXPECTED_REQUIRED.items():
        tool = by_name[name]
        required = set(tool.inputSchema.get("required", []))
        assert required == expected_required, f"{name}: required={required}"

        assert len(tool.description or "") <= 500, f"{name}: description too long"
        first_line = (tool.description or "").strip().splitlines()[0]
        assert len(first_line) <= 100, f"{name}: first line too long: {first_line!r}"

        annotations = tool.annotations
        if name in READ_ONLY_TOOLS:
            assert annotations is not None and annotations.readOnlyHint is True, name
        elif name in IDEMPOTENT_TOOLS:
            assert annotations is not None and annotations.idempotentHint is True, name
        elif name in DESTRUCTIVE_TOOLS:
            assert annotations is not None and annotations.destructiveHint is True, name
        elif name in NO_ANNOTATION_TOOLS:
            assert annotations is None or (
                not annotations.readOnlyHint
                and not annotations.destructiveHint
                and not annotations.idempotentHint
            ), name


@pytest.mark.asyncio
async def test_service_instructions_present_and_bounded():
    mcp = create_mcp_server(Settings())
    assert mcp.instructions
    assert len(mcp.instructions) <= 1500


@pytest.mark.parametrize(
    "status_code,expected_code,expected_retryable",
    [
        (0, "upstream_error", True),
        (400, "invalid_argument", False),
        (401, "unauthorized", False),
        (403, "unauthorized", False),
        (404, "not_found", False),
        (422, "invalid_argument", False),
        (429, "rate_limited", True),
        (500, "upstream_error", True),
        (503, "upstream_error", True),
    ],
)
def test_error_envelope_mapping(status_code, expected_code, expected_retryable):
    err = ChargebeeError(status_code, "boom")
    envelope = json.loads(err.to_envelope())
    assert envelope["error"]["code"] == expected_code
    assert envelope["error"]["retryable"] is expected_retryable
    assert envelope["error"]["message"] == "boom"
