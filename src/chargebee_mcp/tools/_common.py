import base64
import json
from collections.abc import Awaitable, Callable
from typing import Literal

from .._json import MAX_CHARS, dump_json_capped, error_envelope, fit_count, fits

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
    "Pagination cursor from a previous response's next_offset or page_cursor "
    "field. Cursor-based and sequential only — there is no way to jump to an "
    "arbitrary page number; never construct or guess this value, only pass "
    "through a next_offset/page_cursor you already retrieved from THIS same "
    "tool. A cursor issued by a different chargebee_list_* tool, or any "
    "value you invented, is rejected."
)

CUSTOMER_ID_NOTE = (
    " Must be the real Chargebee customer ID, not a company or person name "
    "— if you only have a name, resolve it first via chargebee_list_customers "
    'with a filter like {"company[is]": "..."} or {"email[is]": "..."}.'
)


# ── Pagination cursor codec (PRD-17977) ─────────────────────────────────────
#
# Root cause (see docs/tickets/PRD-17977.md "现状"): the MCP layer pre-parses
# any incoming string argument whose declared type isn't exactly `str` — if
# the string happens to look like JSON, it gets json.loads()'d into a real
# Python value *before* Pydantic validation runs. Chargebee's own next_offset
# for these 5 resources is a 2-element array, so a caller passing that array
# straight back (as a JSON-string or as a genuine list) always ends up being
# validated against the *widened* type below, not rejected outright.
#
# So `offset` accepts three input shapes:
#   1. None / ""                      -> first page
#   2. list[str]                      -> the raw next_offset passed straight
#                                         back (back-compat path, AC1/TC-CBM-002)
#   3. "cb1.<base64url>"              -> an opaque cursor this service issued
#                                         itself (recommended path, AC1/TC-CBM-001)
# Anything else (including a JSON-looking string with content nobody issued)
# is rejected as an invalid cursor (AC5/AC6, TC-CBM-006/013/014).
CURSOR_PREFIX = "cb1."


class InvalidCursorError(ValueError):
    """offset/page_cursor could not be decoded into something Chargebee will
    accept — caller should get invalid_argument, not a raw exception."""


def encode_cursor(raw_next_offset: str | list[str] | None, resource: str) -> str | None:
    """Encode a Chargebee-issued next_offset into an opaque, resource-scoped
    cursor string. Returns None if there is no next page (nothing to encode).
    """
    if raw_next_offset is None:
        return None
    payload = json.dumps({"r": resource, "o": raw_next_offset}, separators=(",", ":"))
    token = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{CURSOR_PREFIX}{token}"


def _looks_like_real_next_offset(value: list) -> bool:
    # Chargebee's compound cursor for these resources is documented/observed
    # as [timestamp_ms_as_str, id_str] — a lightweight, honest format check,
    # NOT an authentication mechanism (this service is stateless and signs
    # nothing). It exists only to tell an actually-round-tripped next_offset
    # apart from an invented 2-element list (TC-CBM-013). Real behavior
    # against a live Chargebee test site is still unverified — see the
    # "风险" note in docs/tickets/PRD-17977.md; revisit if AC9/AC11 surface a
    # shape this rejects.
    return (
        len(value) == 2
        and all(isinstance(v, str) for v in value)
        and value[0].isdigit()
        and len(value[1]) > 0
    )


def decode_cursor(offset: str | list[str] | None, resource: str) -> str | list[str] | None:
    """Turn a caller-supplied offset into the raw form Chargebee expects, or
    raise InvalidCursorError. None/"" both mean "first page" (AC8).
    """
    if offset is None or offset == "":
        return None

    if isinstance(offset, list):
        if not _looks_like_real_next_offset(offset):
            raise InvalidCursorError(f"offset does not look like a real next_offset: {offset!r}")
        return offset

    if not isinstance(offset, str) or not offset.startswith(CURSOR_PREFIX):
        raise InvalidCursorError(f"unrecognized page cursor: {offset!r}")

    token = offset[len(CURSOR_PREFIX):]
    padded = token + "=" * (-len(token) % 4)
    try:
        decoded = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except Exception as e:
        raise InvalidCursorError(f"could not decode page cursor: {offset!r}") from e

    if not isinstance(decoded, dict) or "r" not in decoded or "o" not in decoded:
        raise InvalidCursorError(f"page cursor has an unexpected shape: {offset!r}")
    if decoded["r"] != resource:
        raise InvalidCursorError(
            f"page cursor was issued for {decoded['r']!r}, not {resource!r} — "
            "cursors are not interchangeable across tools"
        )
    return decoded["o"]


def to_request_offset(value: str | list[str] | None) -> str | None:
    """Serialize a decoded offset back into what goes on the wire to
    Chargebee. Assumption (unverified against a live site, see risk note
    above): a compound cursor round-trips as its compact JSON-array string.
    """
    if value is None:
        return None
    if isinstance(value, list):
        return json.dumps(value, separators=(",", ":"))
    return value


async def list_with_cursor(
    resource: str,
    fetch: Callable[[int], Awaitable[dict]],
    limit: int,
    max_chars: int = MAX_CHARS,
) -> str:
    """Shared pagination glue for the 5 chargebee_list_* tools.

    `fetch(page_limit)` performs the actual Chargebee GET at that page size
    and returns the parsed response dict. This function:
      1. calls it once at the caller's requested limit,
      2. if the response would be truncated by dump_json_capped, re-fetches
         once at the largest size that's known to fit (AC4/OQ-3: the cursor
         Chargebee hands back for THAT request lines up with what we return,
         instead of a locally-sliced list paired with the wrong cursor),
      3. replaces the raw next_offset with an opaque, resource-scoped
         page_cursor (original next_offset is kept — AC7).

    No network IO happens here beyond calling the caller-supplied `fetch`;
    _json.py itself stays pure/sync (see fit_count/fits there).
    """
    result = await fetch(limit)
    if not fits(result, max_chars):
        list_keys = [k for k, v in result.items() if isinstance(v, list)]
        if list_keys:
            key = max(list_keys, key=lambda k: len(json.dumps(result[k])))
            k = fit_count(result, key, max_chars)
            if 0 < k < limit:
                result = await fetch(k)

    result = dict(result)
    raw_next = result.get("next_offset")
    if raw_next is not None:
        result["page_cursor"] = encode_cursor(raw_next, resource)
    return dump_json_capped(result, max_chars)
