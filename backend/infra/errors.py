from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class APIError(Exception):
    status_code: int
    code: str
    message: str
    details: Any | None = None


def raise_api_error(status_code: int, code: str, message: str, details: Any | None = None):
    raise APIError(status_code=status_code, code=code, message=message, details=details)
