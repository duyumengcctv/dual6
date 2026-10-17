"""同一个数 N，存一次，二进制引擎和三进制引擎都能无损读回。

核心 API 在 ``dual6.exact_dual``：

    from dual6.exact_dual import encode_number, read_binary, read_ternary

写入：同时算出 N 的 base-2 与 balanced-base-3 展开，配对成 6 态码元。
读取：二进制视图只做 d//3，三进制视图只做 d%3-1，再各自加权求和。
"""

from __future__ import annotations

import os
import struct
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "python"))

from dual6.exact_dual import (  # noqa: E402
    decode_f64,
    encode_f64,
    encode_number,
    read_binary,
    read_ternary,
    to_balanced_ternary,
    to_binary_digits,
)


def show(n: int) -> None:
    symbols = encode_number(n)
    bits = "".join(str(b) for b in reversed(to_binary_digits(n)))
    trits = "".join(
        "+" if t == 1 else ("-" if t == -1 else "0") for t in reversed(to_balanced_ternary(n))
    )
    print(f"\nN = {n}")
    print(f"  二进制展开    : {bits}")
    print(f"  平衡三进制展开: {trits}")
    print(f"  码元 (LSB first): {symbols}")
    print(f"  二进制视图读回: {read_binary(symbols)}")
    print(f"  三进制视图读回: {read_ternary(symbols)}")
    assert read_binary(symbols) == n and read_ternary(symbols) == n


def main() -> int:
    print("=" * 70)
    print("同一个数存一次，二进制 / 三进制各读各的（无损）")
    print("=" * 70)

    for n in (0, 5, 42, 255, 2 ** 64 + 12345):
        show(n)

    for n in range(20000):
        symbols = encode_number(n)
        assert read_binary(symbols) == n, f"binary view failed at {n}"
        assert read_ternary(symbols) == n, f"ternary view failed at {n}"
    print("\n全量对拍 0..19999：两个视图都等于 N ✓")

    # 浮点：编码的是 IEEE-754 位模式，两个视图都能还原同一个 double
    print("\n浮点（按 IEEE-754 位模式编码）：")
    for value in (3.141592653589793, -0.1, 1e300):
        symbols = encode_f64(value)
        via_binary = struct.unpack(
            "<d", read_binary(symbols).to_bytes(8, "little")
        )[0]
        via_ternary = struct.unpack(
            "<d", read_ternary(symbols).to_bytes(8, "little")
        )[0]
        print(f"  {value!r:>24} -> binary视图={via_binary!r}  ternary视图={via_ternary!r}")
        assert via_binary == via_ternary == value
        assert decode_f64(symbols) == value

    print("\n结论：写入时把两个分量压进同一串码元；读取零转换、无损。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
