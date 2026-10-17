"""Sequence-level mux/demux for 6-state Dual6 symbols."""

from __future__ import annotations

from typing import List, Sequence, Tuple

from .errors import Dual6Error, ErrorCode
from .symbol import decode_digit, encode_digit


def mux(bits: Sequence[int], trits: Sequence[int]) -> List[int]:
    """Mux bit and trit sequences into a symbol sequence."""
    if len(bits) != len(trits):
        raise Dual6Error(
            ErrorCode.WIDTH_MISMATCH,
            f"bits length {len(bits)} != trits length {len(trits)}",
        )
    return [encode_digit(b, t) for b, t in zip(bits, trits)]


def demux(symbols: Sequence[int]) -> Tuple[List[int], List[int]]:
    """Demux a symbol sequence into ``(bits, trits)``."""
    bits: List[int] = []
    trits: List[int] = []
    for d in symbols:
        b, t = decode_digit(d)
        bits.append(b)
        trits.append(t)
    return bits, trits
