# chargebee-mcp

Chargebee MCP Service — a stateless HTTP MCP server wrapping the [Chargebee REST API v2](https://apidocs.chargebee.com/docs/api/) for account/customer management use cases (company records, personnel/contacts, subscription lifecycle, payment sources, and financial reporting lookups).

**Tech stack:** Python 3.12 + uv + FastMCP (Starlette/Uvicorn)

## Scope

Chargebee's official [MCP Server](https://www.chargebee.com/docs/billing/2.0/ai-in-chargebee/chargebee-mcp) offering (the "Data Lookup MCP Server") was evaluated first and found unsuitable as a replacement: it is read-only, covers roughly a dozen resource categories, and is missing Coupons, the Item/Item Price/Item Family product-catalog resources, and Upcoming Invoice Estimates entirely — none of which can be added on top of it. This service instead wraps the full Chargebee REST API directly.

Out of Chargebee's ~438 REST API operations across 77 resources, this service implements **30 tools** selected for account/company/personnel/report management use cases:

| Category | Count | Resources |
|---|---|---|
| Company (Customer) | 8 | create/retrieve/update/delete/list/merge, payment role assignment, account hierarchy |
| Personnel (Customer Contacts) | 4 | list/add/update/delete contacts under a customer |
| Account (Subscription lifecycle) | 10 | create/retrieve/update/list, cancel/pause/resume/reactivate, term-end change, scheduled changes |
| Account (Payment Sources) | 4 | list/create(card)/update(card)/delete |
| Report (Invoices/Transactions/Credit Notes) | 4 | list invoices, retrieve invoice, list transactions, list credit notes |

## Quick Start

```powershell
# Install dependencies
cd D:\claude\project\chargebee-mcp
uv sync

# Run in stdio mode (for Claude Desktop)
$env:CHARGEBEE_SITE="your-site"
$env:CHARGEBEE_API_KEY="your_api_key"
uv run chargebee-mcp
```

## Configuration

Copy `.env.example` to `.env` and fill in your values:

| Variable | Default | Description |
|----------|---------|--------------|
| `CHARGEBEE_SITE` | — | Chargebee site name (the subdomain in `https://{site}.chargebee.com`) |
| `CHARGEBEE_API_KEY` | — | Chargebee API key |
| `AUTH_MODE` | `gateway` | `gateway` = site + API key per-request via headers (SOP-compliant); `env` = shared credentials from env vars (local dev only) |
| `MCP_TRANSPORT` | `stdio` | `stdio` (Claude Desktop) or `http` (gateway) |
| `MCP_HTTP_PORT` | `8080` | HTTP server port |

Get your API key: Chargebee Billing → Settings → Configure Chargebee → API Keys and Webhooks → API Keys tab.

## HEADER 授权参数说明

Gateway 模式下，每个请求必须携带以下两个 HTTP Header：

| Header | 类型 | 是否必填 | 默认值 | 枚举值 | 字段描述 | Example |
|---|---|---|---|---|---|---|
| `X-Chargebee-Site` | string | 是 | 无 | 无 | Chargebee site 名称（即 `https://{site}.chargebee.com` 里的子域名部分） | `acme-test` |
| `X-Chargebee-Api-Key` | string | 是 | 无 | 无 | Chargebee API Key（Settings → Configure Chargebee → API Keys and Webhooks 页面生成），本服务用其作为 HTTP Basic Auth 的用户名、密码留空 | `test_XXXXXXXXXXXXXXXXXXXXXXXXXXXXX` |

## Claude Desktop Setup

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "chargebee": {
      "command": "uv",
      "args": ["run", "--directory", "D:/claude/project/chargebee-mcp", "chargebee-mcp"],
      "env": {
        "CHARGEBEE_SITE": "your-site",
        "CHARGEBEE_API_KEY": "your_api_key"
      }
    }
  }
}
```

## Transport Modes

### stdio (Claude Desktop / CLI)
```powershell
$env:CHARGEBEE_SITE="your-site"
$env:CHARGEBEE_API_KEY="your_api_key"
uv run chargebee-mcp
```

### HTTP — single-tenant
```powershell
$env:CHARGEBEE_SITE="your-site"
$env:CHARGEBEE_API_KEY="your_api_key"
$env:MCP_TRANSPORT="http"
$env:AUTH_MODE="env"
uv run chargebee-mcp
```

### HTTP — gateway / multi-tenant
```powershell
$env:MCP_TRANSPORT="http"
$env:AUTH_MODE="gateway"
uv run chargebee-mcp
# Each request must include: X-Chargebee-Site and X-Chargebee-Api-Key headers
```

## Available Tools (30)

### Company (Customer) — 8

| Tool | Description | Parameters |
|---|---|---|
| `chargebee_list_customers` | List customers (companies) | `limit`, `offset`, `include_deleted`, `filters` (dict of Chargebee compound filter keys) |
| `chargebee_create_customer` | Create a customer (company) | `first_name`, `last_name`, `email`, `company`, `phone`, `id`, `auto_collection`, `taxability`, `locale`, `meta_data`, `billing_address` |
| `chargebee_retrieve_customer` | Retrieve a customer by ID | `customer_id` |
| `chargebee_update_customer` | Update a customer | `customer_id`, `first_name`, `last_name`, `email`, `company`, `phone`, `auto_collection`, `taxability`, `locale`, `invoice_notes`, `meta_data` |
| `chargebee_delete_customer` | Delete a customer | `customer_id`, `delete_payment_method` |
| `chargebee_merge_customers` | Merge one customer into another | `from_customer_id`, `to_customer_id` |
| `chargebee_assign_payment_role` | Assign a payment source's role (primary/backup) | `customer_id`, `payment_source_id`, `role` |
| `chargebee_get_customer_hierarchy` | Get account hierarchy for a customer | `customer_id`, `hierarchy_operation_type` |

### Personnel (Customer Contacts) — 4

| Tool | Description | Parameters |
|---|---|---|
| `chargebee_list_customer_contacts` | List contacts under a customer | `customer_id`, `limit`, `offset` |
| `chargebee_add_customer_contact` | Add a contact to a customer | `customer_id`, `first_name`, `last_name`, `email`, `phone`, `label`, `enabled`, `send_account_email`, `send_billing_email` |
| `chargebee_update_customer_contact` | Update an existing contact | `customer_id`, `contact_id`, `first_name`, `last_name`, `email`, `phone`, `label`, `enabled`, `send_account_email`, `send_billing_email` |
| `chargebee_delete_customer_contact` | Delete a contact | `customer_id`, `contact_id` |

### Account (Subscription lifecycle) — 10

| Tool | Description | Parameters |
|---|---|---|
| `chargebee_list_subscriptions` | List subscriptions | `limit`, `offset`, `include_deleted`, `filters` |
| `chargebee_retrieve_subscription` | Retrieve a subscription by ID | `subscription_id` |
| `chargebee_create_subscription` | Create a subscription for a customer | `customer_id`, `subscription_items`, `id`, `start_date`, `trial_end`, `auto_collection`, `po_number`, `coupon_ids`, `payment_source_id`, `invoice_immediately`, `meta_data` |
| `chargebee_update_subscription` | Update an existing subscription | `subscription_id`, `subscription_items`, `replace_items_list`, `coupon_ids`, `replace_coupon_list`, `prorate`, `end_of_term`, `invoice_immediately`, `po_number`, `meta_data` |
| `chargebee_cancel_subscription` | Cancel a subscription | `subscription_id`, `cancel_option`, `end_of_term`, `cancel_at`, `cancel_reason_code`, `credit_option_for_current_term_charges`, `unbilled_charges_option` |
| `chargebee_pause_subscription` | Pause a subscription | `subscription_id`, `pause_option`, `pause_date`, `resume_date`, `unbilled_charges_handling` |
| `chargebee_resume_subscription` | Resume a paused subscription | `subscription_id`, `resume_option`, `resume_date`, `charges_handling` |
| `chargebee_reactivate_subscription` | Reactivate a cancelled subscription | `subscription_id`, `trial_end`, `billing_cycles`, `invoice_immediately` |
| `chargebee_change_subscription_term_end` | Change the current term's end date | `subscription_id`, `term_ends_at`, `prorate`, `invoice_immediately` |
| `chargebee_retrieve_subscription_with_scheduled_changes` | Retrieve a subscription with pending scheduled changes | `subscription_id` |

### Account (Payment Sources) — 4

| Tool | Description | Parameters |
|---|---|---|
| `chargebee_list_payment_sources` | List payment sources | `limit`, `offset`, `subscription_id`, `include_deleted`, `filters` |
| `chargebee_create_card_payment_source` | Add a card payment source to a customer | `customer_id`, `card`, `replace_primary_payment_source` |
| `chargebee_update_card_payment_source` | Update card details on a payment source | `payment_source_id`, `card` |
| `chargebee_delete_payment_source` | Delete a payment source | `payment_source_id` |

### Report (Invoices / Transactions / Credit Notes) — 4

| Tool | Description | Parameters |
|---|---|---|
| `chargebee_list_invoices` | List invoices | `limit`, `offset`, `include_deleted`, `filters` |
| `chargebee_retrieve_invoice` | Retrieve an invoice by ID | `invoice_id`, `line_items_limit`, `line_items_offset` |
| `chargebee_list_transactions` | List payment/refund transactions | `limit`, `offset`, `include_deleted`, `filters` |
| `chargebee_list_credit_notes` | List credit notes | `limit`, `offset`, `include_deleted`, `filters` |

### Filter parameters

Chargebee's list endpoints use compound filter query keys with an operator suffix, e.g. `email[is]=a@b.com`, `created_at[after]=1700000000`, `status[in]=["active","paused"]`. Rather than expanding every field × operator combination into separate function parameters, list tools accept an optional `filters: dict[str, str]` argument — pass the literal Chargebee query key (including the `[operator]` suffix) as the dict key. Supported fields per resource are documented in each tool's docstring; supported operators are `[is]`, `[is_not]`, `[starts_with]`, `[in]`, `[not_in]`, `[between]`, `[after]`, `[before]`, `[on]`, `[none]`, `[is_present]` (availability varies by field type — see [Chargebee's filter documentation](https://apidocs.chargebee.com/docs/api/customers?prod_cat_ver=2#list_customers)).

### Request encoding

Chargebee's REST API uses `application/x-www-form-urlencoded` request bodies, not JSON. Nested object/array parameters (`card`, `billing_address`, `subscription_items`, `meta_data`, etc.) are accepted as plain Python `dict`/`list[dict]` and flattened server-side into Chargebee's bracket-notation form fields (`card[number]=...`, `subscription_items[item_price_id][0]=...`) — see `_flatten_form()` in `api_client.py`.

## Known Gaps

- **⚠️ Not yet verified against a live Chargebee account.** All 30 tools have been checked structurally (MCP handshake, tools-list, schema validity, `/health`, gateway 401 credential-gating) but not yet exercised against a real Chargebee site — pending a real test API key/site from the user. In particular, the array-of-hash form encoding (`subscription_items`, `exemption_details`, etc.) is implemented per Chargebee's documented convention but has not been confirmed with a real `POST` call.
- Complex nested fields (`card`, `billing_address`, `subscription_items`, `meta_data`, etc.) are accepted as generic `dict`/`list[dict]` rather than fully-typed sub-schemas — callers must know Chargebee's field names for these substructures (documented in each tool's docstring where practical, otherwise see the [Chargebee API reference](https://apidocs.chargebee.com/docs/api/)).
- List-endpoint filters are not expanded into named parameters (see "Filter parameters" above) — this keeps the tool count/signature size manageable but pushes filter-key correctness onto the caller.
- Scope is limited to the 30 operations above (company/personnel/account/report management), not the full 438-operation/77-resource Chargebee API. Resources like Coupons, Items/Item Prices/Item Families, Estimates, Orders, Virtual Bank Accounts, Hosted Pages, etc. are out of scope per user-confirmed selection.

## API Reference

- [Chargebee API Documentation](https://apidocs.chargebee.com/docs/api/)
- [Chargebee OpenAPI Specification](https://github.com/chargebee/openapi) (`chargebee_api_v2_pc_v2_spec.json` — API v2 + Product Catalog v2, used as the source of truth for this service)
- [Chargebee Official MCP Servers](https://www.chargebee.com/docs/billing/2.0/ai-in-chargebee/chargebee-mcp) (evaluated and found insufficient — see Scope above)
