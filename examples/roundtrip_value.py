"""把"复杂数值"存进 Dual6，再原样读回来。

一句话原理：
  任何数值 -> 一串字节 -> 拆成 0/1 -> 写进 Dual6 的 bit 通道
  trit 通道没有三值数据时先填 0
  再套 D6P1 帧（magic + 长度 + CRC32），就能落盘、mmap 读回、检测损坏

注意：这不是压缩，只是"原样搬运 + 校验"。
Dual6 真正省空间的时候，是 bit 和 trit 两个通道都有真实数据。
"""

from __future__ import annotations

import os
import struct
import sys
import tempfile

# Windows 控制台默认不是 UTF-8，这里显式设一下，避免中文输出乱码。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "python"))

from dual6 import (  # noqa: E402
    Dual6Error,
    MappedFrame,
    pack_dual_plane_v1,
    unpack_dual_plane_v1,
    write_frame,
)


# --------------------------------------------------------------------------
# 字节 <-> Dual6
# --------------------------------------------------------------------------
def bytes_to_bits(data: bytes) -> list[int]:
    """每个字节拆成 8 个 bit（LSB first）。"""
    return [(byte >> bit) & 1 for byte in data for bit in range(8)]


def bits_to_bytes(bits) -> bytes:
    """8 个 bit 拼回 1 个字节（LSB first）。"""
    if len(bits) % 8:
        raise ValueError("bit 数必须是 8 的倍数")
    out = bytearray(len(bits) // 8)
    for i, bit in enumerate(bits):
        if bit:
            out[i >> 3] |= 1 << (i & 7)
    return bytes(out)


def store_bytes(data: bytes) -> bytes:
    """把任意字节写进 Dual6（bit 通道），返回带 CRC 的 D6P1 帧。"""
    bits = bytes_to_bits(data)
    trits = [0] * len(bits)  # 没有三值数据，先填 0
    return pack_dual_plane_v1(bits, trits)


def load_bytes(frame: bytes, nbytes: int) -> bytes:
    """从 D6P1 帧读回原始字节（自动校验 CRC）。"""
    bits, _trits = unpack_dual_plane_v1(frame)
    out = bits_to_bytes(bits)
    if len(out) < nbytes:
        raise ValueError(f"帧里只有 {len(out)} 字节，需要 {nbytes}")
    return out[:nbytes]


# --------------------------------------------------------------------------
# 数值 <-> 字节（显式编码，不依赖 pickle）
# --------------------------------------------------------------------------
def encode_complex(z: complex) -> bytes:
    return struct.pack("<dd", z.real, z.imag)


def decode_complex(data: bytes) -> complex:
    return complex(*struct.unpack("<dd", data[:16]))


def encode_bigint(n: int) -> bytes:
    mag = abs(n)
    raw = mag.to_bytes(max(1, (mag.bit_length() + 7) // 8), "big")
    return bytes([1 if n < 0 else 0, len(raw)]) + raw


def encode_record(
    z: complex,
    big: int,
    f: float,
    name: str,
    shape: list[int],
    values: list[float],
) -> bytes:
    """把一个混合记录拼成字节：复数 + 大整数 + 浮点 + 字符串 + 小张量。"""
    name_bytes = name.encode("utf-8")
    out = bytearray()
    out += encode_complex(z)
    out += encode_bigint(big)
    out += struct.pack("<d", f)
    out += struct.pack("<B", len(name_bytes)) + name_bytes
    out += struct.pack("<B", len(shape)) + b"".join(struct.pack("<I", d) for d in shape)
    out += b"".join(struct.pack("<f", v) for v in values)
    return bytes(out)


def decode_record(data: bytes):
    pos = 0
    z = decode_complex(data[pos : pos + 16])
    pos += 16

    sign, length = data[pos], data[pos + 1]
    pos += 2
    mag = int.from_bytes(data[pos : pos + length], "big")
    pos += length
    big = -mag if sign else mag

    (f,) = struct.unpack_from("<d", data, pos)
    pos += 8

    name_len = data[pos]
    pos += 1
    name = data[pos : pos + name_len].decode("utf-8")
    pos += name_len

    ndim = data[pos]
    pos += 1
    shape = list(struct.unpack_from("<" + "I" * ndim, data, pos))
    pos += 4 * ndim
    count = 1
    for d in shape:
        count *= d
    values = list(struct.unpack_from("<" + "f" * count, data, pos))
    pos += 4 * count

    assert pos == len(data), "记录里有多余字节"
    return z, big, f, name, shape, values


def decode_bigint(data: bytes) -> int:
    sign, length = data[0], data[1]
    mag = int.from_bytes(data[2 : 2 + length], "big")
    return -mag if sign else mag


def _report(title, original, recovered, payload_len, frame_len):
    print(f"\n[{title}]")
    print(f"  原始   : {original}")
    print(f"  字节数 : {payload_len}")
    print(f"  帧大小 : {frame_len} 字节")
    print(f"  读回   : {recovered}")
    ok = recovered == original
    print(f"  一致   : {ok}")
    assert ok, f"{title} 往返失败"


def main() -> int:
    print("=" * 64)
    print("Dual6 复杂数值 存储 / 读取 演示")
    print("=" * 64)

    # 1) 复数：3.5 - 2.25j -> 两个 f64（16 字节）
    z = complex(3.5, -2.25)
    payload = encode_complex(z)
    frame = store_bytes(payload)
    _report("1. 复数", z, decode_complex(load_bytes(frame, len(payload))), len(payload), len(frame))

    # 2) 大整数：2**200 + 12345
    big = 2 ** 200 + 12345
    payload = encode_bigint(big)
    frame = store_bytes(payload)
    _report("2. 大整数", big, decode_bigint(load_bytes(frame, len(payload))), len(payload), len(frame))

    # 3) 混合记录：复数 + 大整数 + 浮点 + 字符串 + 2x3 张量
    record = (complex(1.0, -0.5), -(10 ** 40 + 7), 2.718281828, "边缘设备", [2, 3], [1.0, -2.5, 3.25, 0.0, 4.5, -6.75])
    payload = encode_record(*record)
    frame = store_bytes(payload)
    _report("3. 混合记录", record, decode_record(load_bytes(frame, len(payload))), len(payload), len(frame))

    # 4) 双通道：24 个 bit + 24 个 trit（Dual6 真正的用途）
    flags = [1, 0, 1, 1, 0, 0, 1, 0] * 3
    trits = [1, -1, 0] * 8
    dual_frame = pack_dual_plane_v1(flags, trits)
    got_bits, got_trits = unpack_dual_plane_v1(dual_frame)
    print("\n[4. 双通道 bit + trit]")
    print(f"  原始 bit  : {flags}")
    print(f"  原始 trit : {trits}")
    print(f"  bit 一致  : {got_bits == flags}")
    print(f"  trit 一致 : {got_trits == trits}")
    assert got_bits == flags and got_trits == trits

    # 5) 损坏检测：改 1 个字节，CRC 必须报错
    broken = bytearray(frame)
    broken[-1] ^= 0xFF
    print("\n[5. 损坏检测]")
    try:
        unpack_dual_plane_v1(bytes(broken))
        print("  结果   : 没检测到（不应该发生）")
        return 1
    except Dual6Error as exc:
        print(f"  结果   : {exc.code.value}（符合预期）")
        assert exc.code.value == "CRC_MISMATCH"

    # 6) 落盘 + mmap 读回
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "value.p6")
        z = complex(-8.25, 15.5)
        payload = encode_complex(z)
        frame = store_bytes(payload)
        write_frame(path, frame)
        with MappedFrame(path) as mapped:
            version, bits, _trits, _meta = mapped.unpack()
        recovered = decode_complex(bits_to_bytes(bits)[: len(payload)])
        print("\n[6. 文件 / mmap]")
        print(f"  文件   : {path} ({os.path.getsize(path)} 字节)")
        print(f"  帧版本 : {version}")
        print(f"  原始   : {z}")
        print(f"  读回   : {recovered}")
        print(f"  一致   : {recovered == z}")
        assert recovered == z

    print("\n" + "=" * 64)
    print("全部通过：复杂数值可以原样存入 Dual6，并从文件 / mmap 读回。")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
