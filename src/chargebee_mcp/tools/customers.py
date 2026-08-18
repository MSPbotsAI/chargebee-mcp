"""Customer (company) + contact (personnel) tools.

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
    async def chargebee_list_customers(
        limit: Annotated[int, Field(description="Max results per page (1-100, default 10).")] = 10,
        offset: Annotated[
            str | None, Field(description="Pagination cursor from a previous response's next_offset.")
        ] = None,
        include_deleted: Annotated[
            bool | None, Field(description="Include deleted customers in the results.")
        ] = None,
        filters: Annotated[
            dict[str, str] | None,
            Field(
                description=(
                    "Optional Chargebee compound filter fields, passed through "
                    'as literal query keys, e.g. {"email[is]": "a@b.com", '
                    '"company[is]": "Acme", "created_at[after]": "1700000000"}. '
                    "Supported fields: id, first_name, last_name, email, company, "
                    "phone, auto_collection, taxability, created_at, updated_at, "
                    "offline_payment_method, auto_close_invoices, channel, "
                    "business_entity_id, relationship. Supported operators vary by "
                    "field type: [is], [is_not], [starts_with], [in], [not_in], "
                    "[between], [after], [before], [on], [none], [is_present]."
                )
            ),
        ] = None,
    ) -> str:
        """List customers (companies).
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
            result = await client.get("/customers", params=params)
            return dump_json_capped(result)
        except ChargebeeError as e:
            return e.to_envelope()

    @mcp.tool()
    async def chargebee_create_customer(
        first_name: Annotated[str | None, Field(description="Customer's first name.")] = None,
        last_name: Annotated[str | None, Field(description="Customer's last name.")] = None,
        email: Annotated[str | None, Field(description="Customer's email address.")] = None,
        company: Annotated[str | None, Field(description="Company name.")] = None,
        phone: Annotated[str | None, Field(description="Phone number.")] = None,
        id: Annotated[
            str | None, Field(description="Optional custom customer ID (auto-generated if omitted).")
        ] = None,
        auto_collection: Annotated[
            str | None, Field(description='"on" or "off" — whether invoices are auto-collected.')
        ] = None,
        taxability: Annotated[str | None, Field(description='"taxable" or "exempt".')] = None,
        locale: Annotated[
            str | None, Field(description='Customer\'s locale (e.g. "en", "fr-CA").')
        ] = None,
        meta_data: Annotated[dict | None, Field(description="Arbitrary key-value metadata dict.")] = None,
        billing_address: Annotated[
            dict | None,
            Field(
                description=(
                    'Billing address fields, e.g. {"line1": "...", '
                    '"city": "...", "state": "...", "zip": "...", "country": "US"}.'
                )
            ),
        ] = None,
    ) -> str:
        """Create a customer (company).

        Chargebee does not require any single field to create a customer —
        every field here is genuinely optional at the API level, and an
        empty call succeeds. In practice, pass at least email or
        first_name/last_name so the resulting customer can be identified
        and matched later.
        """
        client = client_factory()
        if client is None:
            return NO_CREDS
        body = {
            "id": id,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "company": company,
            "phone": phone,
            "auto_collection": auto_collection,
            "taxability": taxability,
            "locale": locale,
            "meta_data": meta_data,
            "billing_address": billing_address,
        }
        try:
            result = await client.post("/customers", body)
            return dump_json_capped(result)
        except ChargebeeError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def chargebee_retrieve_customer(
        customer_id: Annotated[str, Field(description="The customer's unique ID.")],
    ) -> str:
        """Retrieve a customer (company) by ID.
        """
        client = client_factory()
        if client is None:
            return NO_CREDS
        try:
            result = await client.get(f"/customers/{customer_id}")
            return dump_json_capped(result)
        except ChargebeeError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
    async def chargebee_update_customer(
        customer_id: Annotated[str, Field(description="The customer's unique ID.")],
        first_name: Annotated[str | None, Field(description="Customer's first name.")] = None,
        last_name: Annotated[str | None, Field(description="Customer's last name.")] = None,
        email: Annotated[str | None, Field(description="Customer's email address.")] = None,
        company: Annotated[str | None, Field(description="Company name.")] = None,
        phone: Annotated[str | None, Field(description="Phone number.")] = None,
        auto_collection: Annotated[str | None, Field(description='"on" or "off".')] = None,
        taxability: Annotated[str | None, Field(description='"taxable" or "exempt".')] = None,
        locale: Annotated[str | None, Field(description="Customer's locale.")] = None,
        invoice_notes: Annotated[
            str | None, Field(description="Default notes shown on the customer's invoices.")
        ] = None,
        meta_data: Annotated[dict | None, Field(description="Arbitrary key-value metadata dict.")] = None,
    ) -> str:
        """Update a customer (company).
        """
        client = client_factory()
        if client is None:
            return NO_CREDS
        body = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "company": company,
            "phone": phone,
            "auto_collection": auto_collection,
            "taxability": taxability,
            "locale": locale,
            "invoice_notes": invoice_notes,
            "meta_data": meta_data,
        }
        try:
            result = await client.post(f"/customers/{customer_id}", body)
            return dump_json_capped(result)
        except ChargebeeError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def chargebee_list_customer_contacts(
        customer_id: Annotated[str, Field(description="The customer's unique ID.")],
        limit: Annotated[int, Field(description="Max results per page (1-100, default 10).")] = 10,
        offset: Annotated[
            str | None, Field(description="Pagination cursor from a previous response's next_offset.")
        ] = None,
    ) -> str:
        """List the contacts (personnel) associated with a customer (company).
        """
        client = client_factory()
        if client is None:
            return NO_CREDS
        try:
            result = await client.get(
                f"/customers/{customer_id}/contacts",
                params={"limit": min(limit, _MAX_LIMIT), "offset": offset},
            )
            return dump_json_capped(result)
        except ChargebeeError as e:
            return e.to_envelope()
