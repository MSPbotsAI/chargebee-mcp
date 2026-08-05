import contextvars
import sys
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .api_client import ChargebeeClient
from .config import Settings

# ─────────────────────────────────────────────────────────────────────────────
# Per-request site/API-key contextvar for gateway mode.
# GatewayTokenMiddleware sets this before the MCP handler runs.
# Python asyncio copies context per task, so concurrent requests are isolated.
# ─────────────────────────────────────────────────────────────────────────────
_gateway_creds_var: contextvars.ContextVar[tuple[str, str] | None] = contextvars.ContextVar(
    "chargebee_gateway_creds", default=None
)


def get_client_from_context(settings: Settings) -> ChargebeeClient | None:
    """Resolve the active ChargebeeClient for the current request context."""
    if settings.auth_mode == "gateway":
        creds = _gateway_creds_var.get()
        if creds is None:
            return None
        site, api_key = creds
    else:
        site = settings.chargebee_site
        api_key = settings.chargebee_api_key

    if not site or not api_key:
        return None
    return ChargebeeClient(site, api_key)


class GatewayTokenMiddleware:
    """ASGI middleware for gateway mode.

    Reads the configured site + API key headers from each request and stores
    them in the contextvar for the duration of that request. Returns 401 if
    either header is missing on /mcp requests.
    """

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        # Header lookup is case-insensitive in Starlette
        site = request.headers.get(self.settings.chargebee_site_header.lower())
        api_key = request.headers.get(self.settings.chargebee_api_key_header.lower())
        if not site or not api_key:
            response = JSONResponse(
                {
                    "error": "Missing credentials",
                    "message": (
                        f"Gateway mode requires the {self.settings.chargebee_site_header} and "
                        f"{self.settings.chargebee_api_key_header} headers"
                    ),
                    "required_headers": [
                        self.settings.chargebee_site_header,
                        self.settings.chargebee_api_key_header,
                    ],
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return

        ctx_token = _gateway_creds_var.set((site, api_key))
        try:
            await self.app(scope, receive, send)
        finally:
            _gateway_creds_var.reset(ctx_token)


def create_mcp_server(settings: Settings) -> FastMCP:
    """Build the FastMCP server instance and register all tools."""
    # DNS-rebinding protection is disabled because the container runs behind
    # mcp-gateway on an internal Docker network and is never publicly exposed.
    mcp = FastMCP(
        name="chargebee-mcp",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    client_factory: Callable[[], ChargebeeClient | None] = lambda: get_client_from_context(settings)

    if not settings.has_credentials:
        # Graceful degradation: register only a diagnostic tool when no credentials are available.
        @mcp.tool()
        async def chargebee_test_connection() -> str:
            """Test Chargebee API connection. Shows configuration requirements when credentials are missing."""
            return (
                "Error: Missing Chargebee credentials.\n\n"
                "Set the required environment variables:\n"
                "  CHARGEBEE_SITE=your_site\n"
                "  CHARGEBEE_API_KEY=your_api_key\n\n"
                "Or use gateway mode (per-request credentials):\n"
                "  AUTH_MODE=gateway\n"
                f"  Send headers: {settings.chargebee_site_header}: your_site, "
                f"{settings.chargebee_api_key_header}: your_api_key"
            )

        print(
            "Warning: No Chargebee credentials found. Only the diagnostic tool is available.",
            file=sys.stderr,
        )
        return mcp

    # Register all tool modules here.
    from .tools import customers, payment_sources, reports, subscriptions

    customers.register(mcp, client_factory)
    subscriptions.register(mcp, client_factory)
    payment_sources.register(mcp, client_factory)
    reports.register(mcp, client_factory)

    return mcp
