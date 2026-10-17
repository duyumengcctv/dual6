"""Adapters between single-channel streams and Dual6 containers.

These adapters are storage bridges only.  They fill the missing channel with a
constant (0 by default) so that existing binary or ternary data can travel in a
Dual6 block.  They do not perform arithmetic or numerical base conversion.

Scope note: Dual6 v0.3 is a storage tool.  It deliberately does not ship
connectors for external formats or model runtimes (for example GGUF / GGML
quantisation blocks).  Downstream projects may build those on top of the frozen
core API.
"""

from .binary import (
    bits_to_dual6_block64,
    bits_to_symbols,
    dual6_block64_to_bits,
    symbols_to_bits,
)
from .ternary import (
    dual6_block64_to_trits,
    symbols_to_trits,
    trits_to_dual6_block64,
    trits_to_symbols,
)

__all__ = [
    "bits_to_dual6_block64",
    "bits_to_symbols",
    "dual6_block64_to_bits",
    "dual6_block64_to_trits",
    "symbols_to_bits",
    "symbols_to_trits",
    "trits_to_dual6_block64",
    "trits_to_symbols",
]
