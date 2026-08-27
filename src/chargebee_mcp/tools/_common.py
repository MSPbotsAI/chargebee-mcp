from typing import Literal

from .._json import error_envelope

NO_CREDS = error_envelope(
    "not_configured",
    "No Chargebee credentials configured. Send the X-Chargebee-Site and "
    "X-Chargebee-Api-Key headers.",
    False,
)

# Verified against Chargebee's own OpenAPI spec (github.com/chargebee/openapi,
# components/schemas/Customer, checked 2026-08-27) — both real closed enums.
AutoCollection = Literal["on", "off"]
Taxability = Literal["taxable", "exempt"]

OFFSET_DESC = (
    "Pagination cursor from a previous response's next_offset field. "
    "Cursor-based and sequential only — there is no way to jump to an "
    "arbitrary page number; never construct or guess this value, only pass "
    "through a next_offset you already retrieved."
)

CUSTOMER_ID_NOTE = (
    " Must be the real Chargebee customer ID, not a company or person name "
    "— if you only have a name, resolve it first via chargebee_list_customers "
    'with a filter like {"company[is]": "..."} or {"email[is]": "..."}.'
)
