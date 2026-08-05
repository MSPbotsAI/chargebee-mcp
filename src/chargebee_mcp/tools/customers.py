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
    async def chargebee_delete_customer(
        customer_id: str,
        delete_payment_method: bool | None = None,
    ) -> str:
        """Delete a customer (company). Chargebee retains a soft-deleted record.

        API: POST /customers/{customer-id}/delete

        Args:
            customer_id: The customer's unique ID.
            delete_payment_method: Also delete the customer's stored payment methods.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        body = {"delete_payment_method": delete_payment_method}
        try:
            result = await client.post(f"/customers/{customer_id}/delete", body)
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_merge_customers(from_customer_id: str, to_customer_id: str) -> str:
        """Merge one customer's data into another, then delete the source customer.

        API: POST /customers/merge

        Args:
            from_customer_id: The customer ID to merge from (will be deleted).
            to_customer_id: The customer ID to merge into (will retain the data).
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        body = {"from_customer_id": from_customer_id, "to_customer_id": to_customer_id}
        try:
            result = await client.post("/customers/merge", body)
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_assign_payment_role(
        customer_id: str, payment_source_id: str, role: str
    ) -> str:
        """Assign a payment source's role (e.g. primary/backup) for a customer.

        API: POST /customers/{customer-id}/assign_payment_role

        Args:
            customer_id: The customer's unique ID.
            payment_source_id: The payment source ID to assign the role to.
            role: The role to assign — "primary" or "backup".
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        body = {"payment_source_id": payment_source_id, "role": role}
        try:
            result = await client.post(f"/customers/{customer_id}/assign_payment_role", body)
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_get_customer_hierarchy(
        customer_id: str, hierarchy_operation_type: str
    ) -> str:
        """Get the account hierarchy (parent/child relationships) for a customer.

        API: GET /customers/{customer-id}/hierarchy

        Args:
            customer_id: The customer's unique ID.
            hierarchy_operation_type: Required. Either "self_and_ancestors" or
                "self_and_immediate_children" — which part of the hierarchy to return.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        try:
            result = await client.get(
                f"/customers/{customer_id}/hierarchy",
                params={"hierarchy_operation_type": hierarchy_operation_type},
            )
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

    @mcp.tool()
    async def chargebee_add_customer_contact(
        customer_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        label: str | None = None,
        enabled: bool | None = None,
        send_account_email: bool | None = None,
        send_billing_email: bool | None = None,
    ) -> str:
        """Add a contact (person) to a customer (company).

        API: POST /customers/{customer-id}/add_contact

        Args:
            customer_id: The customer's unique ID.
            first_name: Contact's first name.
            last_name: Contact's last name.
            email: Contact's email address.
            phone: Contact's phone number.
            label: A label for this contact (e.g. "Billing", "Technical").
            enabled: Whether this contact is active (default true).
            send_account_email: Whether this contact receives account emails.
            send_billing_email: Whether this contact receives billing emails.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        contact = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "label": label,
            "enabled": enabled,
            "send_account_email": send_account_email,
            "send_billing_email": send_billing_email,
        }
        body = {"contact": {k: v for k, v in contact.items() if v is not None}}
        try:
            result = await client.post(f"/customers/{customer_id}/add_contact", body)
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_update_customer_contact(
        customer_id: str,
        contact_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        label: str | None = None,
        enabled: bool | None = None,
        send_account_email: bool | None = None,
        send_billing_email: bool | None = None,
    ) -> str:
        """Update an existing contact (person) on a customer (company).

        API: POST /customers/{customer-id}/update_contact

        Args:
            customer_id: The customer's unique ID.
            contact_id: The contact's unique ID (from list_customer_contacts).
            first_name: Contact's first name.
            last_name: Contact's last name.
            email: Contact's email address.
            phone: Contact's phone number.
            label: A label for this contact.
            enabled: Whether this contact is active.
            send_account_email: Whether this contact receives account emails.
            send_billing_email: Whether this contact receives billing emails.
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        contact = {
            "id": contact_id,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "label": label,
            "enabled": enabled,
            "send_account_email": send_account_email,
            "send_billing_email": send_billing_email,
        }
        body = {"contact": {k: v for k, v in contact.items() if v is not None}}
        try:
            result = await client.post(f"/customers/{customer_id}/update_contact", body)
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def chargebee_delete_customer_contact(customer_id: str, contact_id: str) -> str:
        """Delete a contact (person) from a customer (company).

        API: POST /customers/{customer-id}/delete_contact

        Args:
            customer_id: The customer's unique ID.
            contact_id: The contact's unique ID (from list_customer_contacts).
        """
        client = client_factory()
        if client is None:
            return _NO_CREDS
        body = {"contact": {"id": contact_id}}
        try:
            result = await client.post(f"/customers/{customer_id}/delete_contact", body)
            return json.dumps(result, indent=2)
        except ChargebeeError as e:
            return f"Error: {e}"
