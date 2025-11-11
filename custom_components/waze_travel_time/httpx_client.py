"""Helper for httpx."""

from __future__ import annotations

import sys
from types import TracebackType
from typing import Any, Self

# httpx dynamically imports httpcore, so we need to import it
# to avoid it being imported later when the event loop is running
import httpcore  # noqa: F401
import httpx

from homeassistant.const import APPLICATION_NAME, EVENT_HOMEASSISTANT_CLOSE, __version__
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.util.ssl import (
    SSLCipherList,
    client_context,
)

# We have a lot of integrations that poll every 10-30 seconds
# and we want to keep the connection open for a while so we
# don't have to reconnect every time so we use 15s to match aiohttp.
KEEP_ALIVE_TIMEOUT = 15
DEFAULT_LIMITS = limits = httpx.Limits(keepalive_expiry=KEEP_ALIVE_TIMEOUT)
SERVER_SOFTWARE = (
    f"{APPLICATION_NAME}/{__version__} "
    f"httpx/{httpx.__version__} Python/{sys.version_info[0]}.{sys.version_info[1]}"
)
USER_AGENT = "User-Agent"


class HassHttpXAsyncClient(httpx.AsyncClient):
    """httpx AsyncClient that suppresses context management."""

    async def __aenter__(self) -> Self:
        """Prevent an integration from reopen of the client via context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        """Prevent an integration from close of the client via context manager."""


@callback
def create_async_httpx_client(
    hass: HomeAssistant,
    ssl_cipher_list: SSLCipherList = SSLCipherList.PYTHON_DEFAULT,
    **kwargs: Any,
) -> httpx.AsyncClient:
    """Create a new httpx.AsyncClient with kwargs, i.e. for cookies.

    Forces use of IPv4.

    This method must be run in the event loop.
    """
    ssl_context = client_context(ssl_cipher_list)
    client = HassHttpXAsyncClient(
        verify=ssl_context,
        headers={USER_AGENT: SERVER_SOFTWARE},
        limits=DEFAULT_LIMITS,
        transport=httpx.HTTPTransport(local_address="0.0.0.0"),
        **kwargs,
    )

    async def _async_close_client(event: Event) -> None:
        """Close httpx client."""
        await client.aclose()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_client)

    return client
