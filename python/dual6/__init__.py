"""Dual6 storage container.

The pure-Python reference implementation is always loaded.  If the compiled
Rust extension ``dual6._native`` is importable, its functions are layered on
top and missing functions fall back to the reference implementation.
"""

from __future__ import annotations

import functools
import os
from typing import Any, Callable

__version__ = "0.3.0"

from . import _ref  # noqa: F401
from ._ref import *  # noqa: F401,F403
from ._ref import __all__ as _ref_all

__all__ = list(_ref_all)

# Single-channel adapter bridges are part of the top-level convenience surface
# on every backend.  ``dual6.adapters`` remains the canonical import path; these
# re-exports keep the ref and native backends API-identical.
from .adapters import (  # noqa: E402
    bits_to_dual6_block64,
    bits_to_symbols,
    dual6_block64_to_bits,
    dual6_block64_to_trits,
    symbols_to_bits,
    symbols_to_trits,
    trits_to_dual6_block64,
    trits_to_symbols,
)

_ADAPTER_NAMES = (
    "bits_to_dual6_block64",
    "bits_to_symbols",
    "dual6_block64_to_bits",
    "dual6_block64_to_trits",
    "symbols_to_bits",
    "symbols_to_trits",
    "trits_to_dual6_block64",
    "trits_to_symbols",
)
for _adapter in _ADAPTER_NAMES:
    if _adapter not in __all__:
        __all__.append(_adapter)
del _adapter

_RUST_ERROR_MAP = {
    "InvalidDigit": "INVALID_DIGIT",
    "InvalidPacking": "INVALID_PACKING",
    "WidthMismatch": "WIDTH_MISMATCH",
    "InvalidBit": "INVALID_BIT",
    "InvalidTrit": "INVALID_TRIT",
    "InvalidLayout": "INVALID_LAYOUT",
    "UnsupportedVersion": "UNSUPPORTED_VERSION",
    "CrcMismatch": "CRC_MISMATCH",
}


def _normalize_native_result(name: str, result: Any) -> Any:
    # PyO3 maps Vec<u8> to Python bytes.  The reference API uses lists of ints
    # for symbol and bit channels, so normalize at the boundary.
    if name in (
        "mux",
        "unpack_digits",
        "unpack_bits_bytes",
        "unpack_block64",
        "unpack_block64_many",
        "unpack_block128",
        "unpack_block40",
        "trits_to_symbols",
        "bits_to_symbols",
        "symbols_to_bits",
        "dual6_block64_to_bits",
    ):
        return list(result)
    if name in (
        "demux",
        "unpack_block64_dp",
        "unpack_block128_dp",
        "unpack_block40_dp",
        "unpack_dual_plane",
        "unpack_dual_plane_v1",
    ):
        return list(result[0]), list(result[1])
    if name == "unpack_dual_plane_v2":
        return list(result[0]), list(result[1]), result[2]
    if name in ("unpack_frame_auto", "unpack_frame_auto_buffer"):
        return result[0], list(result[1]), list(result[2]), result[3]
    if name in ("unpack_bits_from",):
        return list(result)
    if name == "unpack_dual_plane_from":
        return list(result[0]), list(result[1])
    return result


_NATIVE_WIDTH_LIMIT = 48


def _native_needs_ref_fallback(name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> bool:
    """Return True when the native helper's 48-symbol limit should fall back."""
    if name == "pack_digits":
        digits = kwargs.get("digits", args[0] if args else ())
        return len(digits) > _NATIVE_WIDTH_LIMIT
    if name == "unpack_digits":
        if "width" in kwargs:
            return kwargs["width"] > _NATIVE_WIDTH_LIMIT
        return len(args) > 1 and args[1] > _NATIVE_WIDTH_LIMIT
    if name in ("max_interleaved", "fits_unsigned_word"):
        width = kwargs.get("width", args[0] if args else 0)
        return width > _NATIVE_WIDTH_LIMIT
    return False


def _wrap_native(name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if _native_needs_ref_fallback(name, args, kwargs):
            ref_fn = getattr(_ref, name, None)
            if ref_fn is not None:
                return ref_fn(*args, **kwargs)
        try:
            result = fn(*args, **kwargs)
        except Dual6Error:
            raise
        except OverflowError as exc:
            code_name = {
                "encode_digit": "INVALID_BIT",
                "decode_digit": "INVALID_DIGIT",
                "pack_digits": "INVALID_DIGIT",
                "unpack_digits": "INVALID_PACKING",
                "max_interleaved": "INVALID_PACKING",
                "fits_unsigned_word": "INVALID_PACKING",
                "pack_bits_bytes": "INVALID_BIT",
                "pack_trits_bytes": "INVALID_TRIT",
            }.get(name, "INVALID_LAYOUT")
            raise Dual6Error(ErrorCode[code_name], str(exc)) from exc
        except ValueError as exc:
            text = str(exc)
            prefix = text.split(":", 1)[0].strip()
            code_name = _RUST_ERROR_MAP.get(prefix, "INVALID_LAYOUT")
            raise Dual6Error(ErrorCode[code_name], text) from exc
        return _normalize_native_result(name, result)

    return wrapper


# Backend selection.  ``DUAL6_BACKEND`` is an explicit debugging / testing
# switch:
#
#   unset / "auto"  -> native when importable, otherwise ref
#   "native"        -> require the native extension (raise if missing)
#   "ref"           -> force the pure-Python reference implementation
_BACKEND_ENV = os.environ.get("DUAL6_BACKEND", "").strip().lower()
if _BACKEND_ENV not in ("", "auto", "native", "ref"):
    raise ValueError(
        "DUAL6_BACKEND must be one of 'auto', 'native' or 'ref', "
        f"got {_BACKEND_ENV!r}"
    )

if _BACKEND_ENV == "ref":
    _native_module = None
else:
    try:  # pragma: no cover - depends on whether the native extension is built
        from . import _native as _native_module
    except ImportError:  # normal when Rust has not been built
        if _BACKEND_ENV == "native":
            raise ImportError(
                "DUAL6_BACKEND=native was requested but dual6._native is not importable"
            ) from None
        _native_module = None

__backend__ = "native" if _native_module is not None else "ref"

if _native_module is not None:  # pragma: no cover - native-specific path
    for _name in dir(_native_module):
        if _name.startswith("_"):
            continue
        _obj = getattr(_native_module, _name)
        if callable(_obj):
            globals()[_name] = _wrap_native(_name, _obj)
            if _name not in __all__:
                __all__.append(_name)
    del _name, _obj
