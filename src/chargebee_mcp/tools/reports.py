"""Report / financial document lookup tools (invoices, transactions).

Tool naming convention: chargebee_<action>_<resource>
"""

from collections.abc import Callable
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .._json import dump_json_capped
from ..api_client import ChargebeeClient, ChargebeeError
from ._common import NO_CREDS

_MAX_LIMIT = 100  # Chargebee's own documented per_page max


def register(mcp: FastMCP, client_factory: Callable[[], ChargebeeClient | None]) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def chargebee_list_invoices(
        limit: Annotated[int, Field(description="Max results per page (1-100, default 10).")] = 10,
        offset: Annotated[
            str | None, Field(description="Pagination cursor from a previous response's next_offset.")
        ] = None,
        include_deleted: Annotated[
            bool | None, Field(description="Include deleted invoices in the results.")
        ] = None,
        filters: Annotated[
            dict[str, str] | None,
            Field(
                description=(
                    "Optional Chargebee compound filter fields, passed through "
                    'as literal query keys, e.g. {"customer_id[is]": "cus123", '
                    '"status[in]": "[\\"paid\\",\\"payment_due\\"]", '
                    '"date[after]": "1700000000"}. Supported fields: id, '
                    "subscription_id, customer_id, recurring, status, price_type, "
                    "date, paid_at, total, amount_paid, amount_adjusted, "
                    "credits_applied, amount_due, dunning_status, payment_owner, "
                    "updated_at, channel, voided_at, void_reason_code, exclude, "
                    "einvoice. Supported operators vary by field type: [is], "
                    "[is_not], [in], [not_in], [between], [after], [before], [on], "
                    "[none], [is_present]."
                )
            ),
        ] = None,
    ) -> str:
        """List invoices.

        Invoices are billing documents — what was charged to the customer (paid,
        pending, or overdue). To check whether a payment/refund actually went
        through, use chargebee_list_transactions instead.
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
            result = await client.get("/invoices", params=params)
            return dump_json_capped(result)
        except ChargebeeError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def chargebee_list_transactions(
        limit: Annotated[int, Field(description="Max results per page (1-100, default 10).")] = 10,
        offset: Annotated[
            str | None, Field(description="Pagination cursor from a previous response's next_offset.")
        ] = None,
        include_deleted: Annotated[
            bool | None, Field(description="Include deleted transactions in the results.")
        ] = None,
        filters: Annotated[
            dict[str, str] | None,
            Field(
                description=(
                    "Optional Chargebee compound filter fields, passed through "
                    'as literal query keys, e.g. {"customer_id[is]": "cus123", '
                    '"type[is]": "payment", "date[after]": "1700000000"}. Supported '
                    "fields: id, customer_id, subscription_id, payment_source_id, "
                    "payment_method, gateway, gateway_account_id, id_at_gateway, "
                    "reference_number, type, date, amount, amount_capturable, "
                    "status, updated_at. Supported operators vary by field type: "
                    "[is], [is_not], [in], [not_in], [between], [after], [before], "
                    "[on], [none], [is_present]."
                )
            ),
        ] = None,
    ) -> str:
        """List payment/refund transactions.

        Transactions are the actual payment/refund attempts and their settlement
        outcome (success, failure, etc.) against a gateway. For what was billed
        in the first place (the invoice document), use chargebee_list_invoices.
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
            result = await client.get("/transactions", params=params)
            return dump_json_capped(result)
        except ChargebeeError as e:
            return e.to_envelope()
