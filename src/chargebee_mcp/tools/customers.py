"""Customer (company) + contact (personnel) tools.

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
    async def chargebee_list_customers(
        limit: int = 10,
        offset: str | None = None,
        include_deleted: bool | None = None,
        filters: dict[str, str] | None = None,
    ) -> str:
        """List customers (companies).

        API: GET /customers

        Args:
            limit: Max results per page (1-100, default 10).
            offset: Pagination cursor from a previous response's next_offset.
            include_deleted: Include deleted customers in the results.
            filters: Optional Chargebee compound filter fields, passed through
                as literal query keys, e.g. {"email[is]": "a@b.com",
                "company[is]": "Acme", "created_at[after]": "1700000000"}.
                Supported fields: id, first_name, last_name, email, company,
                phone, auto_collection, taxability, created_at, updated_at,
                offline_payment_method, auto_close_invoices, channel,
                business_entity_id, relationship. Supported operators vary by
                field type: [is], [is_not], [starts_with], [in], [not_in],
                [between], [after], [before], [on], [none], [is_present].
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        params: dict = {"limit": limit, "offset": offset, "include_deleted": include_deleted}
        if filters:
            params.update(filters)
        try:
            result = await client.get("/customers", params=params)
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_create_customer(
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        company: str | None = None,
        phone: str | None = None,
        id: str | None = None,
        auto_collection: str | None = None,
        taxability: str | None = None,
        locale: str | None = None,
        meta_data: dict | None = None,
        billing_address: dict | None = None,
    ) -> str:
        """Create a customer (company).

        API: POST /customers

        Args:
            first_name: Customer's first name.
            last_name: Customer's last name.
            email: Customer's email address.
            company: Company name.
            phone: Phone number.
            id: Optional custom customer ID (auto-generated if omitted).
            auto_collection: "on" or "off" — whether invoices are auto-collected.
            taxability: "taxable" or "exempt".
            locale: Customer's locale (e.g. "en", "fr-CA").
            meta_data: Arbitrary key-value metadata dict.
            billing_address: Billing address fields, e.g. {"line1": "...",
                "city": "...", "state": "...", "zip": "...", "country": "US"}.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
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
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_retrieve_customer(customer_id: str) -> str:
        """Retrieve a customer (company) by ID.

        API: GET /customers/{customer-id}

        Args:
            customer_id: The customer's unique ID.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        try:
            result = await client.get(f"/customers/{customer_id}")
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_update_customer(
        customer_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        company: str | None = None,
        phone: str | None = None,
        auto_collection: str | None = None,
        taxability: str | None = None,
        locale: str | None = None,
        invoice_notes: str | None = None,
        meta_data: dict | None = None,
    ) -> str:
        """Update a customer (company).

        API: POST /customers/{customer-id}

        Args:
            customer_id: The customer's unique ID.
            first_name: Customer's first name.
            last_name: Customer's last name.
            email: Customer's email address.
            company: Company name.
            phone: Phone number.
            auto_collection: "on" or "off".
            taxability: "taxable" or "exempt".
            locale: Customer's locale.
            invoice_notes: Default notes shown on the customer's invoices.
            meta_data: Arbitrary key-value metadata dict.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
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
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_list_customer_contacts(
        customer_id: str, limit: int = 10, offset: str | None = None
    ) -> str:
        """List the contacts (personnel) associated with a customer (company).

        API: GET /customers/{customer-id}/contacts

        Args:
            customer_id: The customer's unique ID.
            limit: Max results per page (1-100, default 10).
            offset: Pagination cursor from a previous response's next_offset.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        try:
            result = await client.get(
                f"/customers/{customer_id}/contacts", params={"limit": limit, "offset": offset}
            )
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"
