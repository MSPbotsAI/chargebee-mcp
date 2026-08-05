from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Transport
    mcp_transport: Literal["stdio", "http"] = "stdio"
    mcp_http_port: int = 8080
    mcp_http_host: str = "0.0.0.0"

    # Auth mode:
    # "gateway" — production/SOP-compliant: site + API key from HTTP headers per request (no global state)
    # "env"     — local dev only: shared site + API key from env vars (not SOP-compliant)
    auth_mode: Literal["env", "gateway"] = "gateway"

    # Chargebee credentials (only required in env mode)
    chargebee_site: str | None = None
    chargebee_api_key: str | None = None

    # HTTP header names used to pass site + API key in gateway mode.
    # The client must include both headers on every /mcp request.
    chargebee_site_header: str = "X-Chargebee-Site"
    chargebee_api_key_header: str = "X-Chargebee-Api-Key"

    @property
    def has_credentials(self) -> bool:
        """Returns True if the server can serve API calls.

        Gateway mode always returns True — each request carries its own credentials.
        Env mode requires both CHARGEBEE_SITE and CHARGEBEE_API_KEY to be set.
        """
        if self.auth_mode == "gateway":
            return True
        return self.chargebee_site is not None and self.chargebee_api_key is not None


def get_settings() -> Settings:
    return Settings()
