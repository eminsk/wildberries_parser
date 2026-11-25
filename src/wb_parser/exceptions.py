"""
Typed exceptions for Wildberries Parser SDK.
"""

from __future__ import annotations

from typing import Optional


class WBError(Exception):
    """Base exception for all Wildberries SDK errors."""


class WBNetworkError(WBError):
    """Raised when an HTTP transport or timeout failure exhausts retries."""


class WBNotFoundError(WBError):
    """Raised when the requested product, seller, or feedback resource does not exist (404)."""


class WBRateLimitError(WBError):
    """Raised when Wildberries throttles requests with HTTP 429 or 439."""


class WBAntiBotError(WBError):
    """
    Raised when a gateway endpoint is protected by WBAAS (HTTP 498 / 403).

    Wildberries search and catalog endpoints require either a clean residential/mobile IP
    (e.g., via proxy), valid browser session cookies, or an `x-wbaas-token`.
    Direct CDN endpoints (`wbbasket.ru` `card.json` and `feedbacks1/2.wb.ru`) operate
    without WBAAS gating.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        url: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class WBValidationError(WBError):
    """Raised when URL/ID parsing or response schema validation fails."""
