"""Conformance checks between the pure-Python reference and a native backend.

Native backends are optional.  When ``dual6._native`` is not built, the test
suite still uses this module to self-check ``dual6._ref``.

The harness covers **every** public native-backed callable and compares error
*code* (not just "an error happened"), so a native function that maps a bad
input to the wrong ``ErrorCode`` fails loudly.
"""

from __future__ import annotations

import random
from typing import Any, Callable, List, Tuple

Result = Tuple[str, Any]


def _short(value: Any, limit: int = 120) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[:limit] + "..."


def _call(fn: Callable[..., Any], *args: Any) -> Result:
    """Return ``("ok", value)`` or ``("err", error_code)``."""
    try:
        return ("ok", fn(*args))
    except Exception as exc:  # noqa: BLE001 - the point is to compare failures
        code = getattr(exc, "code", None)
        if code is not None:
            return ("err", getattr(code, "value", code))
        return ("err", type(exc).__name__)


def _compare(name: str, ref_fn: Callable[..., Any], native_fn: Callable[..., Any], *args: Any) -> List[str]:
    ref = _call(ref_fn, *args)
    native = _call(native_fn, *args)
    if ref != native:
        return [f"{name}{_short(args)}: ref={_short(ref)} native={_short(native)}"]
    return []


def _compare_writer(
    name: str,
    ref_fn: Callable[..., Any],
    native_fn: Callable[..., Any],
    make_args: Callable[[bytearray], list],
    size: int = 64,
) -> List[str]:
    """Compare a pack-into-buffer function, including the written bytes."""
    ref_buf = bytearray(size)
    native_buf = bytearray(size)
    ref = _call(ref_fn, *make_args(ref_buf))
    native = _call(native_fn, *make_args(native_buf))
    if ref != native:
        return [f"{name}: ref={ref!r} native={native!r}"]
    if ref[0] == "ok" and bytes(ref_buf) != bytes(native_buf):
        return [f"{name}: buffer mismatch ref={bytes(ref_buf).hex()} native={bytes(native_buf).hex()}"]
    return []


class _RefProxy:
    """Resolve a name from the reference package, then from ``dual6.adapters``.

    The single-channel adapter functions live in ``dual6.adapters`` rather than
    ``dual6._ref``; this proxy lets the harness treat both as "the reference".
    """

    def __init__(self, *namespaces: Any) -> None:
        self._namespaces = namespaces

    def __getattr__(self, name: str) -> Any:
        for namespace in self._namespaces:
            try:
                return getattr(namespace, name)
            except AttributeError:
                continue
        raise AttributeError(name)


