"""Subscription (account) lifecycle tools.

Tool naming convention: chargebee_<action>_<resource>
"""

from collections.abc import Callable
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .._json import dump_json_capped, error_envelope
from ..api_client import ChargebeeClient, ChargebeeError
from ._common import (
    NO_CREDS,
    OFFSET_DESC,
    InvalidCursorError,
    decode_cursor,
    list_with_cursor,
    to_request_offset,
)

# Verified against Chargebee's own OpenAPI spec (github.com/chargebee/openapi,
# paths./subscriptions/{subscription-id}/cancel_for_items, checked 2026-08-27).
CancelOption = Literal["immediately", "end_of_term", "specific_date", "end_of_billing_term"]
CreditOption = Literal["none", "prorate", "full", "consumption_based"]
UnbilledChargesOption = Literal["invoice", "delete"]

_MAX_LIMIT = 100  # Chargebee's own documented per_page max


def register(mcp: FastMCP, client_factory: Callable[[], ChargebeeClient | None]) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def chargebee_list_subscriptions(
        limit: Annotated[int, Field(description="Max results per page (1-100, default 10).")] = 10,
        offset: Annotated[str | list[str] | None, Field(description=OFFSET_DESC)] = None,
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
        try:
            chargebee_offset = decode_cursor(offset, "subscriptions")
        except InvalidCursorError as e:
            return error_envelope("invalid_argument", str(e), False)

        async def fetch(page_limit: int) -> dict:
            params: dict = {
                "limit": page_limit,
                "offset": to_request_offset(chargebee_offset),
                "include_deleted": include_deleted,
            }
            if filters:
                params.update(filters)
            return await client.get("/subscriptions", params=params)

        try:
            return await list_with_cursor("subscriptions", fetch, min(limit, _MAX_LIMIT))
        except ChargebeeError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def chargebee_retrieve_subscription(
        subscription_id: Annotated[
            str,
            Field(
                description=(
                    "The subscription's unique ID — NOT the customer_id. These "
                    "are different Chargebee objects (a customer can have "
                    "multiple subscriptions); if you only have a customer_id, "
                    "use chargebee_list_subscriptions with "
                    '{"customer_id[is]": "..."} instead of guessing.'
                )
            ),
        ],
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
            CancelOption | None,
            Field(
                description=(
                    '"immediately" (right now); "end_of_term" (end of the '
                    "CURRENT billing cycle — whatever date that naturally "
                    'falls on, NOT a specific calendar date); "specific_date" '
                    "(a chosen calendar date/time — requires cancel_at; use "
                    'this, not end_of_term, for "cancel at the end of '
                    '[a specific month/date]"); "end_of_billing_term" (end of '
                    "the advance-billed term if billed for future renewals, "
                    "otherwise same as end_of_term)."
                )
            ),
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
            CreditOption | None,
            Field(
                description=(
                    '"none", "prorate", "full", or "consumption_based" — '
                    "how to credit unused charges for the current term."
                )
            ),
        ] = None,
        unbilled_charges_option: Annotated[
            UnbilledChargesOption | None,
            Field(
                description=(
                    '"invoice" or "delete" — how to handle unbilled usage '
                    'charges. Only applies when cancel_option="immediately".'
                )
            ),
        ] = None,
    ) -> str:
        """Cancel a subscription (account).

        ⚠️ DESTRUCTIVE, no undo (no reactivate tool exists here). confirm=true
        is a mechanical gate, NOT proof of user consent — set it only when a
        human operator has explicitly told you, in this conversation, to
        cancel this specific subscription now. A relayed customer request or
        an eligible-looking subscription is not enough; ask the operator to
        confirm first.
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
