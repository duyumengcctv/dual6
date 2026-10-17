"""Command-line interface for the Dual6 storage container.

Storage only.  It encodes, decodes, packs, unpacks, and inspects frames; it
does not perform arithmetic on ``d``.
"""

from __future__ import annotations

import argparse
import json
import platform
import struct
import sys
from functools import partial
from typing import Any, Dict, List, Optional, Sequence

from . import (
    Dual6Error,
    ErrorCode,
    __version__,
    demux,
    mux,
    pack_block40,
    pack_block40_dp,
    pack_block64,
    pack_block64_dp,
    pack_block128,
    pack_block128_dp,
    pack_dual_plane,
    pack_dual_plane_v1,
    pack_dual_plane_v2,
    unpack_block40,
    unpack_block40_dp,
    unpack_block64,
    unpack_block64_dp,
    unpack_block128,
    unpack_block128_dp,
    unpack_dual_plane,
    unpack_dual_plane_v1,
    unpack_dual_plane_v2,
)

TRIT_CHARS = {"T": -1, "t": -1, "-": -1, "0": 0, "P": 1, "p": 1, "+": 1}
TRIT_TO_CHAR = {-1: "T", 0: "0", 1: "P"}


def _clean(text: str) -> str:
    return text.replace(",", "").replace("_", "").strip()


def parse_bits(text: str) -> List[int]:
    text = _clean(text)
    if any(ch not in "01" for ch in text):
        raise ValueError(f"bits may only contain 0 and 1, got {text!r}")
    return [int(ch) for ch in text]


def format_bits(bits: Sequence[int]) -> str:
    return "".join(str(b) for b in bits)


def parse_trits(text: str) -> List[int]:
    text = _clean(text).replace("-1", "T").replace("+1", "P")
    out: List[int] = []
    for ch in text:
        if ch not in TRIT_CHARS:
            raise ValueError(f"bad trit character {ch!r}")
        out.append(TRIT_CHARS[ch])
    return out


def format_trits(trits: Sequence[int]) -> str:
    return "".join(TRIT_TO_CHAR[t] for t in trits)


def parse_symbols(text: str) -> List[int]:
    text = _clean(text)
    if any(ch not in "012345" for ch in text):
        raise ValueError(f"symbols may only contain 0..5, got {text!r}")
    return [int(ch) for ch in text]


def format_symbols(symbols: Sequence[int]) -> str:
    return "".join(str(d) for d in symbols)


def _bits_trits(args: argparse.Namespace) -> tuple[List[int], List[int]]:
    bits = parse_bits(args.bits)
    trits = parse_trits(args.trits)
    if len(bits) != len(trits):
        raise ValueError(f"bits length {len(bits)} != trits length {len(trits)}")
    return bits, trits


def cmd_encode(args: argparse.Namespace) -> Dict[str, Any]:
    bits, trits = _bits_trits(args)
    symbols = mux(bits, trits)
    return {"symbols": format_symbols(symbols), "width": len(symbols)}


def cmd_decode(args: argparse.Namespace) -> Dict[str, Any]:
    symbols = parse_symbols(args.symbols)
    bits, trits = demux(symbols)
    return {"bits": format_bits(bits), "trits": format_trits(trits), "width": len(symbols)}


def cmd_pack_block64(args: argparse.Namespace) -> Dict[str, Any]:
    data = pack_block64(parse_symbols(args.symbols))
    return {"hex": data.hex(), "bytes": len(data)}


def cmd_unpack_block64(args: argparse.Namespace) -> Dict[str, Any]:
    symbols = unpack_block64(bytes.fromhex(_clean(args.hex)))
    return {"symbols": format_symbols(symbols), "width": len(symbols)}


def cmd_pack_block64_dp(args: argparse.Namespace) -> Dict[str, Any]:
    bits, trits = _bits_trits(args)
    data = pack_block64_dp(bits, trits)
    return {"hex": data.hex(), "bytes": len(data)}


def cmd_unpack_block64_dp(args: argparse.Namespace) -> Dict[str, Any]:
    bits, trits = unpack_block64_dp(bytes.fromhex(_clean(args.hex)))
    return {"bits": format_bits(bits), "trits": format_trits(trits), "width": len(bits)}


