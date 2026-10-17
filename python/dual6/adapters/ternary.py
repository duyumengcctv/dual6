"""Ternary-stream adapters for Dual6 containers."""

from __future__ import annotations

from typing import List, Sequence

from .. import Dual6Error, ErrorCode, demux, mux, pack_block64_dp, unpack_block64_dp


def _check_trit(trit: int) -> None:
    if trit not in (-1, 0, 1):
        raise Dual6Error(ErrorCode.INVALID_TRIT, f"trit must be -1, 0 or 1, got {trit!r}")


def _check_fill_bit(fill_bit: int) -> None:
    if fill_bit not in (0, 1):
        raise Dual6Error(ErrorCode.INVALID_BIT, f"fill_bit must be 0 or 1, got {fill_bit!r}")


def trits_to_symbols(trits: Sequence[int], fill_bit: int = 0) -> List[int]:
    """Pair a pure trit stream with a constant bit channel."""
    _check_fill_bit(fill_bit)
    for t in trits:
        _check_trit(t)
    return mux([fill_bit] * len(trits), trits)


def symbols_to_trits(symbols: Sequence[int]) -> List[int]:
    """Extract the trit channel, discarding the bit channel."""
    _, trits = demux(symbols)
    return trits


def trits_to_dual6_block64(trits: Sequence[int], fill_bit: int = 0) -> bytes:
    """Put a pure 24-trit stream into a D6-64-DP block."""
    _check_fill_bit(fill_bit)
    if len(trits) != 24:
        raise Dual6Error(
            ErrorCode.WIDTH_MISMATCH,
            f"D6-64-DP requires 24 trits, got {len(trits)}",
        )
    return pack_block64_dp([fill_bit] * 24, trits)


def dual6_block64_to_trits(data: bytes) -> List[int]:
    """Recover the trit channel from a D6-64-DP block."""
    _, trits = unpack_block64_dp(data)
    return trits