def run_conformance(ref: Any, native: Any, adapter_ref: Any = None) -> List[str]:
    """Run deterministic cases against two API namespaces.

    ``adapter_ref`` supplies the reference implementation of the single-channel
    adapters (``dual6.adapters``).  Missing native attributes are skipped, not
    failed, so partial native backends can be brought up incrementally.
    """
    if adapter_ref is not None:
        ref = _RefProxy(ref, adapter_ref)
    mismatches: List[str] = []
    rng = random.Random(1234)

    def has(name: str) -> bool:
        return hasattr(native, name) and hasattr(ref, name)

    if has("encode_digit") and has("decode_digit"):
        for b in (0, 1):
            for t in (-1, 0, 1):
                mismatches += _compare("encode_digit", ref.encode_digit, native.encode_digit, b, t)
        for d in range(6):
            mismatches += _compare("decode_digit", ref.decode_digit, native.decode_digit, d)

    if has("mux") and has("demux"):
        for width in (0, 1, 3, 8, 24):
            bits = [rng.randrange(2) for _ in range(width)]
            trits = [rng.choice((-1, 0, 1)) for _ in range(width)]
            mismatches += _compare("mux", ref.mux, native.mux, bits, trits)
            symbols = ref.mux(bits, trits)
            mismatches += _compare("demux", ref.demux, native.demux, symbols)

    if has("pack_digits") and has("unpack_digits"):
        for width in (0, 1, 5, 24, 48):
            symbols = [rng.randrange(6) for _ in range(width)]
            mismatches += _compare("pack_digits", ref.pack_digits, native.pack_digits, symbols)
            value = ref.pack_digits(symbols)
            mismatches += _compare("unpack_digits", ref.unpack_digits, native.unpack_digits, value, width)

    if has("max_interleaved"):
        for width in (0, 1, 5, 24, 48, 49, 100):
            mismatches += _compare("max_interleaved", ref.max_interleaved, native.max_interleaved, width)

    if has("fits_unsigned_word"):
        for width, word_bits in ((0, 0), (4, 10), (24, 63), (24, 64), (25, 64), (100, 512), (100, 256)):
            mismatches += _compare(
                "fits_unsigned_word", ref.fits_unsigned_word, native.fits_unsigned_word, width, word_bits
            )

    if has("pack_bits_bytes") and has("unpack_bits_bytes"):
        for width in list(range(0, 40)) + [64, 129]:
            bits = [rng.randrange(2) for _ in range(width)]
            mismatches += _compare("pack_bits_bytes", ref.pack_bits_bytes, native.pack_bits_bytes, bits)
            data = ref.pack_bits_bytes(bits)
            mismatches += _compare("unpack_bits_bytes", ref.unpack_bits_bytes, native.unpack_bits_bytes, data, width)

    if has("pack_trits_bytes") and has("unpack_trits_bytes"):
        for width in list(range(0, 40)) + [64, 129]:
            trits = [rng.choice((-1, 0, 1)) for _ in range(width)]
            mismatches += _compare("pack_trits_bytes", ref.pack_trits_bytes, native.pack_trits_bytes, trits)
            data = ref.pack_trits_bytes(trits)
            mismatches += _compare("unpack_trits_bytes", ref.unpack_trits_bytes, native.unpack_trits_bytes, data, width)

    if has("bits_bytes_len") and has("trits_bytes_len"):
        for width in (0, 1, 7, 8, 9, 40, 129):
            mismatches += _compare("bits_bytes_len", ref.bits_bytes_len, native.bits_bytes_len, width)
            mismatches += _compare("trits_bytes_len", ref.trits_bytes_len, native.trits_bytes_len, width)

    if has("pack_bits_into") and has("unpack_bits_from"):
        bits = [rng.randrange(2) for _ in range(19)]
        data = ref.pack_bits_bytes(bits)
        for offset in (0, 1, 7):
            mismatches += _compare_writer(
                "pack_bits_into",
                ref.pack_bits_into,
                native.pack_bits_into,
                lambda buf, offset=offset, bits=bits: [bits, buf, offset],
            )
            buf = bytearray(offset) + bytearray(data) + bytearray(8)
            mismatches += _compare("unpack_bits_from", ref.unpack_bits_from, native.unpack_bits_from, buf, 19, offset)

    if has("pack_trits_into") and has("unpack_trits_from"):
        trits = [rng.choice((-1, 0, 1)) for _ in range(19)]
        data = ref.pack_trits_bytes(trits)
        for offset in (0, 1, 3):
            mismatches += _compare_writer(
                "pack_trits_into",
                ref.pack_trits_into,
                native.pack_trits_into,
                lambda buf, offset=offset, trits=trits: [trits, buf, offset],
            )
            buf = bytearray(offset) + bytearray(data) + bytearray(8)
            mismatches += _compare("unpack_trits_from", ref.unpack_trits_from, native.unpack_trits_from, buf, 19, offset)

    if has("pack_dual_plane_into") and has("unpack_dual_plane_from"):
        bits = [rng.randrange(2) for _ in range(19)]
        trits = [rng.choice((-1, 0, 1)) for _ in range(19)]
        mismatches += _compare_writer(
            "pack_dual_plane_into",
            ref.pack_dual_plane_into,
            native.pack_dual_plane_into,
            lambda buf, bits=bits, trits=trits: [bits, trits, buf, 0],
        )
        payload = bytearray(ref.pack_dual_plane_into(bits, trits, bytearray(64)))
        mismatches += _compare(
            "unpack_dual_plane_from", ref.unpack_dual_plane_from, native.unpack_dual_plane_from, payload, 19, 0
        )

    blocks = [
        ("pack_block64", "unpack_block64", 24),
        ("pack_block128", "unpack_block128", 48),
        ("pack_block40", "unpack_block40", 40),
    ]
    for pack_name, unpack_name, symbols in blocks:
        if has(pack_name) and has(unpack_name):
            data_symbols = [rng.randrange(6) for _ in range(symbols)]
            mismatches += _compare(pack_name, getattr(ref, pack_name), getattr(native, pack_name), data_symbols)
            blob = getattr(ref, pack_name)(data_symbols)
            mismatches += _compare(unpack_name, getattr(ref, unpack_name), getattr(native, unpack_name), blob)

    if has("pack_block64_many") and has("unpack_block64_many"):
        flat = [rng.randrange(6) for _ in range(24 * 8)]
        mismatches += _compare(
            "pack_block64_many", ref.pack_block64_many, native.pack_block64_many, flat
        )
        blob = ref.pack_block64_many(flat)
        mismatches += _compare(
            "unpack_block64_many", ref.unpack_block64_many, native.unpack_block64_many, blob
        )

    if has("pack_block64_many_into") and has("unpack_block64_many_into"):
        flat = bytes(rng.randrange(6) for _ in range(24 * 4))
        mismatches += _compare_writer(
            "pack_block64_many_into",
            ref.pack_block64_many_into,
            native.pack_block64_many_into,
            lambda buf, flat=flat: [flat, buf, 0],
            size=64,
        )
        packed = ref.pack_block64_many(list(flat))
        mismatches += _compare_writer(
            "unpack_block64_many_into",
            ref.unpack_block64_many_into,
            native.unpack_block64_many_into,
            lambda buf, packed=packed: [packed, buf, 0],
            size=len(flat) + 8,
        )

    dp_blocks = [
        ("pack_block64_dp", "unpack_block64_dp", 24),
        ("pack_block128_dp", "unpack_block128_dp", 48),
        ("pack_block40_dp", "unpack_block40_dp", 40),
    ]
    for pack_name, unpack_name, symbols in dp_blocks:
        if has(pack_name) and has(unpack_name):
            bits = [rng.randrange(2) for _ in range(symbols)]
            trits = [rng.choice((-1, 0, 1)) for _ in range(symbols)]
            mismatches += _compare(pack_name, getattr(ref, pack_name), getattr(native, pack_name), bits, trits)
            blob = getattr(ref, pack_name)(bits, trits)
            mismatches += _compare(unpack_name, getattr(ref, unpack_name), getattr(native, unpack_name), blob)

    for pack_name, unpack_name in (("pack_dual_plane", "unpack_dual_plane"), ("pack_dual_plane_v1", "unpack_dual_plane_v1")):
        if has(pack_name) and has(unpack_name):
            bits = [rng.randrange(2) for _ in range(17)]
            trits = [rng.choice((-1, 0, 1)) for _ in range(17)]
            mismatches += _compare(pack_name, getattr(ref, pack_name), getattr(native, pack_name), bits, trits)
            frame = getattr(ref, pack_name)(bits, trits)
            mismatches += _compare(unpack_name, getattr(ref, unpack_name), getattr(native, unpack_name), frame)

    if has("pack_dual_plane_v2") and has("unpack_dual_plane_v2"):
        width = 48
        bits = [rng.randrange(2) for _ in range(width)]
        trits = [rng.choice((-1, 0, 1)) for _ in range(width)]
        cases = ((getattr(ref, "DTYPE_RAW", 0), 0), (getattr(ref, "DTYPE_TERNARY", 2), 24))
        for dtype, block_symbols in cases:
            mismatches += _compare(
                "pack_dual_plane_v2", ref.pack_dual_plane_v2, native.pack_dual_plane_v2, bits, trits, dtype, block_symbols
            )
            frame = ref.pack_dual_plane_v2(bits, trits, dtype=dtype, block_symbols=block_symbols)
            mismatches += _compare("unpack_dual_plane_v2", ref.unpack_dual_plane_v2, native.unpack_dual_plane_v2, frame)

    if has("frame_version") and has("unpack_frame_auto"):
        bits = [rng.randrange(2) for _ in range(11)]
        trits = [rng.choice((-1, 0, 1)) for _ in range(11)]
        for pack_name in ("pack_dual_plane", "pack_dual_plane_v1", "pack_dual_plane_v2"):
            if not has(pack_name):
                continue
            frame = getattr(ref, pack_name)(bits, trits)
            mismatches += _compare("frame_version", ref.frame_version, native.frame_version, frame)
            mismatches += _compare("unpack_frame_auto", ref.unpack_frame_auto, native.unpack_frame_auto, frame)
            if has("unpack_frame_auto_buffer"):
                for factory in (bytes, bytearray, memoryview):
                    mismatches += _compare(
                        "unpack_frame_auto_buffer", ref.unpack_frame_auto_buffer, native.unpack_frame_auto_buffer, factory(frame)
                    )

    for name, width in (("trits_to_symbols", 6), ("bits_to_symbols", 6), ("trits_to_dual6_block64", 24), ("bits_to_dual6_block64", 24)):
        if not has(name):
            continue
        if name.startswith("trits"):
            values = [rng.choice((-1, 0, 1)) for _ in range(width)]
        else:
            values = [rng.randrange(2) for _ in range(width)]
        mismatches += _compare(name, getattr(ref, name), getattr(native, name), values)

    if has("symbols_to_bits") and has("symbols_to_trits"):
        bits = [rng.randrange(2) for _ in range(16)]
        trits = [rng.choice((-1, 0, 1)) for _ in range(16)]
        symbols = ref.mux(bits, trits)
        mismatches += _compare("symbols_to_bits", ref.symbols_to_bits, native.symbols_to_bits, symbols)
        mismatches += _compare("symbols_to_trits", ref.symbols_to_trits, native.symbols_to_trits, symbols)

    if has("dual6_block64_to_bits") and has("dual6_block64_to_trits"):
        bits = [rng.randrange(2) for _ in range(24)]
        trits = [rng.choice((-1, 0, 1)) for _ in range(24)]
        bit_block = ref.bits_to_dual6_block64(bits)
        trit_block = ref.trits_to_dual6_block64(trits)
        mismatches += _compare("dual6_block64_to_bits", ref.dual6_block64_to_bits, native.dual6_block64_to_bits, bit_block)
        mismatches += _compare(
            "dual6_block64_to_trits", ref.dual6_block64_to_trits, native.dual6_block64_to_trits, trit_block
        )

    mismatches += _error_conformance(ref, native)
    return mismatches


