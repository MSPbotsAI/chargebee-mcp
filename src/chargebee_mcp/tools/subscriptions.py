"""Subscription (account) lifecycle tools.

Tool naming convention: chargebee_<action>_<resource>
"""

import json
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from ..api_client import ChargebeeClient, ChargebeeError

_NO_CREDS = (
    "Error: No Chargebee credentials configured. Set CHARGEBEE_SITE/CHARGEBEE_API_KEY "
    "or use AUTH_MODE=gateway."
)


def register(mcp: FastMCP, client_factory: Callable[[], ChargebeeClient | None]) -> None:
    @mcp.tool()
    async def chargebee_list_subscriptions(
        limit: int = 10,
        offset: str | None = None,
        include_deleted: bool | None = None,
        filters: dict[str, str] | None = None,
    ) -> str:
        """List subscriptions (accounts).

        API: GET /subscriptions

        Args:
            limit: Max results per page (1-100, default 10).
            offset: Pagination cursor from a previous response's next_offset.
            include_deleted: Include deleted subscriptions in the results.
            filters: Optional Chargebee compound filter fields, passed through
                as literal query keys, e.g. {"customer_id[is]": "cus123",
                "status[in]": "[\\"active\\",\\"non_renewing\\"]"}. Supported
                fields: id, customer_id, item_id, item_price_id, status,
                cancel_reason, cancel_reason_code, remaining_billing_cycles,
                created_at, activated_at, next_billing_at, cancelled_at,
                has_scheduled_changes, updated_at, offline_payment_method,
                auto_close_invoices, override_relationship,
                business_entity_id, channel, decommissioned. Supported
                operators vary by field type: [is], [is_not], [in], [not_in],
                [between], [after], [before], [on], [none], [is_present].
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        params: dict = {"limit": limit, "offset": offset, "include_deleted": include_deleted}
        if filters:
            params.update(filters)
        try:
            result = await client.get("/subscriptions", params=params)
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_retrieve_subscription(subscription_id: str) -> str:
        """Retrieve a subscription (account) by ID.

        API: GET /subscriptions/{subscription-id}

        Args:
            subscription_id: The subscription's unique ID.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        try:
            result = await client.get(f"/subscriptions/{subscription_id}")
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_cancel_subscription(
        subscription_id: str,
        cancel_option: str | None = None,
        end_of_term: bool | None = None,
        cancel_at: int | None = None,
        cancel_reason_code: str | None = None,
        credit_option_for_current_term_charges: str | None = None,
        unbilled_charges_option: str | None = None,
    ) -> str:
        """Cancel a subscription (account).

        API: POST /subscriptions/{subscription-id}/cancel_for_items

        Args:
            subscription_id: The subscription's unique ID.
            cancel_option: "immediately", "end_of_term", or "specific_date".
            end_of_term: Shorthand for cancel_option="end_of_term" (legacy field, kept for compatibility).
            cancel_at: Unix timestamp (seconds) — required when cancel_option="specific_date".
            cancel_reason_code: A reason code configured in your Chargebee site for this cancellation.
            credit_option_for_current_term_charges: "prorate", "full", or "none" —
                how to credit unused charges for the current term.
            unbilled_charges_option: "invoice", "delete", or "carry_forward" — how
                to handle unbilled usage charges.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        body = {
            "cancel_option": cancel_option,
            "end_of_term": end_of_term,
            "cancel_at": cancel_at,
            "cancel_reason_code": cancel_reason_code,
            "credit_option_for_current_term_charges": credit_option_for_current_term_charges,
            "unbilled_charges_option": unbilled_charges_option,
        }
        try:
            result = await client.post(f"/subscriptions/{subscription_id}/cancel_for_items", body)
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"