def _cmd_pack_symbols(args: argparse.Namespace, packer) -> Dict[str, Any]:
    data = packer(parse_symbols(args.symbols))
    return {"hex": data.hex(), "bytes": len(data)}


def _cmd_unpack_symbols(args: argparse.Namespace, unpacker) -> Dict[str, Any]:
    symbols = unpacker(bytes.fromhex(_clean(args.hex)))
    return {"symbols": format_symbols(symbols), "width": len(symbols)}


def _cmd_pack_dp(args: argparse.Namespace, packer) -> Dict[str, Any]:
    bits, trits = _bits_trits(args)
    data = packer(bits, trits)
    return {"hex": data.hex(), "bytes": len(data)}


def _cmd_unpack_dp(args: argparse.Namespace, unpacker) -> Dict[str, Any]:
    bits, trits = unpacker(bytes.fromhex(_clean(args.hex)))
    return {"bits": format_bits(bits), "trits": format_trits(trits), "width": len(bits)}


def _frame_version(data: bytes) -> int:
    if len(data) < 4:
        raise ValueError("frame shorter than magic")
    magic = data[:4]
    if magic == b"D6P0":
        return 0
    if magic == b"D6P1":
        return 1
    if magic == b"D6P2":
        return 2
    raise ValueError(f"unknown frame magic {magic!r}")


def cmd_pack_frame(args: argparse.Namespace) -> Dict[str, Any]:
    bits, trits = _bits_trits(args)
    if args.version == 1:
        if args.dtype != 0 or args.block_symbols != 0 or args.flags != 0:
            raise ValueError("version 1 does not support dtype / block-symbols / flags")
        frame = pack_dual_plane_v1(bits, trits)
    else:
        frame = pack_dual_plane_v2(
            bits,
            trits,
            dtype=args.dtype,
            block_symbols=args.block_symbols,
            flags=args.flags,
        )
    return {"hex": frame.hex(), "bytes": len(frame), "version": args.version}


def cmd_unpack_frame(args: argparse.Namespace) -> Dict[str, Any]:
    data = bytes.fromhex(_clean(args.hex))
    version = _frame_version(data)
    meta: Optional[dict] = None
    if version == 0:
        bits, trits = unpack_dual_plane(data)
    elif version == 1:
        bits, trits = unpack_dual_plane_v1(data)
    else:
        bits, trits, meta = unpack_dual_plane_v2(data)
    result: Dict[str, Any] = {
        "bits": format_bits(bits),
        "trits": format_trits(trits),
        "width": len(bits),
        "version": version,
    }
    if meta is not None:
        result["meta"] = meta
    return result


def cmd_inspect_frame(args: argparse.Namespace) -> Dict[str, Any]:
    data = bytes.fromhex(_clean(args.hex))
    version = _frame_version(data)
    try:
        if version == 0:
            bits, trits = unpack_dual_plane(data)
            magic, ver, width0, bit_len, trit_len = struct.unpack_from("<4sBIII", data, 0)
            meta = {
                "header_width": width0,
                "bit_bytes_len": bit_len,
                "trit_bytes_len": trit_len,
            }
        elif version == 1:
            bits, trits = unpack_dual_plane_v1(data)
            meta = None
        else:
            bits, trits, meta = unpack_dual_plane_v2(data)
        info: Dict[str, Any] = {
            "magic": f"D6P{version}",
            "version": data[4] if len(data) > 4 else None,
            "width": len(bits),
            "crc_ok": None if version == 0 else True,
            "decoded": {"bits": format_bits(bits), "trits": format_trits(trits)},
        }
        if meta is not None:
            info.update(meta)
        return info
    except Dual6Error as exc:
        if exc.code != ErrorCode.CRC_MISMATCH:
            raise
        return {
            "magic": f"D6P{version}",
            "version": data[4] if len(data) > 4 else None,
            "crc_ok": False,
            "decoded": None,
        }


def cmd_info(args: argparse.Namespace) -> Dict[str, Any]:
    """Return runtime / backend / version information."""
    import dual6

    backend = getattr(dual6, "__backend__", "ref")
    native_path = None
    if backend == "native":
        native = getattr(dual6, "_native_module", None)
        native_path = getattr(native, "__file__", None)
    return {
        "name": "dual6",
        "version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "backend": backend,
        "native_path": native_path,
    }