def _error_conformance(ref: Any, native: Any) -> List[str]:
    """Compare the ErrorCode produced for a catalogue of invalid inputs."""
    mismatches: List[str] = []

    def has(name: str) -> bool:
        return hasattr(native, name) and hasattr(ref, name)

    def err(name: str, *args: Any) -> None:
        if has(name):
            mismatches.extend(_compare(f"{name}[error]", getattr(ref, name), getattr(native, name), *args))

    err("encode_digit", 2, 0)
    err("encode_digit", 0, 2)
    err("decode_digit", 6)
    err("decode_digit", -1)
    err("mux", [0, 1], [0])
    err("pack_digits", [0, 6])
    err("unpack_digits", 1000, 5)
    err("unpack_digits", 0, -1)
    err("max_interleaved", -1)
    err("fits_unsigned_word", -1, 8)
    err("pack_bits_bytes", [2])
    err("unpack_bits_bytes", b"\x01", 3)
    err("unpack_bits_bytes", b"\x00", 0)
    err("pack_trits_bytes", [2])
    err("unpack_trits_bytes", b"\xff", 1)
    err("unpack_trits_bytes", b"\x00\x00", 1)
    err("pack_block64", [0] * 23)
    err("pack_block64_many", [0] * 23)
    err("pack_block64_many_into", bytes([0] * 23), bytearray(8), 0)
    err("unpack_block64_many_into", bytes([0] * 7), bytearray(24), 0)
    err("pack_block64_many_into", bytes([0] * 24), bytearray(4), 0)
    err("unpack_block64_many", b"\x00" * 7)
    err("unpack_block64", b"\x00" * 7)
    err("pack_block128", [0] * 47)
    err("unpack_block128", b"\x00" * 15)
    err("pack_block40", [0] * 39)
    err("unpack_block40", b"\x00" * 12)
    err("pack_block64_dp", [0] * 23, [0] * 23)
    err("unpack_block64_dp", b"\x00" * 7)
    err("pack_dual_plane", [0, 1], [0])
    err("unpack_dual_plane", b"XXXX" + b"\x00" * 20)
    err("unpack_dual_plane_v1", b"XXXX" + b"\x00" * 20)
    err("frame_version", b"XXXX")
    err("unpack_frame_auto", b"XXXX" + b"\x00" * 20)

    if has("pack_dual_plane_v1") and has("unpack_dual_plane_v1"):
        frame = bytearray(ref.pack_dual_plane_v1([1, 0, 1], [1, -1, 0]))
        frame[-1] ^= 0xFF
        err("unpack_dual_plane_v1", bytes(frame))

    if has("pack_dual_plane_into"):
        err("pack_dual_plane_into", [0] * 100, [0] * 100, bytearray(4), 0)
    if has("unpack_bits_from"):
        err("unpack_bits_from", bytearray(1), 100, 0)

    return mismatches


def self_check(ref: Any) -> List[str]:
    """Run the conformance harness against the reference implementation."""
    return run_conformance(ref, ref)
