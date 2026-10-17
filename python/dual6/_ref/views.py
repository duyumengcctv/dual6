"""Read-only channel views over a Dual6 symbol sequence.

These are convenience wrappers.  They do not copy unless the caller asks for a
list, and they keep the "container -> one channel" boundary explicit.
"""

from __future__ import annotations

from typing import Iterator, Sequence

from .symbol import decode_digit


class BitView(Sequence[int]):
    """Read-only bit view over a symbol sequence."""

    __slots__ = ("_symbols",)

    def __init__(self, symbols: Sequence[int]) -> None:
        self._symbols = symbols

    def __len__(self) -> int:
        return len(self._symbols)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        return self._symbols[index] // 3

    def __iter__(self) -> Iterator[int]:
        for d in self._symbols:
            yield d // 3

    def to_list(self) -> list[int]:
        return list(self)


class TritView(Sequence[int]):
    """Read-only balanced-trit view over a symbol sequence."""

    __slots__ = ("_symbols",)

    def __init__(self, symbols: Sequence[int]) -> None:
        self._symbols = symbols

    def __len__(self) -> int:
        return len(self._symbols)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        return self._symbols[index] % 3 - 1

    def __iter__(self) -> Iterator[int]:
        for d in self._symbols:
            yield d % 3 - 1

    def to_list(self) -> list[int]:
        return list(self)


def bit_view(symbols: Sequence[int]) -> BitView:
    return BitView(symbols)


def trit_view(symbols: Sequence[int]) -> TritView:
    return TritView(symbols)