def cmd_number(args: argparse.Namespace) -> Dict[str, Any]:
    """Encode one non-negative integer and show both lossless views."""
    from .exact_dual import (
        encode_number,
        read_binary,
        read_ternary,
        to_balanced_ternary,
        to_binary_digits,
    )

    value = args.value
    if value < 0:
        raise ValueError("--value must be a non-negative integer")
    symbols = encode_number(value)
    trits_lsb = to_balanced_ternary(value)
    padded_trits = trits_lsb + [0] * (len(symbols) - len(trits_lsb))
    container = sum(d * (6 ** i) for i, d in enumerate(symbols))
    slot3 = sum(d << (3 * i) for i, d in enumerate(symbols))
    return {
        "value": value,
        "binary": "".join(str(b) for b in reversed(to_binary_digits(value))),
        "balanced_ternary": format_trits(list(reversed(trits_lsb))),
        "balanced_ternary_padded": format_trits(list(reversed(padded_trits))),
        "symbols": format_symbols(symbols),
        "length": len(symbols),
        "container_value": container,
        "container_hex": hex(container),
        "slot3_value": slot3,
        "slot3_hex": hex(slot3),
        "binary_view": read_binary(symbols),
        "ternary_view": read_ternary(symbols),
    }


def cmd_demo(args: argparse.Namespace) -> None:
    """Human-readable demo: one value, two lossless views."""
    from .exact_dual import (
        encode_number,
        read_binary,
        read_ternary,
        to_balanced_ternary,
        to_binary_digits,
    )

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    value = args.value
    if value < 0:
        raise ValueError("--value must be a non-negative integer")
    symbols = encode_number(value)
    trits_lsb = to_balanced_ternary(value)
    padded_trits = trits_lsb + [0] * (len(symbols) - len(trits_lsb))
    binary = "".join(str(b) for b in reversed(to_binary_digits(value)))
    ternary = format_trits(list(reversed(trits_lsb)))
    ternary_padded = format_trits(list(reversed(padded_trits)))
    container = sum(d * (6 ** i) for i, d in enumerate(symbols))
    slot3 = sum(d << (3 * i) for i, d in enumerate(symbols))

    print("Dual6 / 二生三 — 一个数，两种读法")
    print("=" * 46)
    print(f"N              = {value}")
    print(f"二进制展开     = {binary}")
    print(f"平衡三进制     = {ternary}  (补齐到 {len(symbols)} 位: {ternary_padded})")
    print(f"码元(低位在前) = {format_symbols(symbols)}")
    print(f"容器值(交错)   = {container} ({hex(container)})")
    print(f"容器值(3bit)   = {slot3} ({hex(slot3)})")
    print("-" * 46)
    print(f"二进制视图读回 = {read_binary(symbols)}")
    print(f"三进制视图读回 = {read_ternary(symbols)}")
    print("-" * 46)

    if args.check > 0:
        for n in range(args.check):
            s = encode_number(n)
            if read_binary(s) != n or read_ternary(s) != n:
                raise ValueError(f"roundtrip failed at N={n}")
        print(f"0..{args.check - 1} 全量对拍通过：两个视图都等于 N")
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dual6", description="Dual6 storage container CLI")
    parser.add_argument("--version", action="version", version=f"dual6 {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("encode", help="bits + trits -> symbols")
    p.add_argument("--bits", required=True)
    p.add_argument("--trits", required=True)
    p.set_defaults(func=cmd_encode)

    p = sub.add_parser("decode", help="symbols -> bits + trits")
    p.add_argument("--symbols", required=True)
    p.set_defaults(func=cmd_decode)

    p = sub.add_parser("pack-block64", help="24 symbols -> 8-byte interleaved hex")
    p.add_argument("--symbols", required=True)
    p.set_defaults(func=cmd_pack_block64)

    p = sub.add_parser("unpack-block64", help="8-byte interleaved hex -> 24 symbols")
    p.add_argument("--hex", required=True)
    p.set_defaults(func=cmd_unpack_block64)

    p = sub.add_parser("pack-block64-dp", help="24 bits + 24 trits -> 8-byte dual-plane hex")
    p.add_argument("--bits", required=True)
    p.add_argument("--trits", required=True)
    p.set_defaults(func=cmd_pack_block64_dp)

    p = sub.add_parser("unpack-block64-dp", help="8-byte dual-plane hex -> bits + trits")
    p.add_argument("--hex", required=True)
    p.set_defaults(func=cmd_unpack_block64_dp)

    p = sub.add_parser("pack-block128", help="48 symbols -> 16-byte interleaved hex")
    p.add_argument("--symbols", required=True)
    p.set_defaults(func=partial(_cmd_pack_symbols, packer=pack_block128))

    p = sub.add_parser("unpack-block128", help="16-byte interleaved hex -> 48 symbols")
    p.add_argument("--hex", required=True)
    p.set_defaults(func=partial(_cmd_unpack_symbols, unpacker=unpack_block128))

    p = sub.add_parser("pack-block40", help="40 symbols -> 13-byte interleaved hex")
    p.add_argument("--symbols", required=True)
    p.set_defaults(func=partial(_cmd_pack_symbols, packer=pack_block40))

    p = sub.add_parser("unpack-block40", help="13-byte interleaved hex -> 40 symbols")
    p.add_argument("--hex", required=True)
    p.set_defaults(func=partial(_cmd_unpack_symbols, unpacker=unpack_block40))

    p = sub.add_parser("pack-block128-dp", help="48 bits + 48 trits -> 16-byte dual-plane hex")
    p.add_argument("--bits", required=True)
    p.add_argument("--trits", required=True)
    p.set_defaults(func=partial(_cmd_pack_dp, packer=pack_block128_dp))

    p = sub.add_parser("unpack-block128-dp", help="16-byte dual-plane hex -> bits + trits")
    p.add_argument("--hex", required=True)
    p.set_defaults(func=partial(_cmd_unpack_dp, unpacker=unpack_block128_dp))

    p = sub.add_parser("pack-block40-dp", help="40 bits + 40 trits -> 13-byte dual-plane hex")
    p.add_argument("--bits", required=True)
    p.add_argument("--trits", required=True)
    p.set_defaults(func=partial(_cmd_pack_dp, packer=pack_block40_dp))

    p = sub.add_parser("unpack-block40-dp", help="13-byte dual-plane hex -> bits + trits")
    p.add_argument("--hex", required=True)
    p.set_defaults(func=partial(_cmd_unpack_dp, unpacker=unpack_block40_dp))

    p = sub.add_parser("pack-frame", help="bits + trits -> D6P1 / D6P2 hex")
    p.add_argument("--bits", required=True)
    p.add_argument("--trits", required=True)
    p.add_argument("--version", type=int, choices=(1, 2), default=1)
    p.add_argument("--dtype", type=int, default=0)
    p.add_argument("--block-symbols", type=int, default=0)
    p.add_argument("--flags", type=int, default=0)
    p.set_defaults(func=cmd_pack_frame)

    p = sub.add_parser("unpack-frame", help="D6P0 / D6P1 / D6P2 hex -> bits + trits")
    p.add_argument("--hex", required=True)
    p.set_defaults(func=cmd_unpack_frame)

    p = sub.add_parser("inspect-frame", help="auto-detect frame and show CRC status")
    p.add_argument("--hex", required=True)
    p.set_defaults(func=cmd_inspect_frame)

    p = sub.add_parser("info", help="show version / backend / platform info")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("number", help="encode an integer and show both views")
    p.add_argument("--value", type=int, required=True)
    p.set_defaults(func=cmd_number)

    p = sub.add_parser("demo", help="human-readable one-number demo")
    p.add_argument("--value", type=int, default=42)
    p.add_argument("--check", type=int, default=10000)
    p.set_defaults(func=cmd_demo)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = args.func(args)
        if result is None:  # human-readable commands print directly
            return 0
    except Dual6Error as exc:
        print(json.dumps({"error": exc.code.value, "message": str(exc)}), file=sys.stderr)
        return 2
    except ValueError as exc:
        print(json.dumps({"error": "VALUE_ERROR", "message": str(exc)}), file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
