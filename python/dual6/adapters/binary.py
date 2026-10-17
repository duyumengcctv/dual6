"""Binary-stream adapters for Dual6 containers."""

from __future__ import annotations

from typing import List, Sequence

from .. import Dual6Error, ErrorCode, demux, mux, pack_block64_dp, unpack_block64_dp


def _check_bit(bit: int) -> None:
    if bit not in (0, 1):
        raise Dual6Error(ErrorCode.INVALID_BIT, f"bit must be 0 or 1, got {bit!r}")


def _check_fill_trit(fill_trit: int) -> None:
    if fill_trit not in (-1, 0, 1):
        raise Dual6Error(ErrorCode.INVALID_TRIT, f"fill_trit must be -1, 0 or 1, got {fill_trit!r}")


def bits_to_symbols(bits: Sequence[int], fill_trit: int = 0) -> List[int]:
    """Pair a pure bit stream with a constant trit channel."""
    _check_fill_trit(fill_trit)
    for b in bits:
        _check_bit(b)
    return mux(bits, [fill_trit] * len(bits))


def symbols_to_bits(symbols: Sequence[int]) -> List[int]:
    """Extract the bit channel, discarding the trit channel."""
    bits, _ = demux(symbols)
    return bits


def bits_to_dual6_block64(bits: Sequence[int], fill_trit: int = 0) -> bytes:
    """Put a pure 24-bit stream into a D6-64-DP block."""
    _check_fill_trit(fill_trit)
    if len(bits) != 24:
        raise Dual6Error(
            ErrorCode.WIDTH_MISMATCH,
            f"D6-64-DP requires 24 bits, got {len(bits)}",
        )
    return pack_block64_dp(bits, [fill_trit] * 24)


def dual6_block64_to_bits(data: bytes) -> List[int]:
    """Recover the bit channel from a D6-64-DP block."""
    bits, _ = unpack_block64_dp(data)
    return bits
