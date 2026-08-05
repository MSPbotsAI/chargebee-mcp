"""Payment source (account payment method) tools.

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
    async def chargebee_list_payment_sources(
        limit: int = 10,
        offset: str | None = None,
        subscription_id: str | None = None,
        include_deleted: bool | None = None,
        filters: dict[str, str] | None = None,
    ) -> str:
        """List payment sources (stored payment methods).

        API: GET /payment_sources

        Args:
            limit: Max results per page (1-100, default 10).
            offset: Pagination cursor from a previous response's next_offset.
            subscription_id: Filter to payment sources linked to this subscription.
            include_deleted: Include deleted payment sources in the results.
            filters: Optional Chargebee compound filter fields, passed through
                as literal query keys, e.g. {"customer_id[is]": "cus123",
                "type[in]": "[\\"card\\",\\"bank_account\\"]"}. Supported fields:
                customer_id, type, status, updated_at, created_at. Supported
                operators vary by field type: [is], [is_not], [in], [not_in],
                [between], [after], [before], [on], [none], [is_present].
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        params: dict = {
            "limit": limit,
            "offset": offset,
            "subscription_id": subscription_id,
            "include_deleted": include_deleted,
        }
        if filters:
            params.update(filters)
        try:
            result = await client.get("/payment_sources", params=params)
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_create_card_payment_source(
        customer_id: str,
        card: dict,
        replace_primary_payment_source: bool | None = None,
    ) -> str:
        """Add a card payment source to a customer's account.

        API: POST /payment_sources/create_card

        Args:
            customer_id: Required. The customer's unique ID to attach the card to.
            card: Required. Card details dict, e.g. {"number": "4111111111111111",
                "expiry_month": 12, "expiry_year": 2030, "cvv": "123",
                "first_name": "Jane", "last_name": "Doe"}. Use only on a test
                site with test card numbers, or via a tokenized flow in production
                — Chargebee's own guidance is to avoid sending raw card numbers
                from a server you control whenever possible.
            replace_primary_payment_source: Whether this becomes the customer's
                new primary payment source.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        body = {
            "customer_id": customer_id,
            "card": card,
            "replace_primary_payment_source": replace_primary_payment_source,
        }
        try:
            result = await client.post("/payment_sources/create_card", body)
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_update_card_payment_source(
        payment_source_id: str,
        card: dict,
    ) -> str:
        """Update the card details on an existing payment source.

        API: POST /payment_sources/{cust-payment-source-id}/update_card

        Args:
            payment_source_id: The payment source's unique ID.
            card: Required. Card fields to update, e.g. {"expiry_month": 12,
                "expiry_year": 2031}.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        body = {"card": card}
        try:
            result = await client.post(
                f"/payment_sources/{payment_source_id}/update_card", body
            )
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_delete_payment_source(payment_source_id: str) -> str:
        """Delete a payment source (stored payment method).

        API: POST /payment_sources/{cust-payment-source-id}/delete

        Args:
            payment_source_id: The payment source's unique ID.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        try:
            result = await client.post(f"/payment_sources/{payment_source_id}/delete")
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"
