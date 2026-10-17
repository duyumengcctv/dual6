"""Fixed-size Dual6 block layouts.

    D6-64   : 24 symbols -> 8 bytes  (63 bits used)
    D6-128  : 48 symbols -> 16 bytes (125 bits used)
    D6-40   : 40 symbols -> 13 bytes (104 bits used)

Blocks are little-endian byte encodings of the interleaved base-6 container
value.  They are storage containers, not arithmetic operands.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from .errors import Dual6Error, ErrorCode
from .buffers import _check_region, _view, _writable
from .interleaved import pack_digits, unpack_digits
from .symbol import DIGIT_BASE


@dataclass(frozen=True)
class BlockLayout:
    name: str
    symbols: int
    byte_length: int
    bit_length: int
    note: str

    @property
    def max_value(self) -> int:
        return DIGIT_BASE ** self.symbols - 1

    @property
    def information_density(self) -> float:
        return (self.symbols * math.log2(DIGIT_BASE)) / self.bit_length


BLOCK64 = BlockLayout(
    name="D6-64",
    symbols=24,
    byte_length=8,
    bit_length=64,
    note="24 symbols -> 64-bit word; 6^24 < 2^63, so the top bit stays 0.",
)

BLOCK128 = BlockLayout(
    name="D6-128",
    symbols=48,
    byte_length=16,
    bit_length=128,
    note="48 symbols -> 128-bit word; 6^48 < 2^125, top 3 bits stay 0.",
)

BLOCK40 = BlockLayout(
    name="D6-40",
    symbols=40,
    byte_length=13,
    bit_length=104,
    note="40 symbols -> 13 bytes; 6^40 < 2^104.",
)

LAYOUTS: Dict[str, BlockLayout] = {
    BLOCK64.name: BLOCK64,
    BLOCK128.name: BLOCK128,
    BLOCK40.name: BLOCK40,
}


def get_layout(name: str) -> BlockLayout:
    try:
        return LAYOUTS[name]
    except KeyError as exc:
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, f"unknown block layout {name!r}") from exc


def pack_block(symbols: Sequence[int], layout: BlockLayout) -> bytes:
    """Pack exactly ``layout.symbols`` symbols into ``layout.byte_length`` bytes."""
    if len(symbols) != layout.symbols:
        raise Dual6Error(
            ErrorCode.WIDTH_MISMATCH,
            f"{layout.name} requires {layout.symbols} symbols, got {len(symbols)}",
        )
    value = pack_digits(symbols)
    if value > layout.max_value:
        raise Dual6Error(
            ErrorCode.INVALID_PACKING,
            f"value {value} exceeds {layout.name} maximum {layout.max_value}",
        )
    return value.to_bytes(layout.byte_length, "little")


def unpack_block(data: bytes, layout: BlockLayout) -> List[int]:
    """Unpack one fixed-size block into ``layout.symbols`` symbols."""
    if len(data) != layout.byte_length:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"{layout.name} requires {layout.byte_length} bytes, got {len(data)}",
        )
    value = int.from_bytes(data, "little")
    if value > layout.max_value:
        raise Dual6Error(
            ErrorCode.INVALID_PACKING,
            f"value {value} exceeds {layout.name} maximum {layout.max_value}",
        )
    return unpack_digits(value, layout.symbols)


def pack_block64(symbols: Sequence[int]) -> bytes:
    return pack_block(symbols, BLOCK64)


def unpack_block64(data: bytes) -> List[int]:
    return unpack_block(data, BLOCK64)


def pack_block64_many(symbols: Sequence[int]) -> bytes:
    """Pack many D6-64 blocks from one flat symbol stream."""
    if len(symbols) % BLOCK64.symbols:
        raise Dual6Error(
            ErrorCode.WIDTH_MISMATCH,
            f"D6-64 batch requires a multiple of {BLOCK64.symbols} symbols, got {len(symbols)}",
        )
    out = bytearray()
    for i in range(0, len(symbols), BLOCK64.symbols):
        out += pack_block64(symbols[i : i + BLOCK64.symbols])
    return bytes(out)


def unpack_block64_many(data: bytes) -> List[int]:
    """Unpack many D6-64 blocks into one flat symbol stream."""
    if len(data) % BLOCK64.byte_length:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"D6-64 batch requires a multiple of {BLOCK64.byte_length} bytes, got {len(data)}",
        )
    out: List[int] = []
    for i in range(0, len(data), BLOCK64.byte_length):
        out.extend(unpack_block64(data[i : i + BLOCK64.byte_length]))
    return out


def pack_block64_many_into(symbols: Sequence[int], buffer, offset: int = 0) -> int:
    """Pack many D6-64 blocks into a caller-provided writable buffer."""
    data = pack_block64_many(symbols)
    view = _writable(_view(buffer))
    _check_region(view, offset, len(data))
    view[offset : offset + len(data)] = data
    return len(data)


def unpack_block64_many_into(data: bytes, buffer, offset: int = 0) -> int:
    """Unpack many D6-64 blocks into a caller-provided writable buffer."""
    payload = bytes(unpack_block64_many(data))
    view = _writable(_view(buffer))
    _check_region(view, offset, len(payload))
    view[offset : offset + len(payload)] = payload
    return len(payload)


def pack_block128(symbols: Sequence[int]) -> bytes:
    return pack_block(symbols, BLOCK128)


def unpack_block128(data: bytes) -> List[int]:
    return unpack_block(data, BLOCK128)


def pack_block40(symbols: Sequence[int]) -> bytes:
    return pack_block(symbols, BLOCK40)


def unpack_block40(data: bytes) -> List[int]:
    return unpack_block(data, BLOCK40)


# ---------------------------------------------------------------------------
# Dual-plane fixed blocks
# ---------------------------------------------------------------------------

from .dual_plane import (  # noqa: E402
    pack_bits_bytes,
    pack_trits_bytes,
    unpack_bits_bytes,
    unpack_trits_bytes,
)


@dataclass(frozen=True)
class DualPlaneBlockLayout:
    """A fixed block whose payload is `bit plane || trit plane`."""

    name: str
    symbols: int
    byte_length: int
    bit_bytes: int
    trit_bytes: int
    bit_length: int

    def __post_init__(self) -> None:
        if self.bit_bytes != (self.symbols + 7) // 8:
            raise ValueError(f"{self.name}: bit_bytes mismatch")
        if self.trit_bytes != (self.symbols + 4) // 5:
            raise ValueError(f"{self.name}: trit_bytes mismatch")
        if self.bit_bytes + self.trit_bytes != self.byte_length:
            raise ValueError(f"{self.name}: bit_bytes + trit_bytes != byte_length")


BLOCK64_DP = DualPlaneBlockLayout(
    name="D6-64-DP",
    symbols=24,
    byte_length=8,
    bit_bytes=3,
    trit_bytes=5,
    bit_length=64,
)

BLOCK128_DP = DualPlaneBlockLayout(
    name="D6-128-DP",
    symbols=48,
    byte_length=16,
    bit_bytes=6,
    trit_bytes=10,
    bit_length=128,
)

BLOCK40_DP = DualPlaneBlockLayout(
    name="D6-40-DP",
    symbols=40,
    byte_length=13,
    bit_bytes=5,
    trit_bytes=8,
    bit_length=104,
)

LAYOUTS_DP: Dict[str, DualPlaneBlockLayout] = {
    BLOCK64_DP.name: BLOCK64_DP,
    BLOCK128_DP.name: BLOCK128_DP,
    BLOCK40_DP.name: BLOCK40_DP,
}


def get_dp_layout(name: str) -> DualPlaneBlockLayout:
    try:
        return LAYOUTS_DP[name]
    except KeyError as exc:
        raise Dual6Error(ErrorCode.INVALID_LAYOUT, f"unknown dual-plane block layout {name!r}") from exc


def pack_block_dp(bits: Sequence[int], trits: Sequence[int], layout: DualPlaneBlockLayout) -> bytes:
    """Pack bit and trit channels into a dual-plane fixed block."""
    if len(bits) != len(trits) or len(bits) != layout.symbols:
        raise Dual6Error(
            ErrorCode.WIDTH_MISMATCH,
            f"{layout.name} requires {layout.symbols} bits and trits, "
            f"got {len(bits)} and {len(trits)}",
        )
    bit_data = pack_bits_bytes(bits)
    trit_data = pack_trits_bytes(trits)
    if len(bit_data) != layout.bit_bytes or len(trit_data) != layout.trit_bytes:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"{layout.name} internal length mismatch: "
            f"bits {len(bit_data)}/{layout.bit_bytes}, trits {len(trit_data)}/{layout.trit_bytes}",
        )
    return bit_data + trit_data


def unpack_block_dp(data: bytes, layout: DualPlaneBlockLayout) -> Tuple[List[int], List[int]]:
    """Unpack a dual-plane fixed block into `(bits, trits)`."""
    if len(data) != layout.byte_length:
        raise Dual6Error(
            ErrorCode.INVALID_LAYOUT,
            f"{layout.name} requires {layout.byte_length} bytes, got {len(data)}",
        )
    bit_data = data[: layout.bit_bytes]
    trit_data = data[layout.bit_bytes :]
    bits = unpack_bits_bytes(bit_data, layout.symbols)
    trits = unpack_trits_bytes(trit_data, layout.symbols)
    return bits, trits


def pack_block64_dp(bits: Sequence[int], trits: Sequence[int]) -> bytes:
    return pack_block_dp(bits, trits, BLOCK64_DP)


def unpack_block64_dp(data: bytes) -> Tuple[List[int], List[int]]:
    return unpack_block_dp(data, BLOCK64_DP)


def pack_block128_dp(bits: Sequence[int], trits: Sequence[int]) -> bytes:
    return pack_block_dp(bits, trits, BLOCK128_DP)


def unpack_block128_dp(data: bytes) -> Tuple[List[int], List[int]]:
    return unpack_block_dp(data, BLOCK128_DP)


def pack_block40_dp(bits: Sequence[int], trits: Sequence[int]) -> bytes:
    return pack_block_dp(bits, trits, BLOCK40_DP)


def unpack_block40_dp(data: bytes) -> Tuple[List[int], List[int]]:
    return unpack_block_dp(data, BLOCK40_DP)
