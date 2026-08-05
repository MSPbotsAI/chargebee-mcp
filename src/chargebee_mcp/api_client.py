import base64
from typing import Any

import httpx

DEFAULT_BASE_URL_TEMPLATE = "https://{site}.chargebee.com/api/v2"


class ChargebeeError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Chargebee API error {status_code}: {message}")


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
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}{path}",
                headers=self._headers,
                params=self._clean_params(params),
            )
            self._raise_for_status(resp)
            return resp.json() if resp.status_code != 204 else None

    async def post(self, path: str, body: dict | None = None) -> Any:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}{path}",
                headers=self._headers,
                data=_flatten_form(body or {}),
            )
            self._raise_for_status(resp)
            return resp.json() if resp.status_code != 204 else None

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise ChargebeeError(resp.status_code, str(detail))
