"""Error codes and exception type for the Dual6 container layer."""

from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    OK = "OK"
    INVALID_DIGIT = "INVALID_DIGIT"
    INVALID_PACKING = "INVALID_PACKING"
    WIDTH_MISMATCH = "WIDTH_MISMATCH"
    INVALID_BIT = "INVALID_BIT"
    INVALID_TRIT = "INVALID_TRIT"
    INVALID_LAYOUT = "INVALID_LAYOUT"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
    CRC_MISMATCH = "CRC_MISMATCH"


class Dual6Error(Exception):
    """Storage-layer error.

    ``error.code`` is an :class:`ErrorCode`.  The container does not raise
    arithmetic errors; arithmetic belongs to separate binary/ternary engines.
    """

    def __init__(self, code: ErrorCode, message: str = "") -> None:
        self.code = code
        super().__init__(f"{code.value}: {message}" if message else code.value)
