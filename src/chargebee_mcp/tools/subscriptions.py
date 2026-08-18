"""Subscription (account) lifecycle tools.

Tool naming convention: chargebee_<action>_<resource>
"""

from collections.abc import Callable
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .._json import dump_json_capped, error_envelope
from ..api_client import ChargebeeClient, ChargebeeError
from ._common import NO_CREDS

_MAX_LIMIT = 100  # Chargebee's own documented per_page max


def register(mcp: FastMCP, client_factory: Callable[[], ChargebeeClient | None]) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def chargebee_list_subscriptions(
        limit: Annotated[int, Field(description="Max results per page (1-100, default 10).")] = 10,
        offset: Annotated[
            str | None, Field(description="Pagination cursor from a previous response's next_offset.")
        ] = None,
        include_deleted: Annotated[
            bool | None, Field(description="Include deleted subscriptions in the results.")
        ] = None,
        filters: Annotated[
            dict[str, str] | None,
            Field(
                description=(
                    "Optional Chargebee compound filter fields, passed through "
                    'as literal query keys, e.g. {"customer_id[is]": "cus123", '
                    '"status[in]": "[\\"active\\",\\"non_renewing\\"]"}. Supported '
                    "fields: id, customer_id, item_id, item_price_id, status, "
                    "cancel_reason, cancel_reason_code, remaining_billing_cycles, "
                    "created_at, activated_at, next_billing_at, cancelled_at, "
                    "has_scheduled_changes, updated_at, offline_payment_method, "
                    "auto_close_invoices, override_relationship, "
                    "business_entity_id, channel, decommissioned. Supported "
                    "operators vary by field type: [is], [is_not], [in], [not_in], "
                    "[between], [after], [before], [on], [none], [is_present]."
                )
            ),
        ] = None,
    ) -> str:
        """List subscriptions (accounts).
        """
        client = client_factory()
        if client is None:
            return NO_CREDS
        params: dict = {
            "limit": min(limit, _MAX_LIMIT),
            "offset": offset,
            "include_deleted": include_deleted,
        }
        if filters:
            params.update(filters)
        try:
            result = await client.get("/subscriptions", params=params)
            return dump_json_capped(result)
        except ChargebeeError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def chargebee_retrieve_subscription(
        subscription_id: Annotated[str, Field(description="The subscription's unique ID.")],
    ) -> str:
        """Retrieve a subscription (account) by ID.
        """
        client = client_factory()
        if client is None:
            return NO_CREDS
        try:
            result = await client.get(f"/subscriptions/{subscription_id}")
            return dump_json_capped(result)
        except ChargebeeError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
    async def chargebee_cancel_subscription(
        subscription_id: Annotated[str, Field(description="The subscription's unique ID.")],
        confirm: Annotated[
            bool, Field(description="Required — must be set to true to proceed.")
        ] = False,
        cancel_option: Annotated[
            str | None, Field(description='"immediately", "end_of_term", or "specific_date".')
        ] = None,
        end_of_term: Annotated[
            bool | None,
            Field(
                description=(
                    'Shorthand for cancel_option="end_of_term" (legacy field, kept for compatibility).'
                )
            ),
        ] = None,
        cancel_at: Annotated[
            int | None,
            Field(
                description='Unix timestamp (seconds) — required when cancel_option="specific_date".'
            ),
        ] = None,
        cancel_reason_code: Annotated[
            str | None,
            Field(description="A reason code configured in your Chargebee site for this cancellation."),
        ] = None,
        credit_option_for_current_term_charges: Annotated[
            str | None,
            Field(
                description=(
                    '"prorate", "full", or "none" — '
                    "how to credit unused charges for the current term."
                )
            ),
        ] = None,
        unbilled_charges_option: Annotated[
            str | None,
            Field(
                description=(
                    '"invoice", "delete", or "carry_forward" — how '
                    "to handle unbilled usage charges."
                )
            ),
        ] = None,
    ) -> str:
        """Cancel a subscription (account).

        ⚠️ DESTRUCTIVE. Requires confirm=true. Ends a paying customer's
        subscription. This service does not include a reactivate tool, so
        use this only when termination is genuinely intended, not to test
        or preview behavior.
        """
        if not confirm:
            return error_envelope(
                "invalid_argument", "destructive operation requires confirm=true", False
            )
        client = client_factory()
        if client is None:
            return NO_CREDS
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
            return dump_json_capped(result)
        except ChargebeeError as e:
            return e.to_envelope()
