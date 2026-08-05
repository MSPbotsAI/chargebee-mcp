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
    async def chargebee_create_subscription(
        customer_id: str,
        subscription_items: list[dict] | None = None,
        id: str | None = None,
        start_date: int | None = None,
        trial_end: int | None = None,
        auto_collection: str | None = None,
        po_number: str | None = None,
        coupon_ids: list[str] | None = None,
        payment_source_id: str | None = None,
        invoice_immediately: bool | None = None,
        meta_data: dict | None = None,
    ) -> str:
        """Create a subscription (account) for an existing customer.

        API: POST /customers/{customer-id}/subscription_for_items

        Args:
            customer_id: The customer's unique ID to create the subscription under.
            subscription_items: Required for a real subscription. A list of item
                dicts, e.g. [{"item_price_id": "basic-USD-monthly", "quantity": 1}].
                Each dict may include: item_price_id (required), quantity,
                unit_price, billing_cycles, trial_end, charge_on_event,
                charge_on_option, service_period_days, item_type.
            id: Optional custom subscription ID (auto-generated if omitted).
            start_date: Unix timestamp (seconds) to start the subscription in the future.
            trial_end: Unix timestamp (seconds) for the trial period to end.
            auto_collection: "on" or "off".
            po_number: Purchase order number to record on the subscription.
            coupon_ids: List of coupon ID strings to apply.
            payment_source_id: Payment source ID to use for this subscription.
            invoice_immediately: Generate an invoice immediately upon creation.
            meta_data: Arbitrary key-value metadata dict.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        body = {
            "id": id,
            "start_date": start_date,
            "trial_end": trial_end,
            "auto_collection": auto_collection,
            "po_number": po_number,
            "coupon_ids": coupon_ids,
            "payment_source_id": payment_source_id,
            "invoice_immediately": invoice_immediately,
            "meta_data": meta_data,
            "subscription_items": subscription_items,
        }
        try:
            result = await client.post(f"/customers/{customer_id}/subscription_for_items", body)
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_update_subscription(
        subscription_id: str,
        subscription_items: list[dict] | None = None,
        replace_items_list: bool | None = None,
        coupon_ids: list[str] | None = None,
        replace_coupon_list: bool | None = None,
        prorate: bool | None = None,
        end_of_term: bool | None = None,
        invoice_immediately: bool | None = None,
        po_number: str | None = None,
        meta_data: dict | None = None,
    ) -> str:
        """Update an existing subscription (account) — change items, coupons, etc.

        API: POST /subscriptions/{subscription-id}/update_for_items

        Args:
            subscription_id: The subscription's unique ID.
            subscription_items: Items to add/change. A list of item dicts, e.g.
                [{"item_price_id": "basic-USD-monthly", "quantity": 1}]. Each
                dict may include: item_price_id (required), quantity,
                unit_price, billing_cycles, trial_end, charge_on_event,
                charge_on_option, service_period_days, item_type.
            replace_items_list: If true, subscription_items replaces the full
                item list instead of merging with existing items.
            coupon_ids: List of coupon ID strings to apply.
            replace_coupon_list: If true, coupon_ids replaces the full coupon list.
            prorate: Whether to prorate charges for the change.
            end_of_term: Apply the change at the end of the current term instead of immediately.
            invoice_immediately: Generate an invoice immediately for this change.
            po_number: Purchase order number to record on the subscription.
            meta_data: Arbitrary key-value metadata dict.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        body = {
            "replace_items_list": replace_items_list,
            "coupon_ids": coupon_ids,
            "replace_coupon_list": replace_coupon_list,
            "prorate": prorate,
            "end_of_term": end_of_term,
            "invoice_immediately": invoice_immediately,
            "po_number": po_number,
            "meta_data": meta_data,
            "subscription_items": subscription_items,
        }
        try:
            result = await client.post(f"/subscriptions/{subscription_id}/update_for_items", body)
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

    @mcp.tool()
    async def chargebee_pause_subscription(
        subscription_id: str,
        pause_option: str | None = None,
        pause_date: int | None = None,
        resume_date: int | None = None,
        unbilled_charges_handling: str | None = None,
    ) -> str:
        """Pause a subscription (account).

        API: POST /subscriptions/{subscription-id}/pause

        Args:
            subscription_id: The subscription's unique ID.
            pause_option: "immediately" or "end_of_term".
            pause_date: Unix timestamp (seconds) for a scheduled pause.
            resume_date: Unix timestamp (seconds) to auto-resume; leave unset to pause indefinitely.
            unbilled_charges_handling: "invoice" or "delete" — how to handle unbilled charges.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        body = {
            "pause_option": pause_option,
            "pause_date": pause_date,
            "resume_date": resume_date,
            "unbilled_charges_handling": unbilled_charges_handling,
        }
        try:
            result = await client.post(f"/subscriptions/{subscription_id}/pause", body)
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_resume_subscription(
        subscription_id: str,
        resume_option: str | None = None,
        resume_date: int | None = None,
        charges_handling: str | None = None,
    ) -> str:
        """Resume a paused subscription (account).

        API: POST /subscriptions/{subscription-id}/resume

        Args:
            subscription_id: The subscription's unique ID.
            resume_option: "immediately" or "specific_date".
            resume_date: Unix timestamp (seconds) — required when resume_option="specific_date".
            charges_handling: "full_charges_on_resume", "no_charges_on_resume", or
                "schedule_charges_on_resume_date" — how to handle unpaid charges from the pause period.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        body = {
            "resume_option": resume_option,
            "resume_date": resume_date,
            "charges_handling": charges_handling,
        }
        try:
            result = await client.post(f"/subscriptions/{subscription_id}/resume", body)
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_reactivate_subscription(
        subscription_id: str,
        trial_end: int | None = None,
        billing_cycles: int | None = None,
        invoice_immediately: bool | None = None,
    ) -> str:
        """Reactivate a cancelled subscription (account).

        API: POST /subscriptions/{subscription-id}/reactivate

        Args:
            subscription_id: The subscription's unique ID.
            trial_end: Unix timestamp (seconds) for a new trial period to end.
            billing_cycles: Number of billing cycles for a contract term, if applicable.
            invoice_immediately: Generate an invoice immediately upon reactivation.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        body = {
            "trial_end": trial_end,
            "billing_cycles": billing_cycles,
            "invoice_immediately": invoice_immediately,
        }
        try:
            result = await client.post(f"/subscriptions/{subscription_id}/reactivate", body)
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_change_subscription_term_end(
        subscription_id: str,
        term_ends_at: int,
        prorate: bool | None = None,
        invoice_immediately: bool | None = None,
    ) -> str:
        """Change the current term's end date for a subscription (account).

        API: POST /subscriptions/{subscription-id}/change_term_end

        Args:
            subscription_id: The subscription's unique ID.
            term_ends_at: Required. Unix timestamp (seconds) for the new term end date.
            prorate: Whether to prorate charges for the term length change.
            invoice_immediately: Generate an invoice immediately for this change.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        body = {
            "term_ends_at": term_ends_at,
            "prorate": prorate,
            "invoice_immediately": invoice_immediately,
        }
        try:
            result = await client.post(f"/subscriptions/{subscription_id}/change_term_end", body)
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_retrieve_subscription_with_scheduled_changes(subscription_id: str) -> str:
        """Retrieve a subscription (account) along with any changes scheduled
        to take effect at a future date (e.g. pending plan/quantity changes).

        API: GET /subscriptions/{subscription-id}/retrieve_with_scheduled_changes

        Args:
            subscription_id: The subscription's unique ID.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        try:
            result = await client.get(
                f"/subscriptions/{subscription_id}/retrieve_with_scheduled_changes"
            )
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"
