"""一边转换成 Dual6 编码，另一边自动无损解码。

调用方只给一个表示；存下来的是一串码元（一个容器整数）：

    二进制引擎:  bits  --from_bits-->  symbols
    三进制引擎:  symbols --to_trits--> trits   (自动、无损)

    三进制引擎:  trits --from_trits--> symbols
    二进制引擎:  symbols --to_bits-->  bits    (自动、无损)

算术在两端引擎里；Dual6 只负责存储和读取。
"""

from __future__ import annotations

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "python"))

from dual6.exact_dual import (  # noqa: E402
    from_balanced_ternary,
    from_bits,
    from_trits,
    to_balanced_ternary,
    to_binary_digits,
    to_bits,
    to_int,
    to_trits,
)


def bits_to_int(bits):
    return sum(b << i for i, b in enumerate(bits))


def main() -> int:
    print("=" * 64)
    print("一边转换，另一边自动无损解码")
    print("=" * 64)

    # ---- 二进制引擎 -> 三进制引擎 ----
    n_bin = 42 + 7                       # 二进制引擎自己的算术
    bits = to_binary_digits(n_bin)       # 它自己的 native 表示
    symbols = from_bits(bits)            # 转换成 Dual6 编码
    print(f"\n[二进制引擎] 42 + 7 = {n_bin}")
    print(f"  native bits      = {bits}")
    print(f"  from_bits(symbols) = {symbols}")

    trits = to_trits(symbols)            # 三进制引擎自动解码
    n_ter = from_balanced_ternary(trits)
    print(f"[三进制引擎] to_trits = {trits}")
    print(f"  还原 = {n_ter}   （无损，读取时不做进制转换）")
    assert n_ter == n_bin
    assert to_int(symbols) == n_bin

    # ---- 三进制引擎 -> 二进制引擎 ----
    m_ter = n_ter + n_ter                # 三进制引擎自己的算术
    trits2 = to_balanced_ternary(m_ter)  # 它自己的 native 表示
    symbols2 = from_trits(trits2)        # 转换成 Dual6 编码
    print(f"\n[三进制引擎] {n_ter} + {n_ter} = {m_ter}")
    print(f"  native trits     = {trits2}")
    print(f"  from_trits(symbols) = {symbols2}")

    bits2 = to_bits(symbols2)            # 二进制引擎自动解码
    m_bin = bits_to_int(bits2)
    print(f"[二进制引擎] to_bits = {bits2}")
    print(f"  还原 = {m_bin}   （无损，读取时不做进制转换）")
    assert m_bin == m_ter
    assert to_int(symbols2) == m_ter

    # ---- 反例：只写自己那一半 ----
    d = 3 * 1 + (0 + 1)                  # 二进制写 1，trit 留默认 0
    print("\n[反例] 只填自己那一半通道：")
    print(f"  d = {d}  to_bits -> [{(d // 3)}]  to_trits -> [{(d % 3 - 1)}]")
    print("  三进制侧读到的是默认值 0，不是 1 —— 这不是无损交换。")

    print("\n" + "=" * 64)
    print("结论：调用方只给一个表示；编码内部完成配对；另一边自动解码。")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
