import asyncio
import base64
from typing import Any

import httpx

from ._json import error_envelope

DEFAULT_BASE_URL_TEMPLATE = "https://{site}.chargebee.com/api/v2"

_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_MAX_BACKOFF_SECONDS = 20.0

# One shared connection pool for the process lifetime. No credentials are
# ever stored on it — site/api_key are passed per-request via headers built
# by each ChargebeeClient instance, so this is safe to share across
# tenants/requests (see server.py's contextvar-based credential isolation,
# which is what actually keeps tenants apart).
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True)
    return _http_client


# status_code -> (error code, retryable). status_code 0 means a network/
# connection-level failure (no response at all).
_STATUS_TO_CODE: dict[int, tuple[str, bool]] = {
    0: ("upstream_error", True),
    400: ("invalid_argument", False),
    401: ("unauthorized", False),
    403: ("unauthorized", False),
    404: ("not_found", False),
    422: ("invalid_argument", False),
    429: ("rate_limited", True),
}


def _classify(status_code: int) -> tuple[str, bool]:
    if status_code in _STATUS_TO_CODE:
        return _STATUS_TO_CODE[status_code]
    if status_code >= 500:
        return "upstream_error", True
    return "invalid_argument", False


class ChargebeeError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Chargebee API error {status_code}: {message}")

    def to_envelope(self) -> str:
        code, retryable = _classify(self.status_code)
        return error_envelope(code, self.message, retryable)


def _flatten_form(data: dict[str, Any]) -> dict[str, str]:
    """Flatten a nested dict/list structure into Chargebee's bracket-notation
    form fields (Chargebee's REST API is application/x-www-form-urlencoded,
    not JSON).

    Rules (per Chargebee's documented form encoding):
      - scalar:                field=value
      - nested object (hash):  field[subfield]=value
      - list of scalars:       field[0]=v0&field[1]=v1
      - list of objects ("array of hashes", e.g. subscription_items,
        exemption_details): field[subfield][0]=v, field[subfield][1]=v — the
        index is nested *inside* each subfield key, not around the whole hash.
    """
    out: dict[str, str] = {}

    def walk(prefix: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, dict):
            for k, v in value.items():
                walk(f"{prefix}[{k}]", v)
        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                # Array of hashes: transpose to field[subfield][index].
                for idx, item in enumerate(value):
                    if not isinstance(item, dict):
                        continue
                    for k, v in item.items():
                        walk(f"{prefix}[{k}][{idx}]", v)
            else:
                for idx, item in enumerate(value):
                    walk(f"{prefix}[{idx}]", item)
        elif isinstance(value, bool):
            out[prefix] = "true" if value else "false"
        else:
            out[prefix] = str(value)

    for key, value in data.items():
        if value is None:
            continue
        walk(key, value)
    return out


class ChargebeeClient:
    """Async httpx client wrapping the Chargebee REST API v2.

    Auth: HTTP Basic, API key as username, blank password
    (Authorization: Basic base64("{api_key}:")). Base URL is per-tenant:
    https://{site}.chargebee.com/api/v2.

    Reuses the module-level connection pool (see _get_http_client) across
    every call made through this instance, rather than opening a new
    connection per request.
    """

    def __init__(self, site: str, api_key: str):
        self._base_url = DEFAULT_BASE_URL_TEMPLATE.format(site=site)
        basic = base64.b64encode(f"{api_key}:".encode()).decode()
        self._headers = {"Authorization": f"Basic {basic}"}

    def _clean_params(self, params: dict | None) -> dict:
        if not params:
            return {}
        return {k: v for k, v in params.items() if v is not None}

    async def get(self, path: str, params: dict | None = None) -> Any:
        return await self._request("GET", path, params=self._clean_params(params))

    async def post(self, path: str, body: dict | None = None) -> Any:
        return await self._request("POST", path, form_data=_flatten_form(body or {}))

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        form_data: dict | None = None,
    ) -> Any:
        client = _get_http_client()
        url = f"{self._base_url}{path}"

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await client.request(
                    method, url, headers=self._headers, params=params, data=form_data
                )
            except httpx.RequestError as e:
                last_exc = e
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(min(2**attempt, _MAX_BACKOFF_SECONDS))
                    continue
                raise ChargebeeError(0, f"{e or type(e).__name__} (url={url})") from e

            if resp.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
                delay = self._retry_delay(resp, attempt)
                await asyncio.sleep(delay)
                continue

            self._raise_for_status(resp)
            return self._parse_body(resp)

        # Unreachable in practice (loop always returns or raises above), but
        # keeps type checkers happy and guards against future edits.
        if last_exc:
            raise ChargebeeError(0, f"{last_exc}") from last_exc
        raise ChargebeeError(0, "request failed with no response")

    def _retry_delay(self, resp: httpx.Response, attempt: int) -> float:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), _MAX_BACKOFF_SECONDS)
            except ValueError:
                pass
        return min(2**attempt, _MAX_BACKOFF_SECONDS)

    def _parse_body(self, resp: httpx.Response) -> Any:
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return {"raw_response": resp.text}

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            try:
                detail = resp.json()
                if isinstance(detail, dict):
                    msg = detail.get("message") or str(detail)
                else:
                    msg = str(detail)
            except Exception:
                msg = resp.text
            raise ChargebeeError(resp.status_code, msg)
